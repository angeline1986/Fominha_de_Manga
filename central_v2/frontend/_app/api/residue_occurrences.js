async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.error || `Falha HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export async function fetchResidueOccurrences(context, signal) {
  const query = new URLSearchParams(context);
  return requestJson(`/api/textoff/residue-occurrences?${query}`, { signal, cache: "no-store" });
}

export async function saveResidueOccurrences(payload, signal) {
  return requestJson("/api/textoff/residue-occurrences", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    signal,
    body: JSON.stringify(payload),
  });
}
