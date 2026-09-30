import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergedTextoff } from "/_app/api/textoff.js";
import { createMergedExecution } from "/texto_off/merged/execution.js";
import { createMergedView } from "/texto_off/merged/view.js";

export function render(container) {
  let requestId = 0;
  let abortController;
  let disposed = false;
  const view = createMergedView((chapters) => execution.execute(chapters), { title: "Limpeza de Balões — Modo Legado", executeLabel: "Executar Legado" });
  container.replaceChildren(view.element);
  const execution = createMergedExecution({
    onStatus: view.setExecution,
    onComplete: async () => { view.clearSelection(); await load(); },
  });

  async function load() {
    const id = ++requestId;
    abortController?.abort();
    abortController = new AbortController();
    const { provider, manga } = getContext();
    if (!provider || !manga) {
      view.update({ status: "idle", provider, manga, chapters: [] });
      return;
    }
    view.update({ status: "loading", provider, manga, chapters: [] });
    try {
      const result = await fetchMergedTextoff(provider, manga, abortController.signal);
      if (!disposed && id === requestId) view.update({ status: "ready", ...result });
    } catch (error) {
      if (!disposed && id === requestId && error.name !== "AbortError") {
        view.update({ status: "error", provider, manga, chapters: [], error: error.message });
      }
    }
  }

  const unsubscribe = subscribeContext(load);
  load();
  return () => {
    disposed = true;
    requestId += 1;
    abortController?.abort();
    unsubscribe();
    execution.dispose();
    view.dispose();
  };
}
