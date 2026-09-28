export async function fetchBalanceamento(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  return requestJson(`/api/balanceamento?${query}`, { signal, cache: "no-store" });
}

export function balanceamentoImageUrl(provider, manga, chapter, file, kind, proposalId = "") {
  const query = new URLSearchParams({ provider, manga, chapter, file, kind });
  if (proposalId) query.set("proposal_id", proposalId);
  return `/api/balanceamento/image?${query}`;
}

export async function submitBalanceJob(action, data) {
  return requestJson(`/api/balanceamento/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(data),
  });
}

export async function waitForBalanceJob(job, onProgress = () => {}) {
  if (!job?.id) throw new Error("A Central não confirmou a criação do job.");
  let current = job;
  while (!["completed", "failed"].includes(current.status)) {
    onProgress(current);
    await new Promise((resolve) => setTimeout(resolve, 500));
    ({ job: current } = await requestJson(`/api/jobs/${encodeURIComponent(job.id)}`, { cache: "no-store" }));
  }
  onProgress(current);
  if (current.status === "failed") throw new Error(current.error || "O job de Balanceamento falhou.");
  return current.results || [];
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}
