import { fetchResidueOccurrences } from "/_app/api/residue_occurrences.js";

const SOLID_TYPE = "residuo_balao_solido_branco";

export function createSolidAreaLoader(getContext, getRows, onChange) {
  const cache = new Map(), controllers = new Map();
  let contextKey = "", disposed = false;
  const key = (chapter, page) => `${chapter}\u0000${page}`;

  function beginLoad(context) {
    const next = `${context.provider}\u0000${context.manga}`;
    if (contextKey && contextKey !== next) cache.clear();
    contextKey = next;
    controllers.forEach((controller) => controller.abort());
    controllers.clear();
  }

  function attach(rows) {
    rows.forEach((chapter) => chapter.pages.forEach((page) => {
      const saved = cache.get(key(chapter.chapter, page.name));
      Object.assign(page, saved || { areas: [], areasState: "idle" });
    }));
  }

  async function load(pageRow) {
    const current = findPage(getRows(), pageRow.chapter, pageRow.name);
    const target = current || pageRow;
    if (disposed || target.areasState === "loading" || target.areasState === "ready") return;
    const { provider, manga } = getContext(), id = key(pageRow.chapter, pageRow.name);
    const controller = new AbortController(); controllers.set(id, controller);
    target.areasState = "loading"; target.areasError = ""; onChange();
    try {
      const result = await fetchResidueOccurrences({ provider, manga, chapter: pageRow.chapter,
        page: pageRow.name, step: "1", scope: "check" }, controller.signal);
      if (disposed || controller.signal.aborted) return;
      const areas = (result.occurrences || []).filter((row) =>
        (row.tipo ?? row.type) === SOLID_TYPE).map((row) => ({
          id: row.id, number: row.numero, label: row.label || row.tipo || row.type || "",
        }));
      cache.set(id, { areas, areasState: "ready" });
      const current = findPage(getRows(), pageRow.chapter, pageRow.name);
      if (current) Object.assign(current, cache.get(id));
      onChange();
    } catch (error) {
      if (disposed || error.name === "AbortError") return;
      const current = findPage(getRows(), pageRow.chapter, pageRow.name);
      if (current) { current.areasState = "error"; current.areasError = error.message; }
      onChange();
    } finally {
      if (controllers.get(id) === controller) controllers.delete(id);
    }
  }

  function dispose() {
    disposed = true;
    controllers.forEach((controller) => controller.abort()); controllers.clear(); cache.clear();
  }
  return { beginLoad, attach, load, dispose };
}

function findPage(rows, chapterName, pageName) {
  return rows.find((row) => row.chapter === chapterName)?.pages
    .find((row) => row.name === pageName);
}
