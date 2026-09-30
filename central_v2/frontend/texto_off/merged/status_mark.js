export function createStatusMark(label, state) {
  const mark = document.createElement("span");
  const symbol = state === "complete" ? "✓" : state === "review" ? "!" : "—";
  mark.className = `textoff-status-mark is-${state}`;
  mark.textContent = symbol;
  mark.title = label;
  mark.setAttribute("role", "img");
  mark.setAttribute("aria-label", label);
  return mark;
}
