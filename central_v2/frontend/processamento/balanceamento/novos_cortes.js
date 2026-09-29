import { getContext, subscribeContext } from "/_app/state/context.js";
import { clearBalanceSelection, getBalanceSelection } from "/_app/state/balanceamento.js";
import { fetchBalanceamento, submitBalanceJob, waitForBalanceJob } from "/_app/api/balanceamento.js";
import { createBalanceCutsView } from "/processamento/balanceamento/novos_cortes_view.js";
import { defaultRulerColors } from "/_shared/rulers/palette.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { confirmMessage, showMessage } from "/_shared/messages/messages.js";

export function render(container) {
  const view = createBalanceCutsView({
    onBack: () => navigate(container, "validar-estado"),
    onPrepare, onGenerate, onApply, onZoom: () => {},
  });
  const progress = createJobProgress("Balanceamento");
  container.replaceChildren(view.element, progress.element);
  let selection = getBalanceSelection();
  const context = getContext();
  const validSelection = selection && selection.provider === context.provider && selection.manga === context.manga;
  let draft = null;
  let busy = Boolean(validSelection);
  let disposed = false;
  let active = false;
  view.update({ selection: validSelection ? selection : null, draft: null, busy });
  const unsubscribe = subscribeContext((next) => {
    if (!selection || (selection.provider === next.provider && selection.manga === next.manga)) return;
    selection = null;
    clearBalanceSelection();
    view.update({ selection: null, draft: null });
    navigate(container, "validar-estado");
  });
  if (validSelection) restoreDraft();

  async function restoreDraft() {
    try {
      const state = await fetchBalanceamento(selection.provider, selection.manga);
      if (disposed) return;
      const chapter = state.chapters.find((row) => String(row.chapter) === String(selection.chapter));
      const candidate = chapter?.proposal;
      if (candidate?.source_preview && sameFiles(candidate.selected_files, selection.merges)) {
        draft = candidate;
        busy = false;
        view.update({ draft, busy });
        return;
      }
    } catch (error) {
      if (!disposed) {
        busy = false;
        view.update({ busy });
        await showMessage({ title: "Falha ao carregar os merges", message: error.message });
      }
      return;
    }
    if (!disposed) await onPrepare([...defaultRulerColors]);
  }

  async function onPrepare(rulerColors) {
    await run("prepare", {}, "Preparando editor de cortes…", (result) => {
      draft = { ...result, ruler_colors: rulerColors }; view.update({ draft });
    });
  }

  async function onGenerate(cuts, rulerColors) {
    await run("proposal", { cuts }, "Gerando proposta manual…", (result) => {
      draft = { ...draft, ...result, ruler_colors: rulerColors, source_preview: draft.source_preview, source_slices: draft.source_slices, merge_ranges: draft.merge_ranges, region: draft.region };
      view.update({ draft });
    });
  }

  async function onApply() {
    if (!draft || draft.status !== "PROPOSTA_GERADA") return;
    const confirmed = await confirmMessage({ title: "Aplicar composição final", message: "A proposta substituirá os merges selecionados no MERGE oficial. Deseja continuar?", confirmText: "Aplicar" });
    const current = getContext();
    if (!confirmed || disposed) return;
    if (current.provider !== selection.provider || current.manga !== selection.manga) {
      await showMessage({ title: "Contexto alterado", message: "A obra mudou durante a confirmação. Abra a seleção novamente." });
      return;
    }
    await run("apply", {}, "Validando e aplicando a composição…", async (result) => {
      clearBalanceSelection();
      await showMessage({ title: "Composição aplicada", message: result.message || "A composição foi aplicada e validada no MERGE oficial." });
      navigate(container, "validar-estado");
    });
  }

  async function run(action, extra, message, onComplete) {
    const current = getContext();
    if (active || !selection || selection.provider !== current.provider || selection.manga !== current.manga) return;
    active = true; busy = true; view.update({ busy });
    progress.update({ busy: true, title: message, message });
    try {
      const response = await submitBalanceJob(action, { provider: selection.provider, manga: selection.manga,
        chapter: selection.chapter, merges: selection.merges, ...extra });
      const results = await waitForBalanceJob(response.job, reportProgress);
      const result = results[0]?.data || {};
      if (!disposed) await onComplete(result);
    } catch (error) {
      if (!disposed) await showMessage({ title: "Falha no Balanceamento", message: error.message });
    } finally {
      active = false; busy = false;
      if (!disposed) { view.update({ busy }); progress.update({ busy: false }); }
    }
  }

  function reportProgress(job) {
    const data = job.progress || {};
    progress.update({ busy: true, title: `Balanceamento · ${job.status}`, message: data.message,
      percent: data.percent, completed: data.completed, total: data.total });
  }

  function sameFiles(left, right) {
    if (!Array.isArray(left) || left.length !== right.length) return false;
    return left.every((file) => right.includes(file));
  }

  return () => { disposed = true; unsubscribe(); view.dispose(); };
}

function navigate(container, action) {
  container.dispatchEvent(new CustomEvent("menu:action", { bubbles: true, detail: { action } }));
}
