import { comparisonImageUrl } from "/_app/api/comparison.js";

export function bindComparisonPreview(preview, sidebar, getPage, context, mode) {
  function position(button) {
    if (!button || preview.hidden) return;
    const rect = button.getBoundingClientRect();
    const bounds = sidebar.getBoundingClientRect();
    const card = preview.getBoundingClientRect();
    const width = card.width || 300, height = card.height || 420;
    const gap = 12;
    let left = bounds.right + gap;
    if (left + width > innerWidth - 8) left = bounds.left - width - gap;
    left = Math.max(8, Math.min(left, innerWidth - width - 8));
    let top = rect.top - 24;
    top = Math.max(8, Math.min(top, innerHeight - height - 8));
    preview.style.left = `${left}px`; preview.style.top = `${top}px`;
  }
  function show(name, item) {
    if (name === null) { preview.hidden = true; return; }
    const page = getPage(name);
    if (!page) return;
    preview.querySelector("img").src = comparisonImageUrl(
      { ...context, layout: mode.layout }, page, mode.sides[0]);
    preview.querySelector("[data-preview-name]").textContent = name;
    preview.hidden = false;
    position(item);
  }
  return { show, position };
}
