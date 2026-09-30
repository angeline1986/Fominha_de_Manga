import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createLevel2Columns } from "/processamento/auto_merge/shared/residuos_nivel2.js";
import { createStatusFilters, matchesStatus } from "/processamento/auto_merge/shared/filtros_estado.js";

export function createLevel2View({ onExecute } = {}) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level2";
  element.innerHTML = `
    <header><h1 title="Processa os resíduos recebidos do Nível I em busca de divisões seguras.">Auto-Merge Nível II</h1></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search">
        <span class="visually-hidden">Buscar capítulo</span>
        <input type="search" data-query placeholder="Buscar cap.">
      </label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos por estado"></div>
      <button class="auto-merge-execute" type="button" data-execute>Executar Nível II</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>
  `;
  const query = element.querySelector("[data-query]");
  const status = element.querySelector(".auto-merge-status");
  const execute = element.querySelector("[data-execute]");
  const results = element.querySelector(".auto-merge-results");
  const filters = element.querySelector(".auto-merge-filters");
  const pagination = createPagination();
  const selectedChapters = new Set();
  const progress = createJobProgress("Auto-Merge Nível II");
  const handleExecute = () => onExecute?.([...selectedChapters]);
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [], manga: null };
  let selectedFilter = "pending";

  function draw() {
    results.replaceChildren();
    element.setAttribute("aria-busy", String(state.status === "loading"));
    status.hidden = false;
    if (state.status === "idle") status.textContent = "Selecione um provider e uma obra para consultar os resíduos.";
    else if (state.status === "loading") status.textContent = `Consultando ${state.manga}…`;
    else if (state.status === "error") status.textContent = state.error;
    else {
      const term = query.value.trim().toLocaleLowerCase("pt-BR");
      createStatusFilters(filters, { chapters: state.chapters, value: selectedFilter,
        onChange: (value) => { selectedFilter = value; pagination.reset(); draw(); } });
      const rows = state.chapters.filter((row) => row.chapter.toLocaleLowerCase("pt-BR").includes(term) && matchesStatus(row, selectedFilter));
      status.textContent = "";
      status.hidden = true;
      const selection = pagination.select(rows);
      const currentPage = selection.rows.filter((row) => row.eligible !== false).map((row) => row.chapter);
      const columns = createLevel2Columns({
          selected: { chapters: selectedChapters, eligibleChapters: currentPage,
            pageSelected: currentPage.length > 0 && currentPage.every((chapter) => selectedChapters.has(chapter)) },
          onSelect: (chapter, checked) => {
            if (checked) selectedChapters.add(chapter);
            else selectedChapters.delete(chapter);
            draw();
          },
          onSelectPage: (checked) => {
            currentPage.forEach((chapter) => checked ? selectedChapters.add(chapter) : selectedChapters.delete(chapter));
            draw();
          },
        });
      results.append(createTable(columns, selection.rows, "Resíduos aguardando Auto-Merge Nível II", {
        emptyMessage: "Nenhum capítulo disponível para o Nível II.",
      }));
      if (rows.length) results.append(createPaginationControls(selection, (delta) => {
          pagination.move(delta);
          draw();
        }));
    }
    execute.disabled = state.busy || selectedChapters.size === 0;
  }

  function resetAndDraw() {
    pagination.reset();
    draw();
  }
  query.addEventListener("input", resetAndDraw);
  execute.addEventListener("click", handleExecute);
  return {
    element,
    update(next) {
      if (state.provider !== next.provider || state.manga !== next.manga) {
        query.value = "";
        selectedFilter = "pending";
        selectedChapters.clear();
        pagination.reset();
      }
      state = next;
      draw();
    },
    setExecution(next) { progress.update(next); state = { ...state, ...next }; draw(); },
    clearSelection() { selectedChapters.clear(); draw(); },
    dispose() {
      query.removeEventListener("input", resetAndDraw);
      execute.removeEventListener("click", handleExecute);
    },
  };
}
