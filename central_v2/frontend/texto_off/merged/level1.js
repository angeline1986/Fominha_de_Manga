import { getContext, subscribeContext } from "/_app/state/context.js";
import { cachedCleanerOverview, loadCleanerOverview,
  subscribeCleanerOverview } from "/_app/api/cleaner_overview.js";
import { createMergedExecution } from "/texto_off/merged/execution.js";
import { createMergedView } from "/texto_off/merged/view.js";

export function render(container) {
  let requestId = 0;
  let disposed = false;
  const view = createMergedView((chapters) => execution.execute(chapters), {
    title: "Auto-Cleaner — Passo 1: Balões Sólidos",
    description: "Limpeza geral padrão e proteção de áreas translúcidas.",
    executeLabel: "Executar Passo 1",
    mode: "overview",
    comparisonMode: "level1",
  });
  container.replaceChildren(view.element);
  const execution = createMergedExecution({
    level: "1",
    onStatus: view.setExecution,
    onComplete: async () => {
      view.clearSelection();
      const { provider, manga } = getContext();
      await loadCleanerOverview(provider, manga);
    },
  });

  async function load() {
    const id = ++requestId;
    const { provider, manga } = getContext();
    if (!provider || !manga) {
      view.update({ status: "idle", provider, manga, chapters: [] });
      return;
    }
    const cached = cachedCleanerOverview(provider, manga);
    if (cached) { view.update({ status: "ready", ...cached }); return; }
    view.update({ status: "loading", provider, manga, chapters: [] });
    try {
      const result = await loadCleanerOverview(provider, manga);
      const current = getContext();
      if (!disposed && id === requestId && current.provider === provider && current.manga === manga) {
        view.update({ status: "ready", ...result });
      }
    } catch (error) {
      if (!disposed && id === requestId && error.name !== "AbortError") {
        view.update({ status: "error", provider, manga, chapters: [], error: error.message });
      }
    }
  }

  const unsubscribe = subscribeContext(load);
  const unsubscribeData = subscribeCleanerOverview(load);
  load();
  return () => {
    disposed = true;
    requestId += 1;
    unsubscribe();
    unsubscribeData();
    execution.dispose();
    view.dispose();
  };
}
