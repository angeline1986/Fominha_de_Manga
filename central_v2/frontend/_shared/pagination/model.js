import { paginationConfig } from "/_shared/pagination/config.js";

export function createPagination() {
  let page = 1;
  let pages = 1;
  return {
    reset() { page = 1; },
    move(delta) { page = Math.max(1, Math.min(pages, page + delta)); },
    select(rows) {
      const size = paginationConfig.pageSize;
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
