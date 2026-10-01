import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { fetchComparison, comparisonImageUrl } from "/_app/api/comparison.js";
import { createSlider } from "/texto_off/comparison/slider.js";
import { INITIAL_ZOOM, clampZoom } from "/texto_off/comparison/model.js";
import { createPageList } from "/texto_off/comparison/page_list.js";

export function createComparisonScreen(context, onBack) {
  const element = document.createElement("section");
  element.className = "comparison-screen focus-mode-root";
  element.setAttribute("aria-label", "Comparar Capítulo");
  element.innerHTML = `<header class="comparison-page-heading">COMPARAR CAPÍTULO</header>
    <div class="comparison-workspace">
      <aside class="comparison-sidebar">
        <div class="comparison-sidebar-heading"><h2>Páginas</h2><span>Cap. ${escapeHtml(context.chapter)}</span></div>
        <label class="comparison-search"><span class="visually-hidden">Buscar página pelo nome</span>
          <input data-search type="search" placeholder="Buscar página"></label>
        <div class="comparison-page-list" data-pages role="listbox" aria-label="Páginas do capítulo"></div>
        <div class="comparison-pagination" data-pagination></div>
      </aside>
      <main class="comparison-canvas-panel">
        <header class="comparison-canvas-toolbar">
          <div class="comparison-canvas-title"><strong>Comparação do capítulo</strong><span data-summary></span></div>
          <div class="comparison-view-toggle" role="group" aria-label="Modo de comparação">
            <button type="button" data-mode="split" aria-pressed="true">Visão única</button>
            <button type="button" data-mode="side" aria-pressed="false">Lado a lado</button>
          </div>
          <div class="comparison-canvas-controls">
            <div class="zoom-control comparison-zoom" aria-label="Controles de zoom">
              <button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button>
              <output data-zoom-value aria-live="polite">40%</output>
              <button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button>
              <button type="button" data-zoom="one" aria-label="Visualizar em escala 1 para 1">1:1</button>
            </div>
            <button type="button" class="btn comparison-focus-toggle" data-focus-toggle aria-label="Modo Foco" aria-pressed="false">${iconMarkup("focus-exit")} Foco</button>
          </div>
        </header>
        <div class="comparison-canvas-viewport"><div class="comparison-state" data-state role="status" aria-live="polite"></div><div data-viewport></div></div>
        <footer class="comparison-canvas-footer"><span data-footer-context>Original ↔ Texto Off</span>
          <div class="comparison-focus-navigation" data-focus-navigation aria-label="Navegação entre páginas">
            <button type="button" data-prev aria-label="Página anterior" title="Página anterior">${iconMarkup("back")}</button>
            <output data-focus-count></output>
            <button type="button" data-next aria-label="Próxima página" title="Próxima página">${iconMarkup("next")}</button>
          </div>
          <span>Atalho de foco: F</span>
        </footer>
      </main>
    </div>
    <aside class="comparison-hover-preview" data-preview role="tooltip" hidden>
      <img alt="Prévia da imagem original"><span data-preview-name></span></aside>`;

  const query = (selector) => element.querySelector(selector);
  const canvas = query("[data-viewport]");
  const state = query("[data-state]"), preview = query("[data-preview]");
  const controller = new AbortController();
  let pages = [], index = 0, pageState = "loading", mode = "split", zoom = INITIAL_ZOOM, disposed = false;
  const slider = createSlider(canvas, (nextState, error) => {
    canvas.setAttribute("aria-busy", String(nextState === "loading"));
    element.querySelectorAll("[data-zoom]").forEach((button) => { button.disabled = nextState !== "ready"; });
    if (nextState === "error") { pageState = "error"; state.textContent = error; }
    else if (nextState === "ready") { pageState = "ready"; state.textContent = ""; }
    drawState();
  });
  const focusButton = query("[data-focus-toggle]");
  const pageList = createPageList({
    list: query("[data-pages]"), search: query("[data-search]"),
    paginationRoot: query("[data-pagination]"), onSelect: selectPage,
    onPreview: showPreview, onPreviewPosition: drawPreviewPosition,
  });
  const disposeFocus = bindFocusMode(element, { button: focusButton });
  document.body.append(preview);

  function drawState() {
    state.hidden = pageState === "ready";
    if (pageState === "loading" && !state.textContent) state.textContent = "Carregando imagens da comparação…";
    if (pageState === "empty") state.textContent = "Nenhum resultado atual disponível para comparação.";
    if (pageState === "error" && !state.textContent) state.textContent = "Não foi possível carregar a comparação.";
  }
  function selectPage(next) {
    index = next; preview.hidden = true; showPage();
  }
  function showPage() {
    const page = pages[index];
    if (!page) return;
    state.textContent = "Carregando imagens da comparação…"; pageState = "loading"; drawState();
    query("[data-summary]").textContent = `Cap. ${context.chapter} · ${page.name} · ${index + 1} de ${pages.length}`;
    query("[data-focus-count]").textContent = `${index + 1} / ${pages.length}`;
    query("[data-prev]").disabled = index === 0;
    query("[data-next]").disabled = index >= pages.length - 1;
    pageList.render(pages, index);
    slider.load(comparisonImageUrl(context, page, "before"), comparisonImageUrl(context, page, "after"));
    slider.setMode(mode); slider.zoom(zoom / 100); updateZoom();
  }
  function drawPreviewPosition(button) {
    if (!button || preview.hidden) return;
    const rect = button.getBoundingClientRect();
    const sidebar = query(".comparison-sidebar").getBoundingClientRect();
    const card = preview.getBoundingClientRect();
    const width = card.width || 300, height = card.height || 420;
    const gap = 12;
    let left = sidebar.right + gap;
    if (left + width > innerWidth - 8) left = sidebar.left - width - gap;
    left = Math.max(8, Math.min(left, innerWidth - width - 8));
    let top = rect.top - 24;
    top = Math.max(8, Math.min(top, innerHeight - height - 8));
    preview.style.left = `${left}px`; preview.style.top = `${top}px`;
  }
  function showPreview(name, item) {
    if (name === null) { preview.hidden = true; return; }
    const page = pages.find((entry) => entry.name === name);
    if (!page) return;
    preview.querySelector("img").src = comparisonImageUrl(context, page, "before");
    preview.querySelector("[data-preview-name]").textContent = name;
    preview.hidden = false; drawPreviewPosition(item);
  }
  function onZoom(event) {
    const action = event.target.closest("[data-zoom]")?.dataset.zoom;
    if (!action) return;
    zoom = clampZoom(zoom, action);
    slider.zoom(zoom / 100); updateZoom();
  }
  function updateZoom() { query("[data-zoom-value]").textContent = `${zoom}%`; }
  function onMode(event) {
    const button = event.target.closest("[data-mode]");
    if (!button) return;
    mode = button.dataset.mode; slider.setMode(mode);
    element.querySelectorAll("[data-mode]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  }
  function onKeyDown(event) {
    if (event.key === "Escape") {
      if (!element.classList.contains("is-focus-mode")) { event.preventDefault(); onBack(); }
      return;
    }
    if (event.target.closest?.("input, textarea, select, [contenteditable='true'], [role='slider']")) return;
    if (event.key === "ArrowLeft" && index > 0) { event.preventDefault(); selectPage(index - 1); }
    if (event.key === "ArrowRight" && index < pages.length - 1) { event.preventDefault(); selectPage(index + 1); }
  }
  function onMove(event) {
    const control = event.target.closest("[data-prev], [data-next]");
    if (!control) return;
    const delta = control.matches("[data-prev]") ? -1 : 1;
    if (pages[index + delta]) selectPage(index + delta);
  }
  const disposePageList = pageList.dispose;
  element.addEventListener("click", onZoom);
  element.addEventListener("click", onMode);
  element.addEventListener("click", onMove);
  element.addEventListener("keydown", onKeyDown);

  async function load() {
    pageState = "loading"; drawState();
    try {
      const result = await fetchComparison(context, controller.signal);
      if (disposed) return;
      pages = result.pages || [];
      query("[data-footer-context]").textContent = result.experimental ? "Prévia experimental · Original ↔ Texto Off" : "Original ↔ Texto Off";
      if (!pages.length) { pageState = "empty"; drawState(); pageList.render(pages, index); return; }
      showPage();
    } catch (error) {
      if (!disposed && error.name !== "AbortError") { pageState = "error"; state.textContent = error.message; drawState(); }
    }
  }
  function dispose() {
    disposed = true; controller.abort(); preview.hidden = true; preview.querySelector("img").removeAttribute("src"); preview.remove();
    disposePageList();
    element.removeEventListener("click", onZoom); element.removeEventListener("click", onMode);
    element.removeEventListener("click", onMove); element.removeEventListener("keydown", onKeyDown);
    slider.dispose(); disposeFocus();
  }
  drawState();
  return { element, start: load, dispose };
}

function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
