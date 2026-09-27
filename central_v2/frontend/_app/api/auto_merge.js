export async function fetchLevel1(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  const response = await fetch(`/api/auto-merge/level1?${query}`, {
    headers: { Accept: "application/json" }, signal,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Falha ao consultar o Nível I (${response.status}).`);
  }
  return payload;
}
