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

export function mergeManualProposalImageUrl(provider, manga, chapter, proposalId, file) {
  const query = new URLSearchParams({ provider, manga, chapter, proposal_id: proposalId, file });
  return `/api/merge-manual/proposal/image?${query}`;
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

export async function applyMergeManualProposal(selection) {
  const response = await fetch("/api/merge-manual/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(selection),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}
