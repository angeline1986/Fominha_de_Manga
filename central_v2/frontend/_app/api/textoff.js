async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}

export async function fetchMergedTextoff(provider, manga, signal, level = "") {
  const query = new URLSearchParams({ provider, manga });
  const suffix = level ? `/level${level}` : "";
  return requestJson(`/api/textoff/merged${suffix}?${query}`, { signal, cache: "no-store" });
}

export async function startMergedTextoff(provider, manga, chapters, level = "") {
  const suffix = level ? `/level${level}` : "";
  return requestJson(`/api/textoff/merged${suffix}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export async function waitForTextoffJob(job, onProgress = () => {}) {
  if (!job?.id) throw new Error("A Central não confirmou a criação do job.");
  let current = job;
  while (!["completed", "failed"].includes(current.status)) {
    onProgress(current);
    await new Promise((resolve) => setTimeout(resolve, 500));
    ({ job: current } = await requestJson(`/api/jobs/${encodeURIComponent(job.id)}`, { cache: "no-store" }));
  }
  onProgress(current);
  if (current.status === "failed") throw new Error(current.error || "A execução de TextOff falhou.");
  return current.results || [];
}
