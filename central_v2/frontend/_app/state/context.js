const context = {
  catalog: {},
  provider: null,
  manga: null,
};

const listeners = new Set();

export function subscribeContext(listener) {
  listeners.add(listener);

  return () => listeners.delete(listener);
}

function notifyContext() {
  listeners.forEach((listener) => listener(getContext()));
}

export function setCatalog(catalog) {
  context.catalog = catalog ?? {};
  notifyContext();
}

export function selectProvider(provider) {
  context.provider = provider || null;
  context.manga = null;
  notifyContext();
}

export function selectManga(manga) {
  context.manga = manga || null;
  notifyContext();
}

export function getContext() {
  return {
    catalog: context.catalog,
    provider: context.provider,
    manga: context.manga,
  };
}
