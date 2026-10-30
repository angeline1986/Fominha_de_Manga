import { iconMarkup } from "/_shared/icons/icons.js";
import { pageNavigationMarkup } from "/texto_off/comparison/page_navigation.js";
import { panelChooserMarkup } from "/texto_off/comparison/panel_chooser.js";

export function comparisonScreenMarkup(mode, comparisonMode) {
  return `<header class="comparison-page-heading">${mode.heading}</header>
    <div class="comparison-workspace">
      <aside class="comparison-sidebar">
        <div class="comparison-sidebar-heading"><h2>Páginas</h2></div>
        ${pageNavigationMarkup(comparisonMode !== "check")}
        <div class="comparison-page-list" data-pages role="listbox" aria-label="Páginas do capítulo"></div>
        <div class="comparison-pagination" data-pagination></div>
      </aside>
      <main class="comparison-canvas-panel">
        <header class="comparison-canvas-toolbar">
          <div class="comparison-canvas-title"><strong>${mode.title}</strong><span data-summary></span></div>
          <div class="comparison-canvas-controls">
            ${panelChooserMarkup(comparisonMode)}
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
}
