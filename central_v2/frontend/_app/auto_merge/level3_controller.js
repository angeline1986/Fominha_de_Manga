import { fetchLevel3 } from "/_app/api/auto_merge.js";
import { getContext, subscribeContext } from "/_app/state/context.js";

export function connectLevel3(store) {
  let revision = 0;
  let request = null;
  let disposed = false;

  async function refresh() {
    if (disposed) return;
    const current = ++revision;
    request?.abort();
    const { provider, manga } = getContext();
    store.set({ provider, manga, chapters: [], error: "", status: "idle" });
    if (!provider || !manga) return;
    request = new AbortController();
    store.set({ status: "loading" });
    try {
      const result = await fetchLevel3(provider, manga, request.signal);
      if (disposed || current !== revision) return;
      if (result.provider !== provider || result.manga !== manga || !Array.isArray(result.chapters)) {
        throw new Error("A consulta de resíduos retornou um contexto incompatível.");
      }
      store.set({ status: "ready", chapters: result.chapters });
    } catch (error) {
      if (disposed || current !== revision) return;
      store.set({ status: "error", error: error.message, chapters: [] });
    }
  }

  const unsubscribe = subscribeContext(refresh);
  refresh();
  return {
    refresh,
    dispose() {
      disposed = true;
      revision += 1;
      request?.abort();
      unsubscribe();
    },
  };
}
