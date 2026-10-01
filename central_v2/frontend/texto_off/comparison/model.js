import { paginationConfig } from "/_shared/pagination/config.js";

export const COMPARISON_PAGE_SIZE = paginationConfig.inspectionPageSize;
export const INITIAL_ZOOM = 40;
export const MIN_ZOOM = 20;
export const MAX_ZOOM = 200;
export const ZOOM_STEP = 10;
export const SIDE_BY_SIDE_GAP = 18;
export const COMPARISON_MODES = Object.freeze(["split", "side"]);

export function filterComparisonPages(pages, query) {
  const term = String(query || "").trim().toLocaleLowerCase("pt-BR");
  return pages.map((page, originalIndex) => ({ page, originalIndex }))
    .filter(({ page }) => page.name.toLocaleLowerCase("pt-BR").includes(term));
}

export function pageComparisonItems(items, page) {
  const pages = Math.max(1, Math.ceil(items.length / COMPARISON_PAGE_SIZE));
  const current = Math.max(1, Math.min(pages, Math.floor(Number(page) || 1)));
  const offset = (current - 1) * COMPARISON_PAGE_SIZE;
  return { rows: items.slice(offset, offset + COMPARISON_PAGE_SIZE), page: current,
    pages, total: items.length, start: items.length ? offset + 1 : 0,
    end: Math.min(offset + COMPARISON_PAGE_SIZE, items.length) };
}

export function clampZoom(current, action) {
  if (action === "one") return 100;
  const delta = action === "+" ? ZOOM_STEP : -ZOOM_STEP;
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(current) + delta));
}
