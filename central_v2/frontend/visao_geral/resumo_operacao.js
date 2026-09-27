import { getMangaState } from "/_app/state/manga_state.js";

export function render(container) {
  const state = getMangaState();

  container.innerHTML = `
    <section class="page page-resumo-operacao">
      <header class="page-header">
        <div>
          <span class="page-eyebrow">VISÃO GERAL</span>
          <h1>Resumo da Operação</h1>
        </div>
      </header>

      ${
        state.manga
          ? `
            <div class="page-summary">
              <div class="summary-card">
                <span class="summary-label">Obra</span>
                <strong class="summary-value">${escapeHtml(state.manga)}</strong>
              </div>

              <div class="summary-card">
                <span class="summary-label">Capítulos</span>
                <strong class="summary-value">${state.summary.chapters}</strong>
              </div>
            </div>
          `
          : `
            <div class="page-empty">
              <h2>Nenhuma obra selecionada</h2>
              <p>Selecione um provider e uma obra no contexto da Central.</p>
            </div>
          `
      }
    </section>
  `;
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = value ?? "";
  return element.innerHTML;
}
