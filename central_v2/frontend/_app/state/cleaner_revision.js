// Notify interested views when cleaner source data may have changed.
const listeners = new Set();

export function subscribeCleanerInvalidation(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function invalidateCleanerOverview(provider, manga) {
  listeners.forEach((listener) => listener(provider, manga));
}
