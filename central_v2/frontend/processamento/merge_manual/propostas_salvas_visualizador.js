import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";

export function savedProposalToolbar(chapter, page, index, total, zoom, panelOpen) {
  return `<header class="saved-review-toolbar"><div><strong>Merge Manual — Propostas Salvas</strong><span>Cap. ${chapter} · ${page} · ${total ? index + 1 : 0} de ${total}</span></div>
    <div class="saved-review-controls"><div class="saved-review-zoom" aria-label="Controles de zoom">
      <button type="button" class="btn" data-zoom="-" aria-label="Diminuir zoom">−</button><output data-zoom-value aria-live="polite">${zoom}%</output>
      <button type="button" class="btn" data-zoom="+" aria-label="Aumentar zoom">+</button><button type="button" class="btn" data-zoom="one" aria-label="Visualizar em escala 1 para 1">1:1</button></div>
      <button type="button" class="btn saved-review-focus" data-focus-toggle aria-pressed="false">${iconMarkup("focus-exit")} Foco</button>
      <button type="button" class="btn saved-review-panel-toggle" data-panel-toggle aria-controls="saved-proposal-panel" aria-expanded="${panelOpen}" aria-pressed="${panelOpen}">Painel</button></div></header>`;
}

export function savedProposalFooter(index, total) {
  return `<footer class="saved-review-footer"><span>Zoom e rolagem sincronizados</span>
    <div class="saved-review-focus-navigation" aria-label="Navegação entre páginas">
      <button type="button" class="btn" data-focus-prev aria-label="Página anterior" ${index <= 0 ? "disabled" : ""}>${iconMarkup("back")}</button>
      <output>${total ? index + 1 : 0} de ${total}</output>
      <button type="button" class="btn" data-focus-next aria-label="Próxima página" ${index >= total - 1 ? "disabled" : ""}>${iconMarkup("next")}</button>
    </div><span>Atalho de foco: F</span></footer>`;
}

export function bindSavedProposalViewer(root, { zoom, onZoom, activeFocus, onFocusChange }) {
  const focusButton = root.querySelector("[data-focus-toggle]");
  const disposeFocus = bindFocusMode(root, { button: focusButton, active: activeFocus, onChange: onFocusChange });

  function fitImage(image) {
    if (!image.naturalWidth || !image.naturalHeight) return;
    const width = image.naturalWidth * zoom / 100;
    const height = image.naturalHeight * zoom / 100;
    image.style.width = `${width}px`;
    image.style.height = `${height}px`;
    image.closest("figure").style.width = `${width}px`;
    image.closest("figure").style.height = `${height + 44}px`;
  }
  function setZoom(value) {
    zoom = value; root.querySelector("[data-zoom-value]").textContent = `${zoom}%`;
    root.querySelectorAll(".saved-review-images img").forEach(fitImage);
    onZoom(zoom);
  }
  function onClick(event) {
    const action = event.target.closest("[data-zoom]")?.dataset.zoom;
    if (!action) return;
    setZoom(action === "one" ? 100 : Math.max(20, Math.min(200, zoom + (action === "+" ? 10 : -10))));
  }
  function onImageLoad(event) {
    if (event.target.matches(".saved-review-images img")) fitImage(event.target);
  }
  root.addEventListener("click", onClick);
  root.addEventListener("load", onImageLoad, true);
  setZoom(zoom);
  return { refresh() {
    root.querySelectorAll(".saved-review-images img").forEach(fitImage);
    const viewport = root.querySelector(".saved-review-viewport");
    if (viewport) { viewport.scrollTop = 0; viewport.scrollLeft = 0; }
  }, dispose() {
    root.removeEventListener("click", onClick);
    root.removeEventListener("load", onImageLoad, true);
    disposeFocus();
  } };
}
