export function createLevel1Store() {
  let state = { status: "idle", provider: null, manga: null, chapters: [], error: "" };
  const listeners = new Set();
  const get = () => ({ ...state, chapters: [...state.chapters] });

  return {
    get,
    set(next) {
      state = { ...state, ...next };
      listeners.forEach((listener) => listener(get()));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
