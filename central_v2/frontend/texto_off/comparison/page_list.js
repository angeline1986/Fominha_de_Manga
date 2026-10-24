import { createPagination } from "/_shared/pagination/model.js";
import { COMPARISON_PAGE_SIZE, filterComparisonPages } from "/texto_off/comparison/model.js";
import { checkColor } from "/texto_off/comparison/check_palette.js";

export function createPageList({ list, search, paginationRoot, onSelect, onPreview, onPreviewPosition,
  getDraftOccurrenceCount = () => null, getOccurrenceTypes = () => null }) {
  const pagination = createPagination(COMPARISON_PAGE_SIZE);
  function render(pages, selectedIndex) {
    const result = pagination.select(filterComparisonPages(pages, search?.value || ""));
    list.replaceChildren();
    for (const { page, originalIndex } of result.rows) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "comparison-page-item";
      button.dataset.pageName = page.name;
      button.classList.toggle("is-selected", originalIndex === selectedIndex);
      button.setAttribute("role", "option"); button.setAttribute("aria-selected", String(originalIndex === selectedIndex));
      button.textContent = page.name;
      applyOccurrenceIndicator(button, getDraftOccurrenceCount(page.name), page.residue_occurrence_count);
      applyTypeIndicators(button, getOccurrenceTypes(page.name));
      button.addEventListener("click", () => onSelect(originalIndex));
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
  function setOccurrenceCount(pageName, count) {
    const page = currentPages.find((item) => item.name === pageName);
    if (page) page.residue_occurrence_count = count;
    const button = Array.from(list.querySelectorAll("[data-page-name]"))
      .find((item) => item.dataset.pageName === pageName);
    if (button) {
      applyOccurrenceIndicator(button, getDraftOccurrenceCount(pageName), count);
      applyTypeIndicators(button, getOccurrenceTypes(pageName));
    }
  }
  function setDraftOccurrenceCount(pageName, count) {
    const page = currentPages.find((item) => item.name === pageName);
    if (!page) return;
    const button = Array.from(list.querySelectorAll("[data-page-name]"))
      .find((item) => item.dataset.pageName === pageName);
    if (button) {
      applyOccurrenceIndicator(button, count, page.residue_occurrence_count);
      applyTypeIndicators(button, getOccurrenceTypes(pageName));
    }
  }
  function onPointerOver(event) {
    const item = event.target.closest(".comparison-page-item");
    if (item && !item.contains(event.relatedTarget)) onPreview(item.textContent, item);
  }
  function onPointerOut(event) {
    const item = event.target.closest(".comparison-page-item");
    if (item && !item.contains(event.relatedTarget)) onPreview(null);
  }
  list.addEventListener("pointerover", onPointerOver); list.addEventListener("pointerout", onPointerOut);
  search?.addEventListener("input", onSearch);
  function setOccurrenceTypes(pageName) {
    const button = [...list.querySelectorAll("[data-page-name]")]
      .find((item) => item.dataset.pageName === pageName);
    if (button) applyTypeIndicators(button, getOccurrenceTypes(pageName));
  }
  return {
    render(pages, selectedIndex) { currentPages = pages; currentSelected = selectedIndex; renderCurrent(); },
    setOccurrenceCount, setDraftOccurrenceCount, setOccurrenceTypes,
    dispose() {
      list.removeEventListener("pointerover", onPointerOver); list.removeEventListener("pointerout", onPointerOut);
      search?.removeEventListener("input", onSearch);
    },
  };
}

function applyOccurrenceIndicator(button, currentCount, persistedCount) {
  const count = currentCount == null ? persistedCount : currentCount;
  const hasOccurrences = Number(count) > 0;
  button.dataset.hasResidueOccurrences = String(hasOccurrences);
  if (hasOccurrences) button.title = "Possui ocorrência no estado atual da revisão";
  else button.removeAttribute("title");
}

// Exclusivo do Check; outras telas mantêm seu indicador de existência.
const CHECK_DOTS = [
  ["residuo_transparencia", "Transparente"],
  ["balao_transparente", "Transparente"],
  ["residuo_degrade", "Degradê"],
  ["residuo_gradiente", "Gradiente"],
  ["balao_estilizado", "Estilizado"],
  ["residuo_balao_solido_branco", "Branco sólido"],
  ["outro", "Outro / não identificado"],
];
function applyTypeIndicators(button, types) {
  button.querySelector(".comparison-check-dots")?.remove();
  button.classList.remove("has-check-type-dots");
  if (!Array.isArray(types)) return;
  button.dataset.hasResidueOccurrences = "false"; // substitui o ponto azul antigo
  button.removeAttribute("title");
  const container = document.createElement("span");
  container.className = "comparison-check-dots";
  const shown = new Set();
  for (const [type, label] of CHECK_DOTS) {
    if (!types.includes(type) || shown.has(label)) continue;
    shown.add(label);
    const dot = document.createElement("span");
    dot.className = "comparison-check-dot";
    dot.style.backgroundColor = checkColor(type);
    dot.dataset.tooltip = label;
    dot.title = label;
    dot.setAttribute("aria-label", label);
    container.append(dot);
  }
  if (container.childElementCount) button.append(container);
  button.classList.add("has-check-type-dots");
}
