import { planCombo } from "/texto_off/combo_turbo/api.js";
import { MAX_CHAPTERS } from "/texto_off/combo_turbo/model.js";

export async function preflightAll(provider, manga, chapters, onBatch, isCurrent) {
  const rows = new Map(chapters.map((chapter) => [chapter, { chapter, status: "UNKNOWN", pages: [] }]));
  for (let offset = 0; offset < chapters.length; offset += MAX_CHAPTERS) {
    const batch = chapters.slice(offset, offset + MAX_CHAPTERS);
    onBatch(offset + batch.length, chapters.length);
    try {
      const response = await planCombo(provider, manga, batch);
      (response.plan?.chapters || []).forEach((row) => rows.set(String(row.chapter), row));
    } catch (error) {
      batch.forEach((chapter) => rows.set(chapter, { chapter, status: "BLOCKED",
        pages: [], reasons: [error.reason || "PLAN_FAILED"] }));
    }
    if (!isCurrent()) return [...rows.values()];
  }
  return [...rows.values()];
}
