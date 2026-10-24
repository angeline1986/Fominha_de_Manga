/** Estrutura estática da tela do Laboratório L3. */
export function createLaboratorioView(container) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/texto_off/laboratorio/style.css";
  document.head.appendChild(stylesheet);

  const root = document.createElement("section");
  root.className = "lab-page";
  root.innerHTML = `
    <div class="lab-title">LABORATÓRIO</div>
    <div class="lab-columns">
      <aside class="lab-panel lab-pages">
        <div class="lab-panel-head"><strong>Páginas</strong><div class="lab-source-toggle" role="group" aria-label="Origem das imagens"><button type="button" data-lab-source="img" class="is-active" aria-pressed="true">IMG</button><button type="button" data-lab-source="merge" aria-pressed="false">MERGE</button></div></div>
        <div class="lab-pages-body">
          <div class="lab-page-selectors">
            <select class="lab-select-chapter" data-lab-chapter aria-label="Selecionar capítulo"><option value="">Cap.</option></select>
            <select class="lab-select-page" data-lab-page aria-label="Selecionar página" disabled><option value="">Pág.</option></select>
            <button type="button" data-lab-explore class="lab-explore-button" title="Explorar arquivos da obra" aria-label="Explorar arquivos da obra">📂</button>
          </div>
          <div class="lab-page-list" data-lab-list aria-label="Páginas do capítulo"></div>
          <nav class="lab-pager" aria-label="Paginação das páginas">
            <button type="button" data-lab-prev aria-label="Página anterior" disabled>‹</button>
            <span data-lab-counter>1 / 1</span>
            <button type="button" data-lab-next aria-label="Próxima página" disabled>›</button>
          </nav>
          <div class="lab-preview" data-lab-preview hidden><img alt="Prévia da página" /></div>
          <dialog class="lab-explorer" data-lab-explorer aria-label="Explorador de arquivos"><header><strong>Arquivos da obra</strong><button type="button" data-lab-explorer-close aria-label="Fechar explorador">×</button></header><div class="lab-explorer-path" data-lab-explorer-path></div><div class="lab-explorer-list" data-lab-explorer-list></div></dialog>
        </div>
      </aside>
      <main class="lab-workspace">
        <div class="lab-toolbar"><div><strong>Laboratório</strong><div class="lab-muted">Uma imagem original · quatro tratamentos independentes</div></div>
          <div class="lab-tool-group"><button disabled type="button">−</button><span>40%</span><button disabled type="button">+</button><button disabled type="button">1:1</button><button disabled type="button" aria-label="Foco" title="Foco"><svg aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m13-5v3a2 2 0 0 1-2 2h-3"/></svg></button></div>
        </div>
        <div class="lab-stage">
          <div class="lab-cards">
            <section class="lab-image"><header>ORIGINAL</header><div class="lab-placeholder">Aguardando seleção da página</div></section>
            <section class="lab-image lab-treatment-card"><header>DEGRADÊ</header><div class="lab-placeholder" data-treatment-status="degrade" data-state="waiting" role="status" aria-live="polite">Aguardando execução</div><button type="button" class="lab-review-button btn" data-lab-review="degrade" hidden>Comparar com Consolidado Final</button></section>
            <section class="lab-image lab-treatment-card"><header>ARTÍSTICO</header><div class="lab-placeholder" data-treatment-status="stylized" data-state="waiting" role="status" aria-live="polite">Aguardando execução</div><button type="button" class="lab-review-button btn" data-lab-review="estilizado" hidden>Comparar com Consolidado Final</button></section>
            <section class="lab-image lab-treatment-card"><header>SUAVE</header><div class="lab-placeholder" data-treatment-status="smooth" data-state="waiting" role="status" aria-live="polite">Aguardando execução</div><button type="button" class="lab-review-button btn" data-lab-review="gradiente_suave" hidden>Comparar com Consolidado Final</button></section>
            <section class="lab-image lab-treatment-card"><header>SÓLIDOS</header><div class="lab-placeholder" data-treatment-status="solid" data-state="waiting" role="status" aria-live="polite">Aguardando execução</div><button type="button" class="lab-review-button btn" data-lab-review="solidos" hidden>Comparar com Consolidado Final</button></section>
          </div>
        </div>
      </main>
      <aside class="lab-panel lab-actions"><div class="lab-panel-head"><strong>Laboratório</strong></div>
        <div class="lab-panel-body"><strong class="lab-subtitle">Seleção de áreas</strong><button disabled class="lab-wide">Selecionar área</button>
          <p class="lab-muted">Nenhuma área selecionada.</p><hr/><strong class="lab-subtitle">Tratamentos</strong>
          <div class="lab-treatment-actions">
            <button type="button" class="lab-wide" data-lab-degrade>Executar Degradê</button>
            <button type="button" class="lab-wide" data-lab-stylized>Executar Artístico</button>
            <button type="button" class="lab-wide" data-lab-smooth>Executar Suave</button>
            <button type="button" class="lab-wide" data-lab-solid>Executar Sólidos</button>
          </div>
          <p class="lab-final-selection" data-lab-final-selection role="status" aria-live="polite" hidden></p>
          <button type="button" class="lab-final-apply btn" data-lab-final-apply hidden>Aplicar no Consolidado Final</button>
          <button type="button" class="lab-final-history btn" data-lab-final-history hidden>Histórico do Consolidado Final</button>
        </div>
      </aside>
    </div>`;
  container.replaceChildren(root);

  return {
    root,
    dispose() {
      if (root.parentNode === container) root.remove();
      stylesheet.remove();
    },
  };
}
