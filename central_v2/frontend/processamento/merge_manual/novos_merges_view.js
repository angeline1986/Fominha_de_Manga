import { mergeManualImageUrl } from "/_app/api/merge_manual.js";

export const rulerPalette = [
  { name: "Ciano", value: "#00F0FF", title: "Contraste em fundos escuros e quentes" },
  { name: "Neon", value: "#FFE600", title: "Alta visibilidade em cenas escuras" },
  { name: "Pink", value: "#FF007F", title: "Destaque em fundos claros" },
  { name: "Lima", value: "#00FF66", title: "Alto contraste em fundos escuros" },
];
export const defaultRulerColors = ["#FFE600", "#FF007F", "#00FF66", "#00F0FF"];

export function rulerIconMarkup(color) {
  return `<svg class="manual-cut-ruler-icon" viewBox="0 0 24 18" aria-hidden="true"><rect x="2" y="3" width="20" height="13" rx="1.5" fill="none" stroke="${color}" stroke-width="2"/><path d="M6 3v5m4-5v3m4-3v5m4-5v3" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
}

export function drawPageTags(page, pages, width, totalHeight, zoom, cuts, highlightOdd, colors, focusedPageFile = null) {
  const tags = page.querySelector("[data-page-tags]");
  tags.style.width = `${width * zoom / 100}px`;
  tags.style.height = `${totalHeight * zoom / 100}px`;
  let y = 0;
  const highlights = [];
  const focusHighlights = [];
  const labels = pages.map((item) => {
    const isOdd = isOddPage(item.file);
    if (highlightOdd && isOdd) highlights.push(`<span class="manual-cut-page-highlight" style="top:${y * zoom / 100}px;height:${item.pending_height * zoom / 100}px"></span>`);
    if (item.file === focusedPageFile) focusHighlights.push(`<span class="manual-cut-page-focus" style="top:${y * zoom / 100}px;height:${item.pending_height * zoom / 100}px"></span>`);
    const tag = `<span class="manual-cut-page-tag ${isOdd ? "odd" : ""}" style="top:${y * zoom / 100}px">${escapeHtml(item.file)}${isOdd ? " · Ímpar" : ""}</span>`;
    y += item.pending_height;
    return tag;
  }).join("");
  const rulers = cuts.map((cut, index) => `<span class="manual-cut-ruler-line" style="--ruler-color:${colors[index]};top:${cut * zoom / 100}px"><b>Régua ${index + 1}</b></span>`).join("");
  tags.innerHTML = `${highlights.join("")}${focusHighlights.join("")}${labels}${rulers}`;
}

export function drawPageList(page, pages, selection, cuts, colors, onSelectPage) {
  const list = page.querySelector("[data-page-list]");
  list.innerHTML = pages.map((item) => `<button type="button" class="manual-cut-page-item ${isOddPage(item.file) ? "odd" : ""}" data-file="${escapeHtml(item.file)}"><span>${escapeHtml(item.file)}</span><small>${isOddPage(item.file) ? "ÍMPAR" : "Par"}</small></button>`).join("");
  list.querySelectorAll("[data-file]").forEach((button) => {
    const item = pages.find((candidate) => candidate.file === button.dataset.file);
    const showPreview = () => {
      const preview = page.querySelector("[data-page-preview] img");
      const card = page.querySelector("[data-page-preview]");
      const bounds = button.getBoundingClientRect();
      const cardWidth = 250;
      card.style.top = `${Math.max(12, Math.min(window.innerHeight - 210, bounds.top))}px`;
      card.style.left = `${bounds.right + cardWidth + 16 < window.innerWidth ? bounds.right + 10 : Math.max(12, bounds.left - cardWidth - 10)}px`;
      card.classList.add("is-visible");
      preview.src = mergeManualImageUrl(selection.provider, selection.manga, selection.chapter, item.file);
      preview.hidden = false;
      page.querySelector("[data-preview-label]").textContent = item.file;
    };
    const hidePreview = () => page.querySelector("[data-page-preview]").classList.remove("is-visible");
    button.addEventListener("click", () => {
      list.querySelectorAll("[data-file]").forEach((candidate) => candidate.classList.remove("is-selected"));
      button.classList.add("is-selected");
      onSelectPage?.(item);
    });
    button.addEventListener("mouseenter", showPreview);
    button.addEventListener("focus", showPreview);
    button.addEventListener("mouseleave", hidePreview);
    button.addEventListener("blur", hidePreview);
  });
  updatePageCutLabels(page, pages, cuts, colors);
}

export function updatePageCutLabels(page, pages, cuts, colors) {
  const list = page.querySelector("[data-page-list]");
  if (!list) return;
  list.querySelectorAll("[data-file]").forEach((button) => {
    const index = pages.findIndex((item) => item.file === button.dataset.file);
    const pageStart = pages.slice(0, index).reduce((sum, item) => sum + item.pending_height, 0);
    const pageEnd = pageStart + pages[index].pending_height;
    button.querySelectorAll(".manual-cut-cut-label").forEach((node) => node.remove());
    cuts.forEach((cut, ruler) => {
      if (cut >= pageStart && cut <= pageEnd) {
        const marker = document.createElement("small");
        marker.className = "manual-cut-cut-label";
        marker.style.color = colors[ruler];
        marker.textContent = `Corte ${ruler + 1}`;
        button.append(marker);
      }
    });
  });
}

export function isOddPage(file) { return Number(file.match(/page-(\d+)/i)?.[1] || 0) % 2 === 1; }
export function escapeHtml(value) { return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
