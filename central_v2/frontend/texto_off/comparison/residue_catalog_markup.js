import { iconMarkup } from "/_shared/icons/icons.js";

export function residuePanelMarkup(isCheck) {
  const actionControls = `<button class="btn comparison-residue-action" type="button" data-signal aria-pressed="false">${isCheck ? "Sinalizar área" : "Sinalizar Resíduo"}</button>
    <button class="btn comparison-residue-action" type="button" data-draw aria-pressed="false" disabled>Selecionar área manual</button>
    <p data-hint aria-live="polite">Ative a sinalização para selecionar áreas.</p>`;
  const checkTools = `<section class="check-bottom-tools" aria-label="Ferramentas de captura">
    <div class="check-bottom-label">Ferramentas de Captura
      <span class="check-bottom-info" tabindex="0" aria-label="Informação sobre a captura">ⓘ
        <span class="check-bottom-tooltip">Ative a sinalização para selecionar áreas.</span>
      </span>
    </div>
    <div class="check-bottom-grid">
      <button class="btn check-bottom-tool" type="button" data-signal aria-pressed="false">Sinalizar</button>
      <button class="btn check-bottom-tool" type="button" data-draw aria-pressed="false" disabled>Manual</button>
    </div>
    <p data-hint class="check-bottom-hint" aria-live="polite">Ative a sinalização para selecionar áreas.</p>
    <button class="btn comparison-residue-catalog check-bottom-save" type="button" data-catalog disabled>Salvar Check</button>
    <div class="comparison-residue-feedback"><p data-feedback role="status" aria-live="polite"></p>
      <p data-source-status role="status" aria-live="polite" hidden></p>
      <button class="btn comparison-residue-retry" type="button" data-retry hidden>Recarregar ocorrências</button></div>
  </section>`;
  const actionPanel = isCheck ? checkTools
    : `<section class="comparison-residue-step"><h3>Passo 1: identificar resíduo</h3>${actionControls}</section>`;
  const layers = `<section class="comparison-residue-layers"><header><h3>${isCheck ? "Áreas nesta página" : "Camadas / áreas"}</h3><output data-count>0</output></header>
      <div data-layers></div></section>`;
  return `<header class="comparison-residue-heading"><h2>${isCheck ? "Revisão do Auto-Cleaner Check" : "Catalogação de resíduos"}</h2>
      <button class="btn comparison-residue-close" type="button" data-close aria-label="Fechar painel">${iconMarkup("close")}</button></header>
    ${isCheck ? `${layers}${actionPanel}` : `${actionPanel}${layers}`}
    ${isCheck ? "" : `<footer class="comparison-residue-step"><h3>Passo 2</h3>
      <button class="btn comparison-residue-catalog" type="button" data-catalog disabled>Catalogar Resíduo</button>
      <div class="comparison-residue-feedback"><p data-feedback role="status" aria-live="polite"></p>
        <p data-source-status role="status" aria-live="polite" hidden></p>
        <button class="btn comparison-residue-retry" type="button" data-retry hidden>Recarregar ocorrências</button></div></footer>`}`;
}
