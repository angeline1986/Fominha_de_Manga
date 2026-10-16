import { paginationConfig } from "/_shared/pagination/config.js";

// Atalho para paginadores de tabela ativos; um listener por módulo, não por renderização.
function onTablePaginationKey(event) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || event.defaultPrevented || event.repeat
      || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const target = event.target;
  if (target instanceof Element && target.closest(
    'input, textarea, select, button, [contenteditable], [role="slider"], [role="dialog"], [role="listbox"]'
  )) return;
  if (document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')
      || document.body.classList.contains('has-image-focus')
      || document.body.classList.contains('lab-focus-lock')) return;
  const pagers = [...document.querySelectorAll('nav.pagination')].filter((nav) =>
    nav.getClientRects().length && !nav.closest('[hidden], [aria-hidden="true"]'));
  if (pagers.length !== 1) return;
  const button = pagers[0].querySelectorAll('button.pagination-button')[event.key === 'ArrowLeft' ? 0 : 1];
  if (!button || button.disabled) return;
  event.preventDefault();
  button.click();
}
document.addEventListener('keydown', onTablePaginationKey);

export function createPaginationControls(selection, onMove, options = {}) {
  const element = document.createElement("nav");
  element.className = "pagination";
  element.setAttribute("aria-label", "Paginação da listagem");
  const range = document.createElement("span");
  range.setAttribute("aria-live", "polite");
  range.textContent = `${selection.start}–${selection.end} de ${selection.total}`;
  const actions = document.createElement("div");
  const indicator = document.createElement("span");
  indicator.textContent = `${selection.page} / ${selection.pages}`;
  function button(label, delta, disabled) {
    const control = document.createElement("button");
    control.className = "pagination-button";
    control.type = "button";
    control.textContent = label;
    control.disabled = disabled;
    control.addEventListener("click", () => onMove(delta));
    return control;
  }
  actions.append(
    button("<<", -1, selection.page === 1),
    indicator,
    button(">>", 1, selection.page === selection.pages),
  );
  element.append(options.leading ?? range);
  if (!options.hideEmptyActions || selection.total) element.append(actions);
  return element;
}

export function createPageSizeControl(onChange, selected = paginationConfig.pageSize) {
  const label = document.createElement("label");
  label.className = "pagination-page-size";
  label.textContent = "Exibir:";
  const select = document.createElement("select");
  select.setAttribute("aria-label", "Itens por página");
  for (const value of paginationConfig.pageSizeOptions) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(value);
    select.append(option);
  }
  select.value = String(selected);
  select.addEventListener("change", () => onChange(Number(select.value)));
  label.append(select);
  return { element: label, select };
}
