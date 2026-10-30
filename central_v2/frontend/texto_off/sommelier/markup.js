export function sommelierMarkup() {
  return `
    <div data-list-view>
    <header>
      <h1 class="textoff-page-title-hint" data-tooltip="Pré-análise antes da limpeza"
          tabindex="0" aria-description="Pré-análise antes da limpeza">Bubble Sommelier</h1>
    </header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search">
        <span class="visually-hidden">Buscar capítulo</span>
        <input type="search" data-query placeholder="Capítulo">
      </label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar análise"></div>
      <label class="sommelier-profile">
        <select data-profile aria-label="Perfil">
          <option value="">Perfil</option>
          <option value="poc_a_v1">poc_a_v1</option>
          <option value="poc_b_v1">poc_b_v1</option>
        </select>
      </label>
      <button class="auto-merge-execute sommelier-execute" type="button" data-execute
              title="Selecione capítulos e um perfil">Executar Bubble Sommelier</button>
    </div>
    <p class="auto-merge-status" data-status role="status" aria-live="polite"></p>
    <div class="auto-merge-results" data-results></div>
    </div>
    <div data-review-host hidden></div>
  `;
}
