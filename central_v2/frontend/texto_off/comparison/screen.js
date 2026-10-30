import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { fetchComparison, comparisonImageUrl } from "/_app/api/comparison.js";
import { createSlider } from "/texto_off/comparison/slider.js";
import { createSolidCatalog } from "/texto_off/comparison/solid_catalog.js";
import { comparisonModeConfig, INITIAL_ZOOM, clampZoom, level2StatusText } from "/texto_off/comparison/model.js";
import { createPageList } from "/texto_off/comparison/page_list.js";
import { createResidueCatalog } from "/texto_off/comparison/residue_catalog.js";
import { createDegradeContext } from "/texto_off/comparison/degrade_context.js";
import { bindDegradeViewTools } from "/texto_off/comparison/degrade_view_tools.js";
import { bindRestoreMergePreview } from "/texto_off/comparison/restore_merge_preview.js";
import { comparisonScreenMarkup } from "/texto_off/comparison/screen_template.js";
import { createPageNavigation } from "/texto_off/comparison/page_navigation.js";
import { bindComparisonPreview } from "/texto_off/comparison/screen_preview.js";
import { loadCheckTypes } from "/texto_off/comparison/screen_check_types.js";
import { bindPanelChooser } from "/texto_off/comparison/panel_chooser.js";

export function createComparisonScreen(context, onBack) {
  const mode = comparisonModeConfig(context.comparisonMode);
  const element = document.createElement("section");
  element.className = "comparison-screen focus-mode-root";
  if (context.comparisonMode === "check") element.classList.add("comparison-check-filters");
  element.setAttribute("aria-label", mode.heading.replace(" · ", ": "));
  element.innerHTML = comparisonScreenMarkup(mode, context.comparisonMode);
  const query = (selector) => element.querySelector(selector);
  if (context.comparisonMode === "check") {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/texto_off/comparison/restore_merge_preview.css";
    element.append(stylesheet);
  }
  const navigation = createPageNavigation(element, {
    chapter: context.chapter,
    chapters: context.availableChapters,
    onChapterChange: context.onChapterChange,
    onPageChange: selectPage,
  });
  const canvas = query("[data-viewport]");
  const state = query("[data-state]"), preview = query("[data-preview]");
  const controller = new AbortController();
  let pages = [], index = 0, activeImageIndex = null, pageState = "loading", zoom = context.viewState?.zoom ?? INITIAL_ZOOM, disposed = false;
  const checkTypes = new Map();
  const dirtyPages = new Set();
  const checkImageRefreshRetries = new Set();
  const slider = createSlider(canvas, (nextState, error) => {
    canvas.setAttribute("aria-busy", String(nextState === "loading"));
    element.querySelectorAll("[data-zoom]").forEach((button) => { button.disabled = nextState !== "ready"; });
    if (nextState === "error") {
      activeImageIndex = null; pageState = "error"; state.textContent = error;
      refreshCheckImagesOnce();
    }
    else if (nextState === "ready") { activeImageIndex = index; pageState = "ready"; state.textContent = ""; catalog.render?.(); }
    drawState();
  }, context.comparisonMode);
  const panelChooser = context.comparisonMode === "before_after"
    ? bindPanelChooser(element, slider, context.viewState?.visiblePanels) : null;
  const createCatalog = context.comparisonMode === "solid" ? createSolidCatalog
    : ["degrade", "suave", "artistico"].includes(context.comparisonMode)
    ? createDegradeContext : createResidueCatalog;
  if (context.comparisonMode === "solid") query("[data-panel-toggle]").hidden = true;
  const catalog = createCatalog({ workspace: query(".comparison-workspace"), slider, context,
    onCheckSaved: () => load({ preserveSelection: true }),
    onPersistedCount: (pageName, count) => {
      const page = pages.find((item) => item.name === pageName);
      if (!page) return;
      page.residue_occurrence_count = count;
      pageList.setOccurrenceCount(pageName, count);
    },
    onDraftState: (pageName, count, dirty, types) => {
      if (dirty) dirtyPages.add(pageName); else dirtyPages.delete(pageName);
      navigation.setChapterBlocked(dirtyPages.size > 0);
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
  const { show: showPreview, position: drawPreviewPosition } = bindComparisonPreview(
    preview, query(".comparison-sidebar"), (name) => pages.find((page) => page.name === name), context, mode);
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
  const disposeFocus = bindFocusMode(element, { button: focusButton, active: context.viewState?.focus });
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
    navigation.selectPage(index);
    activeImageIndex = index;
    const imageContext = { ...context, layout: mode.layout };
    const status = context.comparisonMode === "before_after" && page.level2_status
      ? level2StatusText(page.level2_status) : "";
    slider.load(mode.sides.map((side) => comparisonImageUrl(imageContext, page, side)), status);
    slider.zoom(zoom / 100); updateZoom();
  }
  function refreshCheckImagesOnce() {
    const page = pages[index];
    if (context.comparisonMode !== "check" || !page || checkImageRefreshRetries.has(page.name)) return;
    checkImageRefreshRetries.add(page.name);
    void load({ preserveSelection: true });
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
  const disposePageList = pageList.dispose;
  element.addEventListener("click", onZoom);
  element.addEventListener("click", onMove);
  element.addEventListener("click", onPanel);
  element.addEventListener("keydown", onKeyDown);
  async function load({ preserveSelection = false } = {}) {
    const selectedPage = preserveSelection ? pages[index]?.name : null;
    pageState = "loading"; state.textContent = "Carregando imagens da comparação…"; drawState();
    try {
      const result = await fetchComparison({ ...context, layout: mode.layout }, controller.signal);
      if (disposed) return;
      pages = result.pages || [];
      if (context.comparisonMode === "check") void loadCheckTypes(pages, context, controller.signal,
        () => disposed, (name, types) => { checkTypes.set(name, types); pageList.setOccurrenceTypes(name); });
      navigation.setPages(pages);
      catalog.setPages?.(pages);
      if (!pages.length) { pageState = "empty"; drawState(); pageList.render(pages, index); return; }
      if (selectedPage && pages.some((page) => page.name === selectedPage)) {
        index = pages.findIndex((page) => page.name === selectedPage);
      } else if (context.initialPage) index = Math.max(0, pages.findIndex((page) =>
        page.name === context.initialPage && (!context.initialOccurrence ||
          page.occurrence_ids?.includes(context.initialOccurrence))));
      showPage();
    } catch (error) {
      if (!disposed && error.name !== "AbortError") { pageState = "error"; state.textContent = error.message; drawState(); }
    }
  }
  function dispose() {
    disposed = true; controller.abort(); preview.hidden = true; preview.querySelector("img").removeAttribute("src"); preview.remove();
    disposePageList();
    element.removeEventListener("click", onZoom);
    element.removeEventListener("click", onMove); element.removeEventListener("click", onPanel);
    element.removeEventListener("keydown", onKeyDown);
    catalog.dispose(); panelChooser?.dispose(); slider.dispose(); disposeFocus();
    restorePreview?.dispose();
    disposeViewTools();
  }
  drawState();
  return { element, start: load, dispose, getViewState: () => ({ zoom, focus: element.classList.contains("is-focus-mode"),
    ...(panelChooser ? { visiblePanels: panelChooser.selected() } : {}) }) };
}
