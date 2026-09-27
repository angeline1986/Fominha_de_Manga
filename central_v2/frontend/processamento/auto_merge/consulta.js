import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { showMessage } from "/_shared/messages/messages.js";
import { createColumns, needsAttention } from "/processamento/auto_merge/registros.js";

export function createLevel1View() {
  const element = document.createElement("section");
  element.className = "auto-merge-page";
  element.innerHTML = `
    <header>
      <h1>Auto-Merge</h1>
    </header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search">
        <span class="visually-hidden">Buscar capítulo</span>
        <input type="search" data-query placeholder="Buscar capítulo...">
      </label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos">
        <button type="button" data-filter="all" aria-pressed="true">Todos</button>
        <button type="button" data-filter="absent" aria-pressed="false">Sem registro</button>
        <button type="button" data-filter="recorded" aria-pressed="false">Com registro</button>
        <button type="button" data-filter="attention" aria-pressed="false">Com problemas</button>
      </div>
      <button class="auto-merge-execute" type="button" data-execute>Executar</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>
    <p class="auto-merge-note">Consulta somente leitura. O residual é o valor salvo no Nível I e pode ter sido tratado nas etapas seguintes; as imagens não são revalidadas.</p>
  `;
  const query = element.querySelector("[data-query]");
  const filters = [...element.querySelectorAll("[data-filter]")];
  const execute = element.querySelector("[data-execute]");
  const status = element.querySelector(".auto-merge-status");
  const results = element.querySelector(".auto-merge-results");
  const pagination = createPagination();
  const selectedChapters = new Set();
  let selectedFilter = "all";
  let state = { status: "idle", chapters: [], manga: null, provider: null };

  function draw() {
    results.replaceChildren();
    element.setAttribute("aria-busy", String(state.status === "loading"));
    if (state.status === "idle") {
      status.textContent = "Selecione um provider e uma obra para consultar o Nível I.";
      return;
    }
    if (state.status === "loading") {
      status.textContent = `Consultando ${state.manga}…`;
      return;
    }
    if (state.status === "error") {
      status.textContent = state.error;
      return;
    }
    const term = query.value.trim().toLocaleLowerCase("pt-BR");
    const rows = state.chapters.filter((row) => {
      if (!row.chapter.toLocaleLowerCase("pt-BR").includes(term)) return false;
      if (selectedFilter === "attention") return needsAttention(row);
      return selectedFilter === "all" || row.level1.status === selectedFilter;
    });
    for (const button of filters) {
      const active = button.dataset.filter === selectedFilter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    status.textContent = state.chapters.length
      ? ""
      : `${state.manga} · Nenhum capítulo com imagens encontrado.`;
    const selection = pagination.select(rows);
    const currentPage = selection.rows.map((row) => row.chapter);
    const columns = createColumns({
      selected: {
        chapters: selectedChapters,
        pageSelected: currentPage.length > 0 && currentPage.every((chapter) => selectedChapters.has(chapter)),
      },
      onSelect: (chapter, checked) => {
        if (checked) selectedChapters.add(chapter);
        else selectedChapters.delete(chapter);
        draw();
      },
      onSelectPage: (checked) => {
        currentPage.forEach((chapter) => checked
          ? selectedChapters.add(chapter) : selectedChapters.delete(chapter));
        draw();
      },
    });
    if (rows.length) results.append(
      createTable(columns, selection.rows, "Resultados registrados do Auto-Merge Nível I"),
      createPaginationControls(selection, (delta) => {
        pagination.move(delta);
        draw();
      }),
    );
    else if (state.chapters.length) status.textContent = "Nenhum resultado para este filtro.";
  }

  function resetAndDraw() {
    pagination.reset();
    draw();
  }

  query.addEventListener("input", resetAndDraw);
  function selectFilter(event) {
    selectedFilter = event.currentTarget.dataset.filter;
    resetAndDraw();
  }
  async function requestExecution() {
    const count = selectedChapters.size;
    const message = count
      ? `A execução do Auto-Merge pela Central V2 ainda não está disponível. ${count} capítulo(s) permanecem selecionados.`
      : "Selecione ao menos um capítulo para executar.";
    await showMessage({ title: count ? "Execução indisponível" : "Nenhum capítulo selecionado", message });
  }
  filters.forEach((button) => button.addEventListener("click", selectFilter));
  execute.addEventListener("click", requestExecution);
  return {
    element,
    update(next) {
      if (state.provider !== next.provider || state.manga !== next.manga) {
        query.value = "";
        selectedFilter = "all";
        selectedChapters.clear();
        pagination.reset();
      }
      state = next;
      draw();
    },
    dispose() {
      query.removeEventListener("input", resetAndDraw);
      filters.forEach((button) => button.removeEventListener("click", selectFilter));
      execute.removeEventListener("click", requestExecution);
    },
  };
}
