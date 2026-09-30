export function createPaginationControls(selection, onMove) {
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
  element.append(range, actions);
  return element;
}
