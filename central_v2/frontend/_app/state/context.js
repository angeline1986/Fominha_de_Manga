const context = {
  catalog: {},
  provider: null,
  manga: null,
};

export function setCatalog(catalog) {
  context.catalog = catalog ?? {};
}

export function selectProvider(provider) {
  context.provider = provider || null;
  context.manga = null;
}

export function selectManga(manga) {
  context.manga = manga || null;
}

export function getContext() {
  return {
    catalog: context.catalog,
    provider: context.provider,
    manga: context.manga,
  };
}
