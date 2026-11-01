import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchImageValidation, startImageAnalysis, applyImageCorrection,
  fetchValidationJob } from "/_app/api/image_validation.js";
import { confirmMessage, showMessage } from "/_shared/messages/messages.js";
import { createValidationList } from "/visao_geral/validar_imagens/list.js";
import { createValidationViewer } from "/visao_geral/validar_imagens/viewer.js";

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function render(container) {
  let disposed = false, revision = 0, request = null, busy = false;
  let context = { provider: null, manga: null }, rows = [], openChapter = null;
  const list = createValidationList({ onExecute: execute, onOpen: open });
  const viewer = createValidationViewer({ onBack: back, onApply: apply });
  container.replaceChildren(list.element);

  function currentContext() {
    const now = getContext();
    return now.provider === context.provider && now.manga === context.manga;
  }

  function back() {
    viewer.dispose();
    openChapter = null;
    container.replaceChildren(list.element);
  }

  function open(chapter) {
    const row = rows.find((item) => item.chapter === chapter && item.status === "review");
    if (!row?.images.length) return;
    openChapter = chapter;
    viewer.update(row, context);
    container.replaceChildren(viewer.element);
  }

  async function refresh(reset = false) {
    const now = getContext();
    const changed = now.provider !== context.provider || now.manga !== context.manga;
    context = { provider: now.provider, manga: now.manga };
    const ownRevision = ++revision;
    request?.abort();
    request = new AbortController();
    if (changed) {
      back();
      rows = [];
      list.resetContext();
    }
    if (!context.provider || !context.manga) {
      list.update([], "idle");
      return;
    }
    if (changed || reset) list.update([], "loading");
    try {
      const result = await fetchImageValidation(context.provider, context.manga, request.signal);
      if (disposed || ownRevision !== revision) return;
      if (result.provider !== context.provider || result.manga !== context.manga
          || !Array.isArray(result.chapters)) throw new Error("Dados de outra obra recebidos.");
      rows = result.chapters;
      list.update(rows);
      if (openChapter) {
        const row = rows.find((item) => item.chapter === openChapter && item.status === "review");
        if (row?.images.length) viewer.update(row, context);
        else back();
      }
    } catch (error) {
      if (disposed || ownRevision !== revision || error.name === "AbortError") return;
      list.update([], "error", error.message);
      back();
    }
  }

  async function runJob(start, title) {
    if (busy || disposed) return false;
    const ownRevision = revision;
    busy = true;
    list.setBusy(true, { title, message: "Enviando execução…", total: 1 });
    try {
      const created = await start();
      if (!created.job?.id) throw new Error("A Central não confirmou a execução.");
      let job = created.job;
      while (!disposed && ownRevision === revision && currentContext()
          && !["completed", "failed"].includes(job.status)) {
        const progress = job.progress || {};
        list.setBusy(true, { title, message: progress.message, percent: progress.percent,
          completed: progress.completed, total: progress.total });
        await pause(600);
        if (disposed || ownRevision !== revision || !currentContext()) return false;
        ({ job } = await fetchValidationJob(job.id));
      }
      if (disposed || ownRevision !== revision || !currentContext()) return false;
      if (job.status === "failed") throw new Error(job.error || "A execução falhou.");
      return true;
    } catch (error) {
      if (!disposed && ownRevision === revision && currentContext()) {
        await showMessage({ title: "Falha em Validar Imagens", message: error.message });
        await refresh();
      }
      return false;
    } finally {
      busy = false;
      if (!disposed) list.setBusy(false);
    }
  }

  async function execute(chapters) {
    if (busy || !chapters.length) return;
    const { provider, manga } = context;
    const accepted = await confirmMessage({ title: "Validar Imagens",
      message: `Analisar dimensões de ${chapters.length} capítulo(s)?`, confirmText: "Executar" });
    if (!accepted || disposed || context.provider !== provider || context.manga !== manga) return;
    const success = await runJob(() => startImageAnalysis(provider, manga, chapters), "Analisando dimensões");
    if (!success || disposed) return;
    list.resetSelection();
    await refresh();
    list.selectReview();
  }

  async function apply(chapter, image) {
    if (busy) return;
    const { provider, manga } = context;
    const row = rows.find((item) => item.chapter === chapter);
    if (!row || !row.images.some((item) => item.file === image.file)) return;
    const height = Math.max(1, Math.round(image.height * row.dominant_width / image.width));
    const accepted = await confirmMessage({ title: "Aplicar solução proposta?",
      message: `Cap. ${chapter} · ${image.file}: ${image.width} × ${image.height} px → ${row.dominant_width} × ${height} px. O original será preservado com sufixo _old.`,
      confirmText: "Aplicar" });
    if (!accepted || disposed || context.provider !== provider || context.manga !== manga) return;
    const success = await runJob(() => applyImageCorrection(provider, manga, chapter, image.file),
      `Corrigindo ${image.file}`);
    if (!success || disposed) return;
    await refresh();
    await showMessage({ title: "Correção aplicada", message: `${image.file} corrigida no capítulo ${chapter}.` });
  }

  const unsubscribe = subscribeContext(() => {
    const now = getContext();
    if (now.provider !== context.provider || now.manga !== context.manga) refresh(true);
  });
  refresh(true);
  return () => {
    disposed = true;
    revision += 1;
    request?.abort();
    unsubscribe();
    viewer.dispose();
    list.dispose();
  };
}
