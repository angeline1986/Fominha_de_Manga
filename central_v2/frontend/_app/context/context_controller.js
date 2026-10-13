import { fetchCatalog } from "/_app/api/catalog.js";
import { fetchMangaState } from "/_app/api/manga_state.js";

import {
  getContext,
  selectManga,
  selectProvider,
  setCatalog,
} from "/_app/state/context.js";

import {
  clearMangaState,
  getMangaState,
  setMangaState,
} from "/_app/state/manga_state.js";

let mangaRequestSequence = 0;
let mangaStateRequest = null;
let synchronizationRequest = null;

export async function initializeContext() {
  const catalog = await fetchCatalog();

  clearMangaState();
  setCatalog(catalog);

  return getContext();
}

export function changeProvider(provider) {
  const { catalog } = getContext();

  if (provider && !Object.hasOwn(catalog, provider)) {
    throw new Error(`Provider inválido: ${provider}`);
  }

  mangaRequestSequence += 1;
  clearMangaState();
  selectProvider(provider);

  return getContext();
}

export async function changeManga(manga) {
  const { catalog, provider } = getContext();

  if (!provider) {
    throw new Error("Selecione um provider antes da obra.");
  }

  if (manga && !(catalog[provider] ?? []).includes(manga)) {
    throw new Error(
      `Obra inválida para o provider ${provider}: ${manga}`,
    );
  }

  const requestSequence = ++mangaRequestSequence;
  clearMangaState();
  selectManga(manga);

  if (!manga) {
    return {
      context: getContext(),
      mangaState: getMangaState(),
    };
  }

  const activeRequest = { requestSequence, provider, manga };
  activeRequest.promise = fetchMangaState(provider, manga);
  mangaStateRequest = activeRequest;
  let state;
  try {
    state = await activeRequest.promise;
  } finally {
    if (mangaStateRequest === activeRequest) mangaStateRequest = null;
  }

  if (requestSequence !== mangaRequestSequence) {
    return {
      context: getContext(),
      mangaState: getMangaState(),
    };
  }

  setMangaState(state);

  return {
    context: getContext(),
    mangaState: getMangaState(),
  };
}

async function synchronizeCurrentContext() {
  const requestSequence = mangaRequestSequence;
  const catalog = await fetchCatalog();
  const current = getContext();
  const provider = current.provider && Object.hasOwn(catalog, current.provider)
    ? current.provider : null;
  const manga = provider && (catalog[provider] ?? []).includes(current.manga)
    ? current.manga : null;

  setCatalog(catalog);
  if (provider !== current.provider) {
    changeProvider(provider);
    return { context: getContext(), mangaState: getMangaState() };
  }
  if (manga !== current.manga) {
    return changeManga(manga);
  }
  if (!manga || requestSequence !== mangaRequestSequence) {
    return { context: getContext(), mangaState: getMangaState() };
  }
  if (mangaStateRequest?.requestSequence === requestSequence
    && mangaStateRequest.provider === provider && mangaStateRequest.manga === manga) {
    await mangaStateRequest.promise;
    return { context: getContext(), mangaState: getMangaState() };
  }

  const stateSequence = ++mangaRequestSequence;
  const state = await fetchMangaState(provider, manga);
  const latest = getContext();
  if (stateSequence === mangaRequestSequence
    && latest.provider === provider && latest.manga === manga) {
    setMangaState(state);
  }
  return { context: getContext(), mangaState: getMangaState() };
}

export function synchronizeContext() {
  if (synchronizationRequest) return synchronizationRequest;
  const request = synchronizeCurrentContext().finally(() => {
    if (synchronizationRequest === request) synchronizationRequest = null;
  });
  synchronizationRequest = request;
  return request;
}
