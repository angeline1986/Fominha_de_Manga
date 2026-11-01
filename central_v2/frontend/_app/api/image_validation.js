const root = "/api/images/validation";

async function json(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}.`);
  return payload;
}

export function fetchImageValidation(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  return json(`${root}?${query}`, { signal, cache: "no-store" });
}

export function validationImageUrl(provider, manga, chapter, file, variant) {
  const query = new URLSearchParams({ provider, manga, chapter, file, variant,
    v: String(Date.now()) });
  return `${root}/image?${query}`;
}

export function startImageAnalysis(provider, manga, chapters) {
  return json(`${root}/analyze`, { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, manga, chapters, tolerance: 3 }) });
}

export function applyImageCorrection(provider, manga, chapter, file) {
  return json(`${root}/apply`, { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, manga, chapter, file }) });
}

export function fetchValidationJob(id, signal) {
  return json(`/api/jobs/${encodeURIComponent(id)}`, { signal, cache: "no-store" });
}
