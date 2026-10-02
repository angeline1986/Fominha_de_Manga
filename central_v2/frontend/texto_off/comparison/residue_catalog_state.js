import { fetchResidueOccurrences, saveResidueOccurrences } from "/_app/api/residue_occurrences.js";
import { RESIDUE_TYPES, addOccurrence, createPageDraftStore, removeFromDraft,
  updateOccurrenceNote, updateOccurrenceType } from "/texto_off/comparison/residue_model.js";

const TYPES = new Set(RESIDUE_TYPES.map(([value]) => value));

export function createResidueCatalogState(context, onChange = () => {}) {
  const drafts = createPageDraftStore(), getControllers = new Set(), saveControllers = new Set();
  let currentPage = "", revision = 0, disposed = false;
  const current = () => drafts.get(currentPage);

  function setPage(page) {
    currentPage = String(page || "");
    const draft = current();
    getControllers.forEach((controller) => controller.abort()); getControllers.clear();
    const requestRevision = ++revision;
    if (draft.loaded) { onChange(); return Promise.resolve(); }
    const controller = new AbortController(); getControllers.add(controller);
    draft.loadState = "loading"; onChange();
    return fetchResidueOccurrences({ ...context, page: currentPage }, controller.signal).then((result) => {
      if (disposed || requestRevision !== revision) return;
      draft.occurrences = (result.occurrences || []).map(fromManifest);
      draft.persisted = Boolean(result.cataloged); draft.loaded = true;
      draft.loadState = "ready"; draft.error = null; onChange();
    }).catch((error) => {
      if (disposed || error.name === "AbortError" || requestRevision !== revision) return;
      draft.loadState = "error"; draft.error = error.message; onChange();
    }).finally(() => getControllers.delete(controller));
  }

  function add(box, id) { const item = addOccurrence(current(), box, id); changed(current()); onChange(); return item; }
  function remove(id) { const draft = current(), changedDraft = removeFromDraft(draft, id); if (changedDraft) { changed(draft); onChange(); } return changedDraft; }
  function setType(id, type) {
    const draft = current(), item = draft.occurrences.find((row) => row.id === id);
    if (item && TYPES.has(type)) { updateOccurrenceType(item, type); changed(draft); onChange(); }
  }
  function setNote(id, note) {
    const draft = current(), item = draft.occurrences.find((row) => row.id === id);
    if (item?.type === "outro") { updateOccurrenceNote(item, note); changed(draft); return true; }
    return false;
  }
  function canSave() {
    const draft = current();
    return draft.saveState !== "saving" && draft.occurrences.length > 0
      && draft.occurrences.every(isValidOccurrence);
  }
  async function save(metrics) {
    if (!canSave()) return { ok: false, error: "Adicione uma ocorrência válida antes de catalogar." };
    const draft = current(), page = currentPage, controller = new AbortController();
    saveControllers.add(controller); draft.saveState = "saving"; onChange();
    const occurrencePayload = draft.occurrences.map((item, index) => ({
      id: item.id, number: index + 1, type: item.type, note: item.note,
      box_normalized: { ...item.box },
    }));
    const submittedState = JSON.stringify(occurrencePayload);
    const payload = {
      ...context, page, occurrences: occurrencePayload,
      image: { naturalWidth: metrics.naturalWidth, naturalHeight: metrics.naturalHeight, source: "after" },
    };
    try {
      const result = await saveResidueOccurrences(payload, controller.signal);
      if (disposed) return { ok: false, cancelled: true };
      draft.persisted = true;
      draft.dirty = JSON.stringify(draft.occurrences.map(toPayload)) !== submittedState;
      draft.saveState = draft.dirty ? "idle" : "saved"; draft.error = null;
      onChange(); return { ok: true, result };
    } catch (error) {
      if (!disposed) { draft.saveState = "error"; draft.error = error.message; onChange(); }
      return disposed ? { ok: false, cancelled: true } : { ok: false, error: error.message };
    } finally { saveControllers.delete(controller); }
  }
  function dispose() {
    disposed = true; revision++;
    getControllers.forEach((controller) => controller.abort());
    saveControllers.forEach((controller) => controller.abort());
    getControllers.clear(); saveControllers.clear(); drafts.clear();
  }
  return { current, setPage, add, remove, setType, setNote, canSave, save, dispose };
}

function fromManifest(item) {
  return { id: item.id, type: item.tipo, note: item.observacao,
    box: { ...item.box_normalized } };
}

function toPayload(item, index) {
  return { id: item.id, number: index + 1, type: item.type, note: item.note,
    box_normalized: { ...item.box } };
}

function changed(draft) {
  draft.dirty = true; draft.error = null;
  if (draft.saveState !== "saving") draft.saveState = "idle";
}

function isValidOccurrence(item) {
  const box = item.box || {};
  const values = [box.left, box.top, box.width, box.height];
  return TYPES.has(item.type) && values.every((value) => Number.isFinite(value))
    && box.left >= 0 && box.top >= 0 && box.width > 0 && box.height > 0
    && box.left + box.width <= 1 && box.top + box.height <= 1
    && (item.type !== "outro" || Boolean(item.note?.trim()));
}
