import { fetchResidueOccurrences } from "/_app/api/residue_occurrences.js";

export async function loadCheckTypes(rows, context, signal, isDisposed, onTypes) {
  let cursor = 0;
  async function worker() {
    while (!isDisposed() && cursor < rows.length) {
      const page = rows[cursor++];
      try {
        const result = await fetchResidueOccurrences({ ...context, page: page.name }, signal);
        if (isDisposed()) return;
        onTypes(page.name, (result.occurrences || []).map((item) => item.type ?? item.tipo ?? ""));
      } catch (error) {
        if (error.name !== "AbortError") console.warn("[Check] Falha ao consultar tipos:", page.name, error);
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(3, rows.length) }, worker));
}
