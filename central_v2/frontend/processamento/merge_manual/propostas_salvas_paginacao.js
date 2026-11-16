import { paginationConfig } from "/_shared/pagination/config.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { escapeHtml } from "/_shared/dom/sanitize.js";

export function createSavedPagePagination(onMove) {
  const pagination = createPagination(paginationConfig.inspectionPageSize);

  function render(list, controls, pages, selected) {
    const view = pagination.select(pages);
    list.innerHTML = view.rows.map((name) => `<button type="button" class="saved-review-page ${name === selected ? "is-selected" : ""}" data-page-name="${escapeHtml(name)}">${escapeHtml(name)}</button>`).join("");
    controls.replaceChildren(createPaginationControls(view, (delta) => {
      pagination.move(delta);
      onMove();
    }, { hideEmptyActions: true }));
  }

  function show(pageName, pages) {
    const index = pages.indexOf(pageName);
    pagination.reset();
    let view = pagination.select(pages);
    while (index >= view.end && view.page < view.pages) {
      pagination.move(1);
      view = pagination.select(pages);
    }
  }

  return { render, reset: () => pagination.reset(), show };
}
