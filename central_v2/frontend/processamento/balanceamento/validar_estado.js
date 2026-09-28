import { getContext, subscribeContext } from "/_app/state/context.js";
import { setBalanceSelection } from "/_app/state/balanceamento.js";
import { fetchBalanceamento, submitBalanceJob, waitForBalanceJob } from "/_app/api/balanceamento.js";
import { createBalanceValidationView } from "/processamento/balanceamento/validar_estado_view.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { showMessage } from "/_shared/messages/messages.js";

export function render(container) {
  const view = createBalanceValidationView({ onOpenEditor, onRevalidate });
  const progress = createJobProgress("Validar Balanceamento");
  container.replaceChildren(view.element, progress.element);
  let revision = 0;
  let request;
  let disposed = false;
  let running = false;
  const unsubscribe = subscribeContext(load);
  const { provider, manga } = getContext();
  if (provider && manga) load();

  async function load() {
    const current = ++revision;
    request?.abort();
    request = new AbortController();
    const { provider, manga } = getContext();
    if (!provider || !manga) { view.update({ status: "idle", provider, manga, chapters: [] }); return; }
    view.update({ status: "loading", provider, manga, chapters: [] });
    try {
      const data = await fetchBalanceamento(provider, manga, request.signal);
      if (!disposed && current === revision) view.update({ status: "ready", provider, manga, ...data });
    } catch (error) {
      if (!disposed && current === revision && error.name !== "AbortError") view.update({ status: "error", provider, manga, chapters: [], error: error.message });
    }
  }

  function onOpenEditor(selection) {
    const { provider, manga } = getContext();
    setBalanceSelection({ provider, manga, ...selection });
    container.dispatchEvent(new CustomEvent("menu:action", { bubbles: true, detail: { action: "novos-cortes" } }));
  }

  async function onRevalidate() {
    if (running) return;
    const { provider, manga } = getContext();
    if (!provider || !manga) return;
    running = true;
    progress.update({ busy: true, message: "Iniciando a análise dos merges oficiais…" });
    try {
      const { job } = await submitBalanceJob("validate", { provider, manga });
      await waitForBalanceJob(job, reportProgress);
      if (disposed) return;
      const current = getContext();
      if (current.provider !== provider || current.manga !== manga) return;
      await load();
      await showMessage({ title: "Validação atualizada", message: "O diagnóstico foi registrado sem modificar os merges oficiais." });
    } catch (error) {
      if (!disposed) await showMessage({ title: "Falha ao validar Balanceamento", message: error.message });
    } finally {
      running = false;
      if (!disposed) progress.update({ busy: false });
    }
  }

  function reportProgress(job) {
    const data = job.progress || {};
    progress.update({ busy: true, title: `Validar Balanceamento · ${job.status}`, message: data.message, percent: data.percent, completed: data.completed, total: data.total });
  }

  if (!provider || !manga) load();
  return () => { disposed = true; revision += 1; request?.abort(); unsubscribe(); view.dispose(); };
}
