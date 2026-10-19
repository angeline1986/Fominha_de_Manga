import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { mergedLevel3ImageUrl } from "/_app/api/textoff.js";
import { createPageList } from "/texto_off/comparison/page_list.js";
import { createSlider } from "/texto_off/comparison/slider.js";
import { clampZoom, INITIAL_ZOOM } from "/texto_off/comparison/model.js";
import { createMapearOverlay } from "/texto_off/comparison/mapear_overlay.js";

export function createMapearComparisonScreen(context, onBack) {
  const element = document.createElement("section");
  element.className = "comparison-screen focus-mode-root mapear-comparison-screen";
  element.setAttribute("aria-label", "Mapear: balões identificados");
  element.innerHTML = `<header class="comparison-page-heading">MAPEAR · BALÕES IDENTIFICADOS</header>
    <div class="comparison-workspace">
      <aside class="comparison-sidebar">
        <div class="comparison-sidebar-heading"><h2>Páginas mapeadas</h2><span></span></div>
        <label class="comparison-search"><span class="visually-hidden">Buscar página</span>
          <input data-search type="search" placeholder="Buscar página"></label>
        <div class="comparison-page-list" data-pages role="listbox" aria-label="Páginas com balões mapeados"></div>
        <div class="comparison-pagination" data-pagination></div>
        <h3 class="mapear-candidate-heading">Balões identificados na página</h3>
        <div class="mapear-candidate-list" data-candidates></div>
      </aside>
      <main class="comparison-canvas-panel">
        <header class="comparison-canvas-toolbar">
          <div class="comparison-canvas-title"><strong>Mapear — Balões identificados</strong><span data-summary></span></div>
          <div class="comparison-canvas-controls"><div class="zoom-control comparison-zoom" aria-label="Controles de zoom">
            <button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button>
            <output data-zoom-value aria-live="polite">40%</output>
            <button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button>
            <button type="button" data-zoom="one" aria-label="Visualizar em escala 1 para 1">1:1</button>
          </div><button type="button" class="btn comparison-focus-toggle" data-focus-toggle aria-label="Modo Foco" aria-pressed="false">${iconMarkup("focus-exit")} Foco</button></div>
        </header>
        <div class="comparison-canvas-viewport"><div class="comparison-state" data-state role="status" aria-live="polite">Carregando páginas do Mapear…</div><div data-viewport></div></div>
        <footer class="comparison-canvas-footer"><span>Zoom e rolagem sincronizados</span>
          <div class="comparison-focus-navigation" aria-label="Navegação entre páginas">
            <button type="button" data-prev aria-label="Página anterior">${iconMarkup("back")}</button>
            <output data-focus-count></output>
            <button type="button" data-next aria-label="Próxima página">${iconMarkup("next")}</button>
          </div><span>Atalho de foco: F</span></footer>
      </main>
    </div>`;
  const query = (selector) => element.querySelector(selector);
  const pages = (context.mapearPages || []).filter((page) => page?.source && page.candidates?.length)
    .map((page) => ({ ...page, name: page.source }));
  const state = query("[data-state]"), viewport = query("[data-viewport]");
  const layer = document.createElement("div");
  layer.className = "mapear-candidate-overlay comparison-after-overlay";
  const candidates = createMapearOverlay(layer, query("[data-candidates]"));
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet"; stylesheet.href = "/texto_off/comparison/mapear_overlay.css";
  element.append(stylesheet);
  let index = 0, zoom = INITIAL_ZOOM;
  const slider = createSlider(viewport, (next, error) => {
    state.hidden = next === "ready";
    if (next === "error") state.textContent = error;
    if (next === "ready") {
      const metrics = slider.getImageMetrics();
      candidates.render(pages[index]?.candidates, metrics.naturalWidth, metrics.naturalHeight);
    }
    element.querySelectorAll("[data-zoom]").forEach((button) => { button.disabled = next !== "ready"; });
  }, "mapear");
  slider.mountAfterOverlay(layer);
  const pageList = createPageList({ list: query("[data-pages]"), search: query("[data-search]"),
    paginationRoot: query("[data-pagination]"), onSelect: selectPage,
    onPreview: () => {}, onPreviewPosition: () => {} });
  const focusDispose = bindFocusMode(element, { button: query("[data-focus-toggle]") });

  function selectPage(next) {
    if (next < 0 || next >= pages.length) return;
    index = next;
    const page = pages[index];
    const url = mergedLevel3ImageUrl(context.provider, context.manga, context.chapter, page.source);
    state.textContent = "Carregando imagem analisada…"; state.hidden = false;
    candidates.clear();
    query("[data-summary]").textContent = `${page.source} · ${index + 1} de ${pages.length} · ${page.candidates.length} balões`;
    query("[data-focus-count]").textContent = `${index + 1} / ${pages.length}`;
    query("[data-prev]").disabled = index === 0;
    query("[data-next]").disabled = index === pages.length - 1;
    pageList.render(pages, index);
    slider.load([url, url]); slider.zoom(zoom / 100); updateZoom();
  }
  function updateZoom() { query("[data-zoom-value]").textContent = `${zoom}%`; }
  function onClick(event) {
    const action = event.target.closest("[data-zoom]")?.dataset.zoom;
    if (action) { zoom = clampZoom(zoom, action); slider.zoom(zoom / 100); updateZoom(); }
    if (event.target.closest("[data-prev]")) selectPage(index - 1);
    if (event.target.closest("[data-next]")) selectPage(index + 1);
  }
  function onKeyDown(event) {
    if (event.key === "Escape" && !element.classList.contains("is-focus-mode")) { event.preventDefault(); onBack(); }
    if (event.target.closest?.("input, textarea, select, [contenteditable='true']")) return;
    if (event.key === "ArrowLeft") selectPage(index - 1);
    if (event.key === "ArrowRight") selectPage(index + 1);
  }
  element.addEventListener("click", onClick); element.addEventListener("keydown", onKeyDown);
  query(".comparison-sidebar-heading span").textContent = `Cap. ${context.chapter}`;

  function dispose() {
    element.removeEventListener("click", onClick); element.removeEventListener("keydown", onKeyDown);
    pageList.dispose(); candidates.dispose(); slider.dispose(); focusDispose();
  }
  return { element, start() {
    if (pages.length) selectPage(0);
    else state.textContent = "Nenhum balão mapeado disponível para este capítulo.";
  }, dispose };
}
