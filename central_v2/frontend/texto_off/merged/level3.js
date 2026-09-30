import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergedTextoff } from "/_app/api/textoff.js";
import { createMergedExecution } from "/texto_off/merged/execution.js";
import { createMergedView } from "/texto_off/merged/view.js";
import { openCandidateReview } from "/texto_off/merged/candidate_review.js";

export function render(container) {
  let requestId = 0;
  let controller;
  let disposed = false;
  const view = createMergedView((chapters) => execution.execute(chapters), {
    title: "Texto Off — Merged Nível III",
    mode: "level3",
    description: "Analisa os MERGES originais em recortes sobrepostos para localizar degradês e contornos estilizados. Candidatos requerem revisão; não altera imagens nem aciona patches.",
    onInspect: (row) => {
      if (!row.candidate_pages?.length) return;
      const { provider, manga } = getContext();
      openCandidateReview({ provider, manga, chapter: row.chapter, pages: row.candidate_pages });
    },
  });
  container.replaceChildren(view.element);
  const execution = createMergedExecution({
    level: "3", onStatus: view.setExecution, onReview: view.inspect,
    onComplete: async () => { view.clearSelection(); await load(); },
  });

  async function load() {
    const id = ++requestId;
    controller?.abort();
    controller = new AbortController();
    const { provider, manga } = getContext();
    if (!provider || !manga) {
      view.update({ status: "idle", provider, manga, chapters: [] });
      return;
    }
    view.update({ status: "loading", provider, manga, chapters: [] });
    try {
      const result = await fetchMergedTextoff(provider, manga, controller.signal, "3");
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
    controller?.abort();
    unsubscribe();
    execution.dispose();
    view.dispose();
  };
}
