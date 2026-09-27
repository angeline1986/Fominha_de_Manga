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

export async function initializeContext() {
  const catalog = await fetchCatalog();

  setCatalog(catalog);
  clearMangaState();

  return getContext();
}

export function changeProvider(provider) {
  const { catalog } = getContext();

  if (provider && !Object.hasOwn(catalog, provider)) {
    throw new Error(`Provider inválido: ${provider}`);
  }

  mangaRequestSequence += 1;
  selectProvider(provider);
  clearMangaState();

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

  selectManga(manga);
  clearMangaState();

  if (!manga) {
    mangaRequestSequence += 1;

    return {
      context: getContext(),
      mangaState: getMangaState(),
    };
  }

  const requestSequence = ++mangaRequestSequence;
  const state = await fetchMangaState(provider, manga);

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
