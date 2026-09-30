import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createLevel3Columns } from "/processamento/auto_merge/shared/residuos_niveis_3_a_5.js";
import { createStatusFilters, matchesStatus } from "/processamento/auto_merge/shared/filtros_estado.js";

export function createLevel3View({ onExecute } = {}) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level3";
  element.innerHTML = `
    <header><h1 title="Análise estrutural dos resíduos seguros recebidos do Nível II.">Auto-Merge Nível III</h1></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span>
        <input type="search" data-query placeholder="Buscar cap."></label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos por estado"></div>
      <button class="auto-merge-execute" type="button" data-execute>Executar Nível III</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>`;
  const query = element.querySelector("[data-query]");
  const status = element.querySelector(".auto-merge-status");
  const execute = element.querySelector("[data-execute]");
  const results = element.querySelector(".auto-merge-results");
  const filters = element.querySelector(".auto-merge-filters");
  const pagination = createPagination();
  const selectedChapters = new Set();
  const progress = createJobProgress("Auto-Merge Nível III");
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [], manga: null };
  let selectedFilter = "all";

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
      const current = selection.rows.filter((row) => row.eligible !== false).map((row) => row.chapter);
      const columns = createLevel3Columns({
          selected: { chapters: selectedChapters, eligibleChapters: current,
            pageSelected: current.length > 0 && current.every((chapter) => selectedChapters.has(chapter)) },
          onSelect: (chapter, checked) => { checked ? selectedChapters.add(chapter) : selectedChapters.delete(chapter); draw(); },
          onSelectPage: (checked) => { current.forEach((chapter) => checked ? selectedChapters.add(chapter) : selectedChapters.delete(chapter)); draw(); },
        });
      results.append(createTable(columns, selection.rows, "Resíduos aguardando Auto-Merge Nível III", {
        emptyMessage: "Nenhum capítulo disponível para o Nível III.",
      }));
      if (rows.length) results.append(createPaginationControls(selection, (delta) => { pagination.move(delta); draw(); }));
    }
    execute.disabled = state.busy || selectedChapters.size === 0;
  }

  function resetAndDraw() { pagination.reset(); draw(); }
  const handleExecute = () => onExecute?.([...selectedChapters]);
  query.addEventListener("input", resetAndDraw);
  execute.addEventListener("click", handleExecute);
  return {
    element,
    update(next) {
      if (state.provider !== next.provider || state.manga !== next.manga) {
        query.value = ""; selectedFilter = "all"; selectedChapters.clear(); pagination.reset();
      }
      state = next;
      draw();
    },
    setExecution(next) { progress.update(next); state = { ...state, ...next }; draw(); },
    clearSelection() { selectedChapters.clear(); draw(); },
    dispose() { query.removeEventListener("input", resetAndDraw); execute.removeEventListener("click", handleExecute); },
  };
}
