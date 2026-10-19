import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { fetchComparison, comparisonImageUrl } from "/_app/api/comparison.js";
import { createSlider } from "/texto_off/comparison/slider.js";
import { createSolidCatalog } from "/texto_off/comparison/solid_catalog.js";
import { comparisonModeConfig, INITIAL_ZOOM, clampZoom, level2StatusText } from "/texto_off/comparison/model.js";
import { createPageList } from "/texto_off/comparison/page_list.js";
import { createResidueCatalog } from "/texto_off/comparison/residue_catalog.js";
import { fetchResidueOccurrences } from "/_app/api/residue_occurrences.js";
import { createDegradeContext } from "/texto_off/comparison/degrade_context.js";
import { bindDegradeViewTools } from "/texto_off/comparison/degrade_view_tools.js";
import { bindRestoreMergePreview } from "/texto_off/comparison/restore_merge_preview.js";

export function createComparisonScreen(context, onBack) {
  const mode = comparisonModeConfig(context.comparisonMode);
  const element = document.createElement("section");
  element.className = "comparison-screen focus-mode-root";
  if (context.comparisonMode === "check") element.classList.add("comparison-check-filters");
  element.setAttribute("aria-label", mode.heading.replace(" · ", ": "));
  element.innerHTML = `<header class="comparison-page-heading">${mode.heading}</header>
    <div class="comparison-workspace">
      <aside class="comparison-sidebar">
        <div class="comparison-sidebar-heading"><h2>Páginas</h2>${context.comparisonMode === "check" ? "" : `<span>Cap. ${escapeHtml(context.chapter)}</span>`}</div>
        ${context.comparisonMode === "check" ? `<div class="comparison-check-selects">
          <label><span class="visually-hidden">Capítulo</span><select data-check-chapter aria-label="Capítulo"></select></label>
          <label><span class="visually-hidden">Página</span><select data-check-page aria-label="Página"></select></label>
        </div>` : `<label class="comparison-search"><span class="visually-hidden">Buscar página pelo nome</span>
          <input data-search type="search" placeholder="Buscar página"></label>`}
        <div class="comparison-page-list" data-pages role="listbox" aria-label="Páginas do capítulo"></div>
        <div class="comparison-pagination" data-pagination></div>
      </aside>
      <main class="comparison-canvas-panel">
        <header class="comparison-canvas-toolbar">
          <div class="comparison-canvas-title"><strong>${mode.title}</strong><span data-summary></span></div>
          <div class="comparison-canvas-controls">
            <div class="zoom-control comparison-zoom" aria-label="Controles de zoom">
              <button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button>
              <output data-zoom-value aria-live="polite">40%</output>
              <button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button>
              <button type="button" data-zoom="one" aria-label="Visualizar em escala 1 para 1">1:1</button>
            </div>
            <button type="button" class="btn comparison-focus-toggle" data-focus-toggle aria-label="Modo Foco" aria-pressed="false">${iconMarkup("focus-exit")} Foco</button>
            <button type="button" class="btn comparison-panel-toggle" data-panel-toggle aria-controls="comparison-residue-panel" aria-expanded="false" aria-pressed="false">Painel</button>
          </div>
        </header>
        <div class="comparison-canvas-viewport"><div class="comparison-state" data-state role="status" aria-live="polite"></div><div data-viewport></div></div>
        <footer class="comparison-canvas-footer"><span>Zoom e rolagem sincronizados</span>
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
  if (context.comparisonMode === "check") {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/texto_off/comparison/restore_merge_preview.css";
    element.append(stylesheet);
  }
  if (context.comparisonMode === "check") {
    const style = document.createElement("style");
    style.textContent = `.comparison-check-filters .comparison-check-selects{
        display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.34fr);
        gap:9px;margin:0 0 14px;align-items:center
      }
      .comparison-check-filters .comparison-check-selects label{
        position:relative;display:block;min-width:0
      }
      .comparison-check-filters .comparison-check-selects label::after{
        content:"";pointer-events:none;position:absolute;
        width:8px;height:8px;right:15px;top:calc(50% - 6px);
        border-right:1.8px solid #537b93;border-bottom:1.8px solid #537b93;
        transform:rotate(45deg)
      }
      .comparison-check-filters .comparison-check-selects select{
        display:block;width:100%;min-width:0;height:44px;
        box-sizing:border-box;padding:0 34px 0 13px;
        border:1px solid #c7dfed;border-radius:10px;
        background-color:#fff;color:#275875;
        font-family:inherit;font-size:15px;font-weight:500;line-height:1.3;
        letter-spacing:0;appearance:none;-webkit-appearance:none;
        box-shadow:none;cursor:pointer;outline:none
      }
      .comparison-check-filters .comparison-check-selects select:hover{
        border-color:#9bc8e1
      }
      .comparison-check-filters .comparison-check-selects select:focus-visible{
        border-color:#5b9ec1;outline:2px solid #aed7ec;outline-offset:1px
      }
      .comparison-check-filters .comparison-check-selects select:disabled{
        color:#738e9f;background-color:#f8fbfd;cursor:default
      }
      .comparison-check-filters .comparison-check-selects label:has(select:disabled)::after{
        opacity:.55
      }`;
    element.append(style);
    const chapterSelect = query("[data-check-chapter]");
    const chapters = Array.isArray(context.availableChapters) ? context.availableChapters : [];
    const candidates = chapters.filter((item) => item.cleaned === true);
    if (!candidates.some((item) => String(item.chapter) === String(context.chapter))) {
      candidates.unshift({ chapter: context.chapter });
    }
    for (const item of candidates) {
      const option = document.createElement("option");
      option.value = String(item.chapter);
      option.textContent = `Cap. ${item.chapter}`;
      chapterSelect.append(option);
    }
    chapterSelect.value = String(context.chapter);
    chapterSelect.addEventListener("change", () => context.onChapterChange?.(chapterSelect.value));
  }
  const canvas = query("[data-viewport]");
  const state = query("[data-state]"), preview = query("[data-preview]");
  const controller = new AbortController();
  let pages = [], index = 0, activeImageIndex = null, pageState = "loading", zoom = INITIAL_ZOOM, disposed = false;
  const checkTypes = new Map();
  const slider = createSlider(canvas, (nextState, error) => {
    canvas.setAttribute("aria-busy", String(nextState === "loading"));
    element.querySelectorAll("[data-zoom]").forEach((button) => { button.disabled = nextState !== "ready"; });
    if (nextState === "error") { activeImageIndex = null; pageState = "error"; state.textContent = error; }
    else if (nextState === "ready") { activeImageIndex = index; pageState = "ready"; state.textContent = ""; catalog.render?.(); }
    drawState();
  }, context.comparisonMode);
  const createCatalog = context.comparisonMode === "solid" ? createSolidCatalog
    : ["degrade", "suave", "artistico"].includes(context.comparisonMode)
    ? createDegradeContext : createResidueCatalog;
  if (context.comparisonMode === "solid") query("[data-panel-toggle]").hidden = true;
  const catalog = createCatalog({ workspace: query(".comparison-workspace"), slider, context,
    onPersistedCount: (pageName, count) => {
      const page = pages.find((item) => item.name === pageName);
      if (!page) return;
      page.residue_occurrence_count = count;
      pageList.setOccurrenceCount(pageName, count);
    },
    onDraftState: (pageName, count, dirty, types) => {
      if (context.comparisonMode === "check" && Array.isArray(types)) checkTypes.set(pageName, types);
      pageList.setDraftOccurrenceCount(pageName, count);
    },
    onOpenChange: (open) => {
      const button = query("[data-panel-toggle]");
      button.setAttribute("aria-expanded", String(open)); button.setAttribute("aria-pressed", String(open));
    },
  });
  catalog.element.id = "comparison-residue-panel";
  query(".comparison-workspace").append(catalog.element);
  const focusButton = query("[data-focus-toggle]");
  const pageList = createPageList({
    list: query("[data-pages]"), search: query("[data-search]"),
    paginationRoot: query("[data-pagination]"), onSelect: selectPage,
    onPreview: showPreview, onPreviewPosition: drawPreviewPosition,
    getDraftOccurrenceCount: (pageName) => catalog.draftOccurrenceCount(pageName),
    getOccurrenceTypes: context.comparisonMode === "check"
      ? (pageName) => catalog.draftOccurrenceTypes(pageName) ?? checkTypes.get(pageName) ?? null
      : () => null,
  });
  const restorePreview = context.comparisonMode === "check"
    ? bindRestoreMergePreview(query(".comparison-canvas-controls"), () => ({
        context, page: pages[index],
      }), () => load()) : null;
  const disposeFocus = bindFocusMode(element, { button: focusButton });
  const disposeViewTools = context.comparisonMode === "degrade" ? bindDegradeViewTools(query(".comparison-canvas-controls"), slider) : () => {};
  document.body.append(preview);

  function drawState() {
    state.hidden = pageState === "ready";
    if (pageState === "loading" && !state.textContent) state.textContent = "Carregando imagens da comparação…";
    if (pageState === "empty") state.textContent = "Nenhum resultado atual disponível para comparação.";
    if (pageState === "error" && !state.textContent) state.textContent = "Não foi possível carregar a comparação.";
  }
  function selectPage(next) {
    preview.hidden = true;
    if (next === index && activeImageIndex === next) return;
    index = next; showPage();
  }
  function showPage() {
    const page = pages[index];
    if (!page) return;
    state.textContent = "Carregando imagens da comparação…"; pageState = "loading"; drawState();
    query("[data-summary]").textContent = `Cap. ${context.chapter} · ${page.name} · ${index + 1} de ${pages.length}`;
    catalog.setPage(page.name);
    query("[data-focus-count]").textContent = `${index + 1} / ${pages.length}`;
    query("[data-prev]").disabled = index === 0;
    query("[data-next]").disabled = index >= pages.length - 1;
    pageList.render(pages, index);
    restorePreview?.setReady(Boolean(pages[index]));
    const pageSelect = query("[data-check-page]");
    if (pageSelect) pageSelect.value = String(index);
    activeImageIndex = index;
    const imageContext = { ...context, layout: mode.layout };
    const status = context.comparisonMode === "before_after" && page.level2_status
      ? level2StatusText(page.level2_status) : "";
    slider.load(mode.sides.map((side) => comparisonImageUrl(imageContext, page, side)), status);
    slider.zoom(zoom / 100); updateZoom();
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
    preview.querySelector("img").src = comparisonImageUrl(
      { ...context, layout: mode.layout }, page, mode.sides[0],
    );
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
  function onPanel(event) { if (event.target.closest("[data-panel-toggle]")) catalog.toggle(); }
  const pageSelect = query("[data-check-page]");
  if (pageSelect) pageSelect.addEventListener("change", () => selectPage(Number(pageSelect.value)));
  const disposePageList = pageList.dispose;
  element.addEventListener("click", onZoom);
  element.addEventListener("click", onMove);
  element.addEventListener("click", onPanel);
  element.addEventListener("keydown", onKeyDown);
  async function load() {
    pageState = "loading"; drawState();
    try {
      const result = await fetchComparison({ ...context, layout: mode.layout }, controller.signal);
      if (disposed) return;
      pages = result.pages || [];
      if (context.comparisonMode === "check") void loadCheckTypes(pages);
      if (pageSelect) {
        pageSelect.replaceChildren();
        pages.forEach((page, pageIndex) => {
          const option = document.createElement("option");
          option.value = String(pageIndex);
          option.textContent = page.name.replace(/^page-/, "Pág. ").replace(/\.png$/i, "");
          pageSelect.append(option);
        });
        pageSelect.disabled = pages.length === 0;
      }
      catalog.setPages?.(pages);
      if (!pages.length) { pageState = "empty"; drawState(); pageList.render(pages, index); return; }
      if (context.initialPage) index = Math.max(0, pages.findIndex((page) =>
        page.name === context.initialPage && (!context.initialOccurrence ||
          page.occurrence_ids?.includes(context.initialOccurrence))));
      showPage();
    } catch (error) {
      if (!disposed && error.name !== "AbortError") { pageState = "error"; state.textContent = error.message; drawState(); }
    }
  }
  async function loadCheckTypes(rows) {
    // Até três requisições simultâneas; uma falha não cria classificação fictícia.
    let cursor = 0;
    async function worker() {
      while (!disposed && cursor < rows.length) {
        const page = rows[cursor++];
        try {
          const result = await fetchResidueOccurrences({ ...context, page: page.name }, controller.signal);
          if (disposed) return;
          checkTypes.set(page.name, (result.occurrences || []).map((item) => item.type ?? item.tipo ?? ""));
          pageList.setOccurrenceTypes(page.name);
        } catch (error) {
          if (error.name !== "AbortError") console.warn("[Check] Falha ao consultar tipos:", page.name, error);
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(3, rows.length) }, worker));
  }
  function dispose() {
    disposed = true; controller.abort(); preview.hidden = true; preview.querySelector("img").removeAttribute("src"); preview.remove();
    disposePageList();
    element.removeEventListener("click", onZoom);
    element.removeEventListener("click", onMove); element.removeEventListener("click", onPanel);
    element.removeEventListener("keydown", onKeyDown);
    catalog.dispose(); slider.dispose(); disposeFocus();
    restorePreview?.dispose();
    disposeViewTools();
  }
  drawState();
  return { element, start: load, dispose };
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
