export async function fetchMergeManual(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  const response = await fetch(`/api/merge-manual?${query}`, { signal });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}

export function mergeManualImageUrl(provider, manga, chapter, file) {
  const query = new URLSearchParams({ provider, manga, chapter, file });
  return `/api/merge-manual/image?${query}`;
}

export async function generateMergeManualProposal(selection, cuts) {
  const response = await fetch("/api/merge-manual/proposal", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ ...selection, cuts }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}
