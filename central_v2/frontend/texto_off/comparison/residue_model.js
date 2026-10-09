export const RESIDUE_TYPES = [
  ["residuo_transparencia", "Resíduo de transparência"],
  ["residuo_degrade", "Resíduo do degradê"],
  ["residuo_gradiente", "Resíduo do gradiente"],
  ["balao_estilizado", "Balão estilizado"],
  ["fragmento_balao", "Fragmento de balão"],
  ["texto_residual", "Texto residual"],
  ["outro", "Outro defeito"],
];

export function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

export function normalizedPoint(event, rect) {
  return {
    x: rect.width ? clamp((event.clientX - rect.left) / rect.width, 0, 1) : 0,
    y: rect.height ? clamp((event.clientY - rect.top) / rect.height, 0, 1) : 0,
  };
}

export function normalizedBox(start, end) {
  const left = Math.min(start.x, end.x), top = Math.min(start.y, end.y);
  return { left, top, width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y) };
}

export function renderedBoxSize(box, rect) {
  return { width: box.width * rect.width, height: box.height * rect.height };
}

export function createPageDraft() {
  return { occurrences: [], confirmedOccurrences: [], loaded: false, persisted: false,
    decisionPersisted: false, sourceSnapshot: null, sourceStatus: null, staleSources: [],
    dirty: false, loadState: "idle", saveState: "idle" };
}

export function createPageDraftStore() {
  const pages = new Map();
  return {
    get(key) {
      if (!pages.has(key)) pages.set(key, createPageDraft());
      return pages.get(key);
    },
    peek(key) { return pages.get(key); },
    entries() { return pages.entries(); },
    clear() { pages.clear(); },
  };
}

export function addOccurrence(draft, box, id) {
  const occurrence = { id, type: "residuo_transparencia", note: null, box,
    origin: "MANUAL", origins: ["MANUAL"] };
  draft.occurrences.push(occurrence);
  draft.dirty = true;
  return occurrence;
}

export function removeFromDraft(draft, id) {
  const index = draft.occurrences.findIndex((item) => item.id === id);
  if (index < 0) return false;
  draft.occurrences.splice(index, 1);
  draft.dirty = true;
  return true;
}

export function updateOccurrenceType(occurrence, type) {
  occurrence.type = type;
  if (type !== "outro") occurrence.note = null;
}

export function updateOccurrenceNote(occurrence, note) {
  occurrence.note = note || null;
}

export function cloneOccurrences(occurrences) {
  return occurrences.map((item) => ({ ...item, box: { ...item.box },
    origins: [...(item.origins || [item.origin || "MANUAL"])],
    source_references: (item.source_references || []).map((source) => ({ ...source })),
    source_classifications: (item.source_classifications || []).map((source) => ({ ...source })) }));
}

export function occurrencesEqual(left, right) {
  return JSON.stringify(canonicalOccurrences(left)) === JSON.stringify(canonicalOccurrences(right));
}

function canonicalOccurrences(occurrences) {
  return occurrences.map((item) => ({
    id: String(item.id), type: item.type, note: item.note || null,
    origin: item.origin || "MANUAL",
    origins: [...(item.origins || [item.origin || "MANUAL"])].sort(),
    source_references: item.source_references || [],
    source_classification: item.source_classification || null,
    source_classifications: item.source_classifications || [],
    candidate: item.candidate ?? null,
    box: {
      left: Number(item.box.left), top: Number(item.box.top),
      width: Number(item.box.width), height: Number(item.box.height),
    },
  })).sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
}
