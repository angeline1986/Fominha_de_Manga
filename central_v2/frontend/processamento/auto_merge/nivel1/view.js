import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createColumns, matchesLevel1Filter } from "/processamento/auto_merge/shared/registros.js";

export function createLevel1View({ onExecute } = {}) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level1";
  element.innerHTML = `
    <header>
      <h1>Auto-Merge</h1>
    </header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search">
        <span class="visually-hidden">Buscar capítulo</span>
        <input type="search" data-query placeholder="Buscar cap.">
      </label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos">
        <button type="button" data-filter="all" aria-pressed="true">Todos</button>
        <button type="button" data-filter="clean" aria-pressed="false">Limpeza pronta</button>
        <button type="button" data-filter="pdf_merge" aria-pressed="false">PDF pronto</button>
        <button type="button" data-filter="occurrences" aria-pressed="false">Com ocorrências</button>
        <button type="button" data-filter="merge" aria-pressed="false">MERGE identificado</button>
      </div>
      <button class="auto-merge-execute" type="button" data-execute>Executar</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>
    <p class="auto-merge-note">A tabela mostra os registros salvos. A execução usa somente cortes seguros e preserva estágios ou destinos MERGE já existentes.</p>
  `;
  const query = element.querySelector("[data-query]");
  const filters = [...element.querySelectorAll("[data-filter]")];
  const execute = element.querySelector("[data-execute]");
  const status = element.querySelector(".auto-merge-status");
  const progress = createJobProgress();
  element.querySelector(".auto-merge-toolbar").after(progress.element);
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
      return matchesLevel1Filter(row, selectedFilter);
    });
    for (const button of filters) {
      const active = button.dataset.filter === selectedFilter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    status.textContent = "";
    status.hidden = true;
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
    results.append(createTable(columns, selection.rows, "Resultados registrados do Auto-Merge Nível I", {
      emptyMessage: state.chapters.length ? "Nenhum resultado para este filtro." : "Nenhum capítulo com imagens encontrado.",
    }));
    if (rows.length) results.append(createPaginationControls(selection, (delta) => {
        pagination.move(delta);
        draw();
      }));
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
    await onExecute?.([...selectedChapters]);
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
    setExecution(next) {
      execute.disabled = next.busy;
      progress.update(next);
    },
    clearSelection() {
      selectedChapters.clear();
      draw();
    },
    dispose() {
      query.removeEventListener("input", resetAndDraw);
      filters.forEach((button) => button.removeEventListener("click", selectFilter));
      execute.removeEventListener("click", requestExecution);
    },
  };
}
