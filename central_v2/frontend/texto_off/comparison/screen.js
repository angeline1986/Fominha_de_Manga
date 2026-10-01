import { fetchComparison, comparisonImageUrl } from "/_app/api/comparison.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { createSlider } from "/texto_off/comparison/slider.js";

export function createComparisonScreen(context, onBack) {
  const element = document.createElement("section");
  element.className = "comparison-screen";
  element.setAttribute("aria-label", "Antes e Depois");
  element.innerHTML = `<header class="qc-studio-toolbar">
    <div class="toolbar-z-left"><button class="btn comparison-back" type="button" data-back>← Voltar</button>
    <nav class="comparison-breadcrumb" aria-label="Localização"><span data-manga></span><span>›</span>
    <span>Cap. <b data-chapter></b></span><span>›</span><span data-filename></span></nav></div>
    <div class="toolbar-z-center"><div class="view-mode-toggle" role="group" aria-label="Modo de comparação">
      <button class="mode-btn active" type="button" data-mode="split">◐ Visão única</button>
      <button class="mode-btn" type="button" data-mode="side">◫ Lado a lado</button></div>
      <div class="zoom-widget"><button type="button" data-zoom-down aria-label="Diminuir zoom">−</button>
      <span class="z-val" data-zoom-value>100%</span><button type="button" data-zoom-up aria-label="Aumentar zoom">+</button>
      <button type="button" data-zoom-reset aria-label="Redefinir zoom">↺</button></div></div>
    <div class="toolbar-z-right"><span class="comparison-kind" data-kind></span></div>
    </header><div class="comparison-studio-body">
      <aside class="studio-pages-sidebar"><div class="sidebar-obra-head"><div class="o-title" data-sidebar-manga></div>
      <div class="o-sub">Cap. <span data-sidebar-chapter></span> · <span data-total></span> páginas</div></div>
      <div class="sidebar-search-box"><input type="search" data-search placeholder="Buscar página" aria-label="Buscar página"></div>
      <div class="pages-scroll-stack" data-pages role="listbox" aria-label="Páginas do capítulo"></div></aside>
      <div class="studio-canvas-area"><div class="comparison-message" role="status" aria-live="polite"></div>
      <div class="comparison-viewport"></div></div>
      <aside class="hover-thumb-card" data-preview hidden><img alt="Prévia da página" data-preview-image>
      <div><span data-preview-name></span><span data-preview-number></span></div></aside>
    </div><footer class="studio-footer-pager"><button class="btn-pager" type="button" data-prev>◀ Anterior</button>
    <span class="page-pill-current" data-count></span><button class="btn-pager" type="button" data-next>Próxima ▶</button></footer>`;
  const query = (selector) => element.querySelector(selector);
  query("[data-manga]").textContent = context.manga;
  query("[data-sidebar-manga]").textContent = context.manga;
  query("[data-chapter]").textContent = context.chapter;
  query("[data-sidebar-chapter]").textContent = context.chapter;
  const message = query(".comparison-message"), viewport = query(".comparison-viewport");
  const list = query("[data-pages]"), search = query("[data-search]");
  const controller = new AbortController();
  let pages = [], index = 0, disposed = false, mode = "split", previewTimer;
  const slider = createSlider(viewport, (state, error) => {
    viewport.setAttribute("aria-busy", String(state === "loading"));
    message.hidden = state === "ready";
    message.textContent = state === "loading" ? "Carregando imagens…" : error || "";
    element.querySelectorAll("[data-zoom-down], [data-zoom-up], [data-zoom-reset]")
      .forEach((button) => { button.disabled = state !== "ready"; });
  });
  function filteredPages() {
    const term = search.value.trim().toLocaleLowerCase("pt-BR");
    return pages.map((page, position) => ({ page, position }))
      .filter(({ page }) => page.name.toLocaleLowerCase("pt-BR").includes(term));
  }
  function drawList() {
    list.replaceChildren();
    for (const { page, position } of filteredPages()) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "page-row-btn";
      button.classList.toggle("active", position === index);
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(position === index));
      button.textContent = page.name;
      button.addEventListener("click", () => { index = position; show(); });
      button.addEventListener("mouseenter", () => showPreview(page, position, button));
      button.addEventListener("mouseleave", schedulePreviewClose);
      list.append(button);
    }
  }
  function schedulePreviewClose() { previewTimer = setTimeout(() => { query("[data-preview]").hidden = true; }, 100); }
  function showPreview(page, position, button) {
    clearTimeout(previewTimer);
    const card = query("[data-preview]"), rect = button.getBoundingClientRect();
    card.style.top = `${Math.max(12, Math.min(rect.top, innerHeight - 470))}px`;
    query("[data-preview-name]").textContent = page.name;
    query("[data-preview-number]").textContent = `${position + 1} / ${pages.length}`;
    query("[data-preview-image]").src = comparisonImageUrl(context, page, "before");
    card.hidden = false;
  }
  function show() {
    const page = pages[index];
    if (!page) return;
    query("[data-filename]").textContent = page.name;
    query("[data-count]").textContent = `${index + 1} / ${pages.length}`;
    query("[data-prev]").disabled = index === 0;
    query("[data-next]").disabled = index >= pages.length - 1;
    drawList();
    slider.load(comparisonImageUrl(context, page, "before"), comparisonImageUrl(context, page, "after"));
  }
  query("[data-back]").addEventListener("click", onBack);
  query("[data-prev]").addEventListener("click", () => { if (index > 0) { index--; show(); } });
  query("[data-next]").addEventListener("click", () => { if (index < pages.length - 1) { index++; show(); } });
  search.addEventListener("input", drawList);
  const preview = query("[data-preview]");
  preview.addEventListener("mouseenter", () => clearTimeout(previewTimer));
  preview.addEventListener("mouseleave", schedulePreviewClose);
  element.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
    mode = button.dataset.mode; slider.setMode(mode);
    element.querySelectorAll("[data-mode]").forEach((item) => {
      const active = item === button; item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  }));
  query("[data-zoom-down]").addEventListener("click", () => setZoom(slider.getZoom() - 0.25));
  query("[data-zoom-up]").addEventListener("click", () => setZoom(slider.getZoom() + 0.25));
  query("[data-zoom-reset]").addEventListener("click", () => setZoom(1));
  function setZoom(value) {
    const zoom = slider.zoom(value); query("[data-zoom-value]").textContent = `${Math.round(zoom * 100)}%`;
  }
  element.addEventListener("keydown", (event) => {
    if (event.key === "Escape") onBack();
    if (event.target.matches("input, select, [role=slider], [contenteditable=true]")) return;
    if (event.key === "ArrowLeft" && index > 0) { index--; show(); }
    if (event.key === "ArrowRight" && index < pages.length - 1) { index++; show(); }
  });
  async function load() {
    message.textContent = "Consultando imagens disponíveis…";
    try {
      const result = await fetchComparison(context, controller.signal);
      if (disposed) return;
      pages = result.pages;
      query("[data-total]").textContent = String(pages.length);
      query("[data-kind]").textContent = result.experimental ? "Prévia experimental" : "Resultado registrado";
      if (!pages.length) { message.textContent = "Nenhum resultado atual disponível para comparação."; return; }
      show(); query("[data-back]").focus();
    } catch (error) { if (!disposed && error.name !== "AbortError") message.textContent = error.message; }
  }
  return {
    element,
    start() { query("[data-back]").focus(); load(); },
    dispose() { disposed = true; clearTimeout(previewTimer); controller.abort(); slider.dispose(); element.remove(); },
  };
}
