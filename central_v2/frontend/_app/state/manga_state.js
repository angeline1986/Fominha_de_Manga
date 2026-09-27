const mangaState = {
  provider: null,
  manga: null,
  chapters: [],
  summary: {
    chapters: 0,
  },
};

export function setMangaState(state) {
  mangaState.provider = state?.provider ?? null;
  mangaState.manga = state?.manga ?? null;
  mangaState.chapters = [...(state?.chapters ?? [])];
  mangaState.summary = {
    chapters: state?.summary?.chapters ?? 0,
  };
}

export function clearMangaState() {
  mangaState.provider = null;
  mangaState.manga = null;
  mangaState.chapters = [];
  mangaState.summary = {
    chapters: 0,
  };
}

export function getMangaState() {
  return {
    provider: mangaState.provider,
    manga: mangaState.manga,
    chapters: [...mangaState.chapters],
    summary: {
      ...mangaState.summary,
    },
  };
}
