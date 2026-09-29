import { paginationConfig } from "/_shared/pagination/config.js";

export function createPagination(pageSize = paginationConfig.pageSize) {
  let page = 1;
  let pages = 1;
  const size = Math.max(1, Math.floor(Number(pageSize) || paginationConfig.pageSize));
  return {
    reset() { page = 1; },
    move(delta) { page = Math.max(1, Math.min(pages, page + delta)); },
    select(rows) {
      pages = Math.max(1, Math.ceil(rows.length / size));
      page = Math.min(page, pages);
      const offset = (page - 1) * size;
      return {
        rows: rows.slice(offset, offset + size),
        page, pages, total: rows.length,
        start: rows.length ? offset + 1 : 0,
        end: Math.min(offset + size, rows.length),
      };
    },
  };
}
