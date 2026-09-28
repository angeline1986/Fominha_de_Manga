export function createLevel3Store() {
  let state = { status: "idle", chapters: [], provider: null, manga: null, error: "" };
  const listeners = new Set();
  return {
    get: () => state,
    set(next) {
      state = { ...state, ...next };
      listeners.forEach((listener) => listener(state));
    },
    subscribe(listener) {
      listeners.add(listener);
      listener(state);
      return () => listeners.delete(listener);
    },
  };
}
