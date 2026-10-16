import { getContext, subscribeContext } from "/_app/state/context.js";
import { subscribeCleanerInvalidation } from "/_app/state/cleaner_revision.js";

let entry = null;
let generation = 0;
let contextKey = "";
const listeners = new Set();

function key(provider, manga) { return JSON.stringify([provider, manga]); }
contextKey = key(getContext().provider, getContext().manga);

function clear(notify = true) {
  generation += 1;
  entry?.controller?.abort();
  entry = null;
  if (notify) listeners.forEach((listener) => listener());
}

subscribeContext(() => {
  const { provider, manga } = getContext();
  const next = key(provider, manga);
  if (next !== contextKey) { contextKey = next; clear(false); }
});

export function subscribeCleanerOverview(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

subscribeCleanerInvalidation((provider, manga) => {
  const target = key(provider, manga);
  if (!provider || !manga || entry?.key === target || contextKey === target) clear();
});

export function cachedCleanerOverview(provider, manga) {
  return entry?.key === key(provider, manga) ? entry.data ?? null : null;
}

export function loadCleanerOverview(provider, manga) {
  const requestedKey = key(provider, manga);
  if (entry?.key === requestedKey) {
    if (entry.data) return Promise.resolve(entry.data);
    if (entry.promise) return entry.promise;
  }
  clear(false);
  const version = generation;
  const controller = new AbortController();
  const current = { key: requestedKey, controller, data: null, promise: null };
  entry = current;
  const query = new URLSearchParams({ provider, manga });
  current.promise = fetch(`/api/textoff/merged/level1?${query}`, {
    signal: controller.signal, cache: "no-store",
  }).then(async (response) => {
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
    if (payload.provider !== provider || payload.manga !== manga || !Array.isArray(payload.chapters)) {
      throw new Error("A consulta retornou dados de outra obra.");
    }
    if (generation === version && entry === current) current.data = payload;
    return payload;
  }).catch((error) => {
    if (entry === current) entry = null;
    throw error;
  }).finally(() => { current.promise = null; current.controller = null; });
  return current.promise;
}
