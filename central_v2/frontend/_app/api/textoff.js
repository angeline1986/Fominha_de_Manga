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

export async function startMergedSpecialTextoff(provider, manga, chapters, level) {
  return requestJson(`/api/textoff/merged/level${level}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export async function fetchManualSpecial(provider, manga, level, signal) {
  const query = new URLSearchParams({ provider, manga });
  return requestJson(`/api/textoff/special/level${level}?${query}`, { signal, cache: "no-store" });
}

export function manualSpecialImageUrl(provider, manga, chapter, filename) {
  const query = new URLSearchParams({ provider, manga, chapter, file: filename });
  return `/api/textoff/special/image?${query}`;
}

export function mergedLevel3ImageUrl(provider, manga, chapter, filename) {
  const query = new URLSearchParams({ provider, manga, chapter, file: filename });
  return `/api/textoff/merged/level3/image?${query}`;
}

export function manualSpecialResultUrl(runId) {
  return `/api/textoff/special/result?${new URLSearchParams({ run_id: runId })}`;
}

export async function startManualSpecial(provider, manga, level, chapter, filename, selections) {
  return requestJson(`/api/textoff/special/level${level}/execute`, {
    method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapter, filename, selections }),
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

export async function fetchBubbleSommelier(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  return requestJson(`/api/textoff/sommelier?${query}`, { signal, cache: "no-store" });
}

export async function startBubbleSommelier(provider, manga, chapters) {
  return requestJson("/api/textoff/sommelier/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

