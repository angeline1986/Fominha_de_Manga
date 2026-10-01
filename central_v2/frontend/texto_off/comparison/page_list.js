import { createPagination } from "/_shared/pagination/model.js";
import { COMPARISON_PAGE_SIZE, filterComparisonPages } from "/texto_off/comparison/model.js";

export function createPageList({ list, search, paginationRoot, onSelect, onPreview, onPreviewPosition }) {
  const pagination = createPagination(COMPARISON_PAGE_SIZE);
  function render(pages, selectedIndex) {
    const result = pagination.select(filterComparisonPages(pages, search.value));
    list.replaceChildren();
    for (const { page, originalIndex } of result.rows) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "comparison-page-item";
      button.classList.toggle("is-selected", originalIndex === selectedIndex);
      button.setAttribute("role", "option"); button.setAttribute("aria-selected", String(originalIndex === selectedIndex));
      button.textContent = page.name; button.addEventListener("click", () => onSelect(originalIndex));
      list.append(button);
    }
    drawPagination(result);
  }
  function drawPagination(result) {
    paginationRoot.replaceChildren();
    const range = document.createElement("span"); range.setAttribute("aria-live", "polite");
    range.textContent = `${result.start}–${result.end} de ${result.total}`;
    const controls = document.createElement("div"); controls.className = "comparison-page-controls";
    controls.append(pageButton("Página anterior da lista", "«", () => { pagination.move(-1); rerender(); }, result.page === 1));
    const current = document.createElement("span"); current.textContent = `${result.page} / ${result.pages}`;
    controls.append(current, pageButton("Próxima página da lista", "»", () => { pagination.move(1); rerender(); }, result.page === result.pages));
    paginationRoot.append(range, controls); onPreviewPosition();
  }
  function pageButton(label, text, action, disabled) {
    const button = document.createElement("button"); button.type = "button";
    button.className = "comparison-page-control"; button.setAttribute("aria-label", label);
    button.textContent = text; button.disabled = disabled; button.addEventListener("click", action); return button;
  }
  function rerender() { render(currentPages, currentSelected); }
  let currentPages = [], currentSelected = 0;
  function renderCurrent() { render(currentPages, currentSelected); }
  function onSearch() { pagination.reset(); renderCurrent(); }
  function onPointerOver(event) {
    const item = event.target.closest(".comparison-page-item");
    if (item && !item.contains(event.relatedTarget)) onPreview(item.textContent, item);
  }
  function onPointerOut(event) {
    const item = event.target.closest(".comparison-page-item");
    if (item && !item.contains(event.relatedTarget)) onPreview(null);
  }
  list.addEventListener("pointerover", onPointerOver); list.addEventListener("pointerout", onPointerOut);
  search.addEventListener("input", onSearch);
  return {
    render(pages, selectedIndex) { currentPages = pages; currentSelected = selectedIndex; renderCurrent(); },
    dispose() {
      list.removeEventListener("pointerover", onPointerOver); list.removeEventListener("pointerout", onPointerOut);
      search.removeEventListener("input", onSearch);
    },
  };
}
