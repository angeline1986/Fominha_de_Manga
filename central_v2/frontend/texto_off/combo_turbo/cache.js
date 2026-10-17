import { fetchChapterOverview } from "/texto_off/combo_turbo/api.js";
import { preflightAll } from "/texto_off/combo_turbo/planning.js";
import { getContext, subscribeContext } from "/_app/state/context.js";
import { subscribeCleanerInvalidation } from "/_app/state/cleaner_revision.js";

const entries = new Map();
const uiState = new Map();
const invalidatedJobs = new Set();
const keyFor = (provider, manga) => JSON.stringify([provider, manga]);
const chapterList = (payload) => (payload.chapters || []).map((row) => String(row.chapter));
const chapterRevision = (payload) => JSON.stringify(payload.chapters || []);
let contextKey = keyFor(getContext().provider, getContext().manga);

subscribeContext(() => {
  const context = getContext();
  const nextKey = keyFor(context.provider, context.manga);
  if (nextKey !== contextKey) entries.delete(contextKey);
  contextKey = nextKey;
});

subscribeCleanerInvalidation((provider, manga) => {
  if (!provider || !manga) { entries.clear(); return; }
  entries.delete(keyFor(provider, manga));
});

export function savedComboUiState(provider, manga) {
  return uiState.get(keyFor(provider, manga)) || {};
}

export function saveComboUiState(provider, manga, state) {
  uiState.set(keyFor(provider, manga), { ...savedComboUiState(provider, manga), ...state });
}

export function markComboResultInvalidated(jobId) {
  if (invalidatedJobs.has(jobId)) return false;
  invalidatedJobs.add(jobId);
  return true;
}

export function loadComboRows(provider, manga, { refresh = false, onBatch } = {}) {
  const key = keyFor(provider, manga);
  let entry = entries.get(key);
  if (entry?.promise) return entry.promise;
  // Local revisions invalidate immediately; this projection check catches remote Check/source changes.
  if (entry?.rows && !refresh && Date.now() - entry.verifiedAt < 30000) {
    return Promise.resolve(entry.rows);
  }
  if (entry?.rows && !refresh) {
    entry.promise = verifyCachedRows(provider, manga, key, entry, onBatch);
    return entry.promise;
  }
  entry = { rows: null, promise: null, verifiedAt: 0 };
  entries.set(key, entry);
  entry.promise = fetchAndPlan(provider, manga, key, entry, onBatch);
  return entry.promise;
}

async function verifyCachedRows(provider, manga, key, entry, onBatch) {
  try {
    const overview = await fetchChapterOverview(provider, manga);
    if (chapterRevision(overview) === entry.revision) {
      entry.verifiedAt = Date.now();
      return entry.rows;
    }
    entry.rows = null;
    entry.promise = fetchAndPlan(provider, manga, key, entry, onBatch, overview);
    return await entry.promise;
  } finally { entry.promise = null; }
}

async function fetchAndPlan(provider, manga, key, entry, onBatch, knownOverview = null) {
  try {
    const overview = knownOverview || await fetchChapterOverview(provider, manga);
    const chapters = chapterList(overview);
    const rows = await preflightAll(provider, manga, chapters, onBatch, () => true);
    if (entries.get(key) === entry) {
      entry.rows = rows;
      entry.chapters = chapters;
      entry.revision = chapterRevision(overview);
      entry.verifiedAt = Date.now();
    }
    return rows;
  } finally { entry.promise = null; }
}
