import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createLevel3Columns } from "/processamento/auto_merge/shared/residuos_niveis_3_a_5.js";
import { createStatusFilters, matchesStatus } from "/processamento/auto_merge/shared/filtros_estado.js";

export function createLevel4View({ onExecute } = {}) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level4 auto-merge-level3";
  element.innerHTML = `<header><h1 title="Composição estrutural global dos resíduos válidos recebidos do Nível III.">Auto-Merge Nível IV</h1></header>
    <div class="auto-merge-toolbar"><label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span><input type="search" data-query placeholder="Buscar cap."></label>
    <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos por estado"></div>
    <button class="auto-merge-execute" type="button" data-execute>Executar Nível IV</button></div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p><div class="auto-merge-results"></div>`;
  const query = element.querySelector("[data-query]"), status = element.querySelector(".auto-merge-status");
  const execute = element.querySelector("[data-execute]"), results = element.querySelector(".auto-merge-results");
  const filters = element.querySelector(".auto-merge-filters");
  const pagination = createPagination(), selected = new Set(), progress = createJobProgress("Auto-Merge Nível IV");
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [], manga: null };
  let selectedFilter = "all";
  function draw() {
    results.replaceChildren(); element.setAttribute("aria-busy", String(state.status === "loading")); status.hidden = false;
    if (state.status === "idle") status.textContent = "Selecione um provider e uma obra para consultar os resíduos.";
    else if (state.status === "loading") status.textContent = `Consultando ${state.manga}…`;
    else if (state.status === "error") status.textContent = state.error;
    else {
      const term = query.value.trim().toLocaleLowerCase("pt-BR");
      createStatusFilters(filters, { chapters: state.chapters, value: selectedFilter,
        onChange: (value) => { selectedFilter = value; pagination.reset(); draw(); } });
      const rows = state.chapters.filter((row) => row.chapter.toLocaleLowerCase("pt-BR").includes(term) && matchesStatus(row, selectedFilter));
      status.textContent = ""; status.hidden = true;
      const selection = pagination.select(rows), current = selection.rows.filter((row) => row.eligible !== false).map((row) => row.chapter);
      const columns = createLevel3Columns({ selected: { chapters: selected, eligibleChapters: current, pageSelected: current.length > 0 && current.every((name) => selected.has(name)) },
        onSelect: (name, checked) => { checked ? selected.add(name) : selected.delete(name); draw(); },
        onSelectPage: (checked) => { current.forEach((name) => checked ? selected.add(name) : selected.delete(name)); draw(); },
      });
      results.append(createTable(columns, selection.rows, "Resíduos aguardando Auto-Merge Nível IV", { emptyMessage: "Nenhum capítulo disponível para o Nível IV." }));
      if (rows.length) results.append(createPaginationControls(selection, (delta) => { pagination.move(delta); draw(); }));
    }
    execute.disabled = state.busy || selected.size === 0;
  }
  const reset = () => { pagination.reset(); draw(); }, handleExecute = () => onExecute?.([...selected]);
  query.addEventListener("input", reset); execute.addEventListener("click", handleExecute);
  return { element, update(next) { if (state.provider !== next.provider || state.manga !== next.manga) { query.value = ""; selectedFilter = "all"; selected.clear(); pagination.reset(); } state = next; draw(); },
    setExecution(next) { progress.update(next); state = { ...state, ...next }; draw(); }, clearSelection() { selected.clear(); draw(); },
    dispose() { query.removeEventListener("input", reset); execute.removeEventListener("click", handleExecute); } };
}
