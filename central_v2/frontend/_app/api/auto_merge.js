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

export async function fetchLevel2(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  const response = await fetch(`/api/auto-merge/level2?${query}`, { signal });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}

export async function fetchLevel3(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  const response = await fetch(`/api/auto-merge/level3?${query}`, { signal });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}

export async function fetchLevel4(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  const response = await fetch(`/api/auto-merge/level4?${query}`, { signal });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}

export async function fetchLevel5(provider, manga, signal) {
  const query = new URLSearchParams({ provider, manga });
  const response = await fetch(`/api/auto-merge/level5?${query}`, { signal });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Falha HTTP ${response.status}`);
  return payload;
}

export async function submitLevel1(provider, manga, chapters) {
  return requestJson("/api/auto-merge/level1/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export async function submitLevel2(provider, manga, chapters) {
  return requestJson("/api/auto-merge/level2/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export async function submitLevel3(provider, manga, chapters) {
  return requestJson("/api/auto-merge/level3/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export async function submitLevel4(provider, manga, chapters) {
  return requestJson("/api/auto-merge/level4/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export async function submitLevel5(provider, manga, chapters) {
  return requestJson("/api/auto-merge/level5/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export async function openAutoMergeFolder(provider, manga, chapter, level) {
  return requestJson("/api/auto-merge/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ provider, manga, chapter, level }),
  });
}

export async function fetchJob(jobId, signal) {
  const result = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}`, { signal, cache: "no-store" });
  if (["completed", "failed"].includes(result.job?.status)) invalidateCleanerOverview();
  return result;
}

async function requestJson(url, options) {
  try {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Falha na solicitação (${response.status}).`);
    return payload;
  } finally {
    if (url.endsWith("/execute")) {
      const { provider, manga } = JSON.parse(options.body);
      invalidateCleanerOverview(provider, manga);
    }
  }
}
import { invalidateCleanerOverview } from "/_app/state/cleaner_revision.js";
