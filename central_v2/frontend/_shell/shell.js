export function mountShell(root) {
  root.innerHTML = `
    <div class="app-shell">
      <header class="app-header">
        <div class="app-brand">
          <strong>Fominha de Mangá</strong>
          <span>Central de Processamento</span>
        </div>
      </header>

      <div class="app-body">
        <aside class="app-sidebar" aria-label="Navegação principal">
          <nav class="app-nav">
            <button type="button" data-route="visao-geral">Visão Geral</button>
            <button type="button" data-route="processamento">Processamento</button>
            <button type="button" data-route="balanceamento">Balanceamento</button>
            <button type="button" data-route="gerar-pdf">Gerar PDF</button>
            <button type="button" data-route="texto-off">Texto Off</button>
            <button type="button" data-route="exportar-arquivos">Exportar Arquivos</button>
          </nav>
        </aside>

        <main class="app-content" id="page-content" tabindex="-1">
          <h1>Central V2</h1>
          <p>Estrutura inicial da nova Central de Processamento.</p>
        </main>
      </div>
    </div>
  `;
}
