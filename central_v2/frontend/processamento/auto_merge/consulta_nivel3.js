import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createLevel3Columns } from "/processamento/auto_merge/residuos_nivel3.js";

export function createLevel3View({ onExecute } = {}) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level3";
  element.innerHTML = `
    <header><h1>Auto-Merge Nível III</h1><p class="auto-merge-subtitle">Análise estrutural dos resíduos seguros que vieram do Nível II.</p></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span>
        <input type="search" data-query placeholder="Buscar capítulo..."></label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos">
        <button class="active" type="button" aria-pressed="true">Pendentes</button></div>
      <button class="auto-merge-execute" type="button" data-execute>Executar Nível III</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>`;
  const query = element.querySelector("[data-query]");
  const status = element.querySelector(".auto-merge-status");
  const execute = element.querySelector("[data-execute]");
  const results = element.querySelector(".auto-merge-results");
  const pagination = createPagination();
  const selectedChapters = new Set();
  const progress = createJobProgress("Auto-Merge Nível III");
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [], manga: null };

  function draw() {
    results.replaceChildren();
    element.setAttribute("aria-busy", String(state.status === "loading"));
    status.hidden = false;
    if (state.status === "idle") status.textContent = "Selecione um provider e uma obra para consultar os resíduos.";
    else if (state.status === "loading") status.textContent = `Consultando ${state.manga}…`;
    else if (state.status === "error") status.textContent = state.error;
    else {
      const term = query.value.trim().toLocaleLowerCase("pt-BR");
      const rows = state.chapters.filter((row) => row.chapter.toLocaleLowerCase("pt-BR").includes(term));
      status.textContent = rows.length ? "" : "Nenhum capítulo com residual elegível do Nível II.";
      status.hidden = rows.length > 0;
      const selection = pagination.select(rows);
      const current = selection.rows.map((row) => row.chapter);
      if (rows.length) results.append(
        createTable(createLevel3Columns({
          selected: { chapters: selectedChapters,
            pageSelected: current.length > 0 && current.every((chapter) => selectedChapters.has(chapter)) },
          onSelect: (chapter, checked) => { checked ? selectedChapters.add(chapter) : selectedChapters.delete(chapter); draw(); },
          onSelectPage: (checked) => { current.forEach((chapter) => checked ? selectedChapters.add(chapter) : selectedChapters.delete(chapter)); draw(); },
        }), selection.rows, "Resíduos aguardando Auto-Merge Nível III"),
        createPaginationControls(selection, (delta) => { pagination.move(delta); draw(); }),
      );
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
        query.value = ""; selectedChapters.clear(); pagination.reset();
      }
      state = next;
      draw();
    },
    setExecution(next) { progress.update(next); state = { ...state, ...next }; draw(); },
    clearSelection() { selectedChapters.clear(); draw(); },
    dispose() { query.removeEventListener("input", resetAndDraw); execute.removeEventListener("click", handleExecute); },
  };
}
