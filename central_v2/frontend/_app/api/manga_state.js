export async function fetchMangaState(provider, manga) {
  const params = new URLSearchParams({
    provider,
    manga,
  });

  const response = await fetch(`/api/state?${params}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(
      `Falha ao carregar estado da obra (${response.status}).`,
    );
  }

  return response.json();
}
