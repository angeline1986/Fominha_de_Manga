import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergedTextoff } from "/_app/api/textoff.js";
import { createMergedView } from "/texto_off/merged/view.js";

export function render(container) {
  let requestId = 0;
  let controller;
  let disposed = false;
  const view = createMergedView(() => {}, {
    title: "Auto-Cleaner Check",
    description: "Revise, classifique e aprove as áreas sugeridas por Mapear, Sommelier e pelo catálogo manual.",
    mode: "overview",
    comparisonMode: "check",
    comparisonScope: "check",
    showExecute: false,
    selectionEnabled: false,
  });
  container.replaceChildren(view.element);

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
      const result = await fetchMergedTextoff(provider, manga, controller.signal, "1");
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
    view.dispose();
  };
}
