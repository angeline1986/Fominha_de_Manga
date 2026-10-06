import { fetchResidueOccurrences, saveResidueOccurrences } from "/_app/api/residue_occurrences.js";
import { RESIDUE_TYPES, addOccurrence, cloneOccurrences, createPageDraftStore,
  occurrencesEqual, removeFromDraft, updateOccurrenceNote, updateOccurrenceType } from "/texto_off/comparison/residue_model.js";

const TYPES = new Set(RESIDUE_TYPES.map(([value]) => value));

export function createResidueCatalogState(context, onChange = () => {},
  onPersistedCount = () => {}, onDraftState = () => {}) {
  const isCheck = context.scope === "check";
  const drafts = createPageDraftStore(), getControllers = new Set();
  let currentPage = "", revision = 0, disposed = false, saveController = null;
  const current = () => drafts.get(currentPage);
  const notify = (page = currentPage) => {
    const draft = drafts.get(page);
    const validCount = draft.occurrences.filter((item) => isValidOccurrence(item, isCheck)).length;
    onDraftState(page, draft.loaded ? validCount : null, draft.dirty);
    onChange();
  };

  function setPage(page) {
    currentPage = String(page || "");
    const draft = current();
    getControllers.forEach((controller) => controller.abort()); getControllers.clear();
    const requestRevision = ++revision;
    if (draft.loaded) { notify(); return Promise.resolve(); }
    const controller = new AbortController(); getControllers.add(controller);
    draft.loadState = "loading"; notify();
    return fetchResidueOccurrences({ ...context, page: currentPage }, controller.signal).then((result) => {
      if (disposed || requestRevision !== revision) return;
      draft.confirmedOccurrences = (result.occurrences || []).map(fromManifest);
      draft.occurrences = cloneOccurrences(draft.confirmedOccurrences);
      draft.persisted = result.decision_persisted ?? (draft.confirmedOccurrences.length > 0);
      draft.decisionPersisted = Boolean(result.decision_persisted);
      draft.sourceSnapshot = result.source_snapshot || null;
      draft.sourceStatus = result.source_status || null;
      draft.staleSources = result.stale_sources || [];
      draft.loaded = true; draft.dirty = false; draft.loadState = "ready"; draft.error = null;
      notify(currentPage);
    }).catch((error) => {
      if (disposed || error.name === "AbortError" || requestRevision !== revision) return;
      draft.loadState = "error"; draft.error = error.message; notify(currentPage);
    }).finally(() => getControllers.delete(controller));
  }

  function add(box, id) { const item = addOccurrence(current(), box, id); changed(current()); notify(); return item; }
  function remove(id) {
    const draft = current();
    if (!removeFromDraft(draft, id)) return false;
    changed(draft); notify(); return true;
  }
  function setType(id, type) {
    const draft = current(), item = draft.occurrences.find((row) => row.id === id);
    if (item && TYPES.has(type)) { updateOccurrenceType(item, type); changed(draft); notify(); }
  }
  function setNote(id, note) {
    const draft = current(), item = draft.occurrences.find((row) => row.id === id);
    if (!item || item.type !== "outro") return false;
    updateOccurrenceNote(item, note); changed(draft); notify(); return true;
  }
  function dirtyPages() {
    return Array.from(drafts.entries(), ([page, draft]) => ({ page, draft }))
      .filter(({ draft }) => draft.dirty)
      .sort((a, b) => a.page < b.page ? -1 : a.page > b.page ? 1 : 0);
  }
  function canSaveChapter() {
    const rows = dirtyPages();
    const initialCheckSave = isCheck && current().loaded && !current().decisionPersisted;
    const candidates = rows.length ? rows : initialCheckSave ? [{ page: currentPage, draft: current() }] : [];
    return !saveController && candidates.length > 0 && candidates.every(({ draft }) =>
      draft.loaded && draft.occurrences.every((item) => isValidOccurrence(item, isCheck)));
  }
  async function saveChapter() {
    if (!canSaveChapter()) return { ok: false, error: "Não há alterações válidas para catalogar." };
    const dirty = dirtyPages();
    const saveRows = dirty.length ? dirty : [{ page: currentPage, draft: current() }];
    const submitted = saveRows.map(({ page, draft }) => ({
      page, occurrences: draft.occurrences.map(toPayload), snapshot: cloneOccurrences(draft.occurrences),
      sourceSnapshot: draft.sourceSnapshot,
    }));
    saveController = new AbortController();
    submitted.forEach(({ page }) => { drafts.get(page).saveState = "saving"; });
    onChange();
    try {
      const result = await saveResidueOccurrences({ ...context,
        source_snapshot: submitted[0].sourceSnapshot || current().sourceSnapshot,
        pages: submitted.map(({ page, occurrences }) => ({ page, occurrences })),
      }, saveController.signal);
      if (disposed) return { ok: false, cancelled: true };
      if (!matchesBatch(result, submitted)) throw new Error("Resposta do catálogo incompleta.");
      confirm(submitted.map((row) => ({ page: row.page, occurrences: row.snapshot })));
      return { ok: true, result, savedPages: submitted.length };
    } catch (error) {
      if (disposed || error.name === "AbortError") return { ok: false, cancelled: true };
      if (error.status == null || error.status >= 500) {
        const reconciled = await reconcile(submitted, saveController.signal);
        if (reconciled) {
          confirm(reconciled); return { ok: true, reconciled: true, savedPages: submitted.length };
        }
      }
      submitted.forEach(({ page }) => {
        const draft = drafts.get(page); draft.saveState = "error"; draft.error = error.message;
      });
      onChange(); submitted.forEach(({ page }) => notify(page));
      return { ok: false, error: error.message };
    } finally { saveController = null; onChange(); }
  }

  async function reconcile(submitted, signal) {
    try {
      const persisted = await Promise.all(submitted.map(async ({ page, snapshot }) => {
        const result = await fetchResidueOccurrences({ ...context, page }, signal);
        const occurrences = (result.occurrences || []).map(fromManifest);
        return occurrencesEqual(occurrences, snapshot) ? { page, occurrences } : null;
      }));
      return persisted.every(Boolean) ? persisted : null;
    } catch { return null; }
  }
  function confirm(rows) {
    rows.forEach(({ page, occurrences }) => {
      const draft = drafts.get(page);
      draft.confirmedOccurrences = cloneOccurrences(occurrences);
      draft.persisted = isCheck ? true : occurrences.length > 0;
      if (isCheck) draft.decisionPersisted = true;
      draft.dirty = !occurrencesEqual(draft.occurrences, draft.confirmedOccurrences);
      draft.saveState = draft.dirty ? "idle" : "saved"; draft.error = null;
      onPersistedCount(page, occurrences.length); notify(page);
    });
  }
  function dispose() {
    disposed = true; revision++;
    getControllers.forEach((controller) => controller.abort()); getControllers.clear();
    saveController?.abort(); drafts.clear();
  }
  return { current, setPage, add, remove, setType, setNote, canSaveChapter,
    hasDirtyPages: () => dirtyPages().length > 0, dirtyPageCount: () => dirtyPages().length,
    draftOccurrenceCount: (page) => countDraftOccurrences(drafts.peek(page), isCheck),
    isSaving: () => Boolean(saveController), saveChapter, dispose };
}

