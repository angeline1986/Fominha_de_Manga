import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergeManual, mergeManualImageUrl } from "/_app/api/merge_manual.js";
import { setMergeManualSelection } from "/_app/state/merge_manual.js";
import { createMergeManualView } from "/processamento/merge_manual/view.js";

export function render(container) {
  const view = createMergeManualView();
  container.replaceChildren(view.element);
  let requestId = 0;
  let abortController;
  function openCuts(event) {
    const { provider, manga } = getContext();
    setMergeManualSelection({ provider, manga, ...event.detail });
    container.dispatchEvent(new CustomEvent("menu:action", {
      bubbles: true, detail: { action: "novos-merges" },
    }));
  }
  view.element.addEventListener("merge-manual:open-cuts", openCuts);
  const unsubscribe = subscribeContext(load);

  async function load() {
    const id = ++requestId;
    abortController?.abort();
    abortController = new AbortController();
    const { provider, manga } = getContext();
    if (!provider || !manga) {
      view.update({ status: "idle", chapters: [] });
      return;
    }
    view.update({ status: "loading", provider, manga, chapters: [] });
    try {
      const data = await fetchMergeManual(provider, manga, abortController.signal);
      if (id === requestId) view.update({ status: "ready", provider, manga, ...data });
    } catch (error) {
      if (id === requestId && error.name !== "AbortError") {
        view.update({ status: "error", provider, manga, chapters: [], error: error.message });
      }
    }
  }

  load();
  return () => {
    requestId += 1;
    abortController?.abort();
    unsubscribe();
    view.element.removeEventListener("merge-manual:open-cuts", openCuts);
    view.dispose();
  };
}

export { mergeManualImageUrl };
