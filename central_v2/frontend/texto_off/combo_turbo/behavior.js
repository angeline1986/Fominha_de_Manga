import { comboState, MAX_CHAPTERS, TERMINAL } from "/texto_off/combo_turbo/model.js";

export function isSelectable(row) { return comboState(row) === "PLANNED"; }

export function reconcileSelection(selected, rows) {
  const eligible = new Set(rows.filter(isSelectable).map((row) => String(row.chapter)));
  const next = new Set([...selected].filter((chapter) => eligible.has(String(chapter))));
  return { selected: next, changed: next.size !== selected.size };
}

export function selectChapter(selected, rows, chapter, checked) {
  if (!checked) {
    const next = new Set(selected); next.delete(chapter);
    return { selected: next, changed: next.size !== selected.size };
  }
  if (!rows.some((row) => String(row.chapter) === String(chapter) && isSelectable(row))) {
    return { selected, changed: false, reason: "Capítulo sem elegibilidade para execução." };
  }
  if (!selected.has(chapter) && selected.size >= MAX_CHAPTERS) {
    return { selected, changed: false, reason: `O limite é ${MAX_CHAPTERS} capítulos por execução.` };
  }
  const next = new Set(selected); next.add(chapter);
  return { selected: next, changed: next.size !== selected.size };
}

export function selectChapters(selected, rows, chapters, checked) {
  const eligible = new Set(rows.filter(isSelectable).map((row) => String(row.chapter)));
  const next = new Set(selected);
  chapters.forEach((chapter) => {
    if (!checked || eligible.has(String(chapter))) checked ? next.add(chapter) : next.delete(chapter);
  });
  if (next.size > MAX_CHAPTERS) return { selected, changed: false,
    reason: `A seleção foi limitada a ${MAX_CHAPTERS} capítulos.` };
  return { selected: next, changed: next.size !== selected.size };
}

export function selectEligible(rows) {
  return new Set(rows.filter(isSelectable).slice(0, MAX_CHAPTERS).map((row) => String(row.chapter)));
}

export function canExecute(state) {
  return !state.busy && !state.loading && !state.conflict && state.planValid
    && state.selected?.size > 0;
}

export function isConflict(error) { return error?.status === 409; }
export function resultVisible(job, result) {
  return Boolean(result) && TERMINAL.has(String(job?.status || "").toLowerCase());
}

export function progressPresentation(job = {}) {
  const progress = job.progress && typeof job.progress === "object" ? job.progress : job;
  const raw = progress.percent;
  const validPercent = Number.isFinite(raw) && raw >= 0 && raw <= 100;
  const terminal = TERMINAL.has(String(job.status || "").toLowerCase());
  const percent = validPercent ? (!terminal && raw === 100 ? 99 : raw) : null;
  const completed = progress.completed ?? job.pages_completed;
  const total = progress.total ?? job.pages_total;
  const hasCounts = Number.isFinite(completed) && Number.isFinite(total) && (completed > 0 || total > 0);
  const count = hasCounts ? `${completed} de ${total} páginas` : "";
  const text = percent === null ? count : `${percent}%${count ? ` · ${count}` : ""}`;
  return { percent, text, terminal };
}