function matchesBatch(result, submitted) {
  if (!Array.isArray(result?.pages) || result.pages.length !== submitted.length) return false;
  const pages = new Map(result.pages.map((item) => [item.page, item]));
  if (pages.size !== submitted.length) return false;
  return submitted.every(({ page, occurrences }) => {
    const saved = pages.get(page);
    return saved && saved.total_occurrences === occurrences.length
      && Array.isArray(saved.occurrences)
      && occurrencesEqual(saved.occurrences.map(fromManifest), occurrences.map(fromPayload));
  });
}
function fromPayload(item) {
  return { id: item.id, type: item.type, note: item.note,
    box: { ...item.box_normalized }, origin: item.origin || "MANUAL",
    origins: [...(item.origins || [item.origin || "MANUAL"])],
    source_references: (item.source_references || []).map((source) => ({ ...source })),
    source_classification: item.source_classification || null,
    source_classifications: (item.source_classifications || []).map((source) => ({ ...source })),
    candidate: item.candidate ?? null };
}
function fromManifest(item) {
  return { id: item.id, type: item.type ?? item.tipo ?? "", note: item.note ?? item.observacao ?? null,
    box: { ...(item.box || item.box_normalized) }, origin: item.origin || "MANUAL",
    origins: [...(item.origins || [item.origin || "MANUAL"])],
    source_references: (item.source_references || []).map((source) => ({ ...source })),
    source_classification: item.source_classification || null,
    source_classifications: (item.source_classifications || []).map((source) => ({ ...source })),
    candidate: item.candidate ?? null };
}
function toPayload(item, index) {
  return { id: item.id, number: index + 1, type: item.type, note: item.note,
    box_normalized: { ...item.box }, origin: item.origin || "MANUAL",
    origins: [...(item.origins || [item.origin || "MANUAL"])],
    source_references: (item.source_references || []).map((source) => ({ ...source })),
    source_classification: item.source_classification || null,
    source_classifications: (item.source_classifications || []).map((source) => ({ ...source })),
    candidate: item.candidate ?? null };
}
function changed(draft) {
  draft.dirty = !occurrencesEqual(draft.occurrences, draft.confirmedOccurrences);
  draft.error = null;
  if (draft.saveState !== "saving") draft.saveState = "idle";
}
function countDraftOccurrences(draft, isCheck) {
  return !draft?.loaded ? null : draft.occurrences.filter((item) => isValidOccurrence(item, isCheck)).length;
}
function isValidOccurrence(item, isCheck = false) {
  const box = item.box || {}, values = [box.left, box.top, box.width, box.height];
  const knownType = TYPES.has(item.type);
  const sourceUnclassified = isCheck && item.type === "" && item.origin !== "MANUAL"
    && (Boolean(item.source_classification) || typeof item.candidate === "boolean");
  return (knownType || sourceUnclassified) && values.every(Number.isFinite)
    && box.left >= 0 && box.top >= 0 && box.width > 0 && box.height > 0
    && box.left + box.width <= 1 && box.top + box.height <= 1
    && (item.type !== "outro" || Boolean(item.note?.trim()));
}
