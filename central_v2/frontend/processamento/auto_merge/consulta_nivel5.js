import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createLevel3Columns } from "/processamento/auto_merge/residuos_nivel3.js";

export function createLevel5View({ onExecute } = {}) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level5 auto-merge-level3";
  element.innerHTML = `<header><h1>Auto-Merge Nível V</h1><p class="auto-merge-subtitle">Busca global SAFE nos resíduos dirigidos do Nível IV; o restante segue para revisão.</p></header>
    <div class="auto-merge-toolbar"><label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span><input type="search" data-query placeholder="Buscar capítulo..."></label>
    <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos"><button class="active" type="button" aria-pressed="true">Pendentes</button></div>
    <button class="auto-merge-execute" type="button" data-execute>Executar Nível V</button></div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p><div class="auto-merge-results"></div>`;
  const query = element.querySelector("[data-query]"), status = element.querySelector(".auto-merge-status");
  const execute = element.querySelector("[data-execute]"), results = element.querySelector(".auto-merge-results");
  const pagination = createPagination(), selected = new Set(), progress = createJobProgress("Auto-Merge Nível V");
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [], manga: null };
  function draw() {
    results.replaceChildren(); element.setAttribute("aria-busy", String(state.status === "loading")); status.hidden = false;
    if (state.status === "idle") status.textContent = "Selecione um provider e uma obra para consultar os resíduos.";
    else if (state.status === "loading") status.textContent = `Consultando ${state.manga}…`;
    else if (state.status === "error") status.textContent = state.error;
    else {
      const term = query.value.trim().toLocaleLowerCase("pt-BR");
      const rows = state.chapters.filter((row) => row.chapter.toLocaleLowerCase("pt-BR").includes(term));
      status.textContent = rows.length ? "" : "Nenhum capítulo com residual elegível do Nível IV dirigido."; status.hidden = rows.length > 0;
      const selection = pagination.select(rows), current = selection.rows.map((row) => row.chapter);
      if (rows.length) results.append(createTable(createLevel3Columns({ selected: { chapters: selected, pageSelected: current.length > 0 && current.every((name) => selected.has(name)) },
        onSelect: (name, checked) => { checked ? selected.add(name) : selected.delete(name); draw(); },
        onSelectPage: (checked) => { current.forEach((name) => checked ? selected.add(name) : selected.delete(name)); draw(); },
      }), selection.rows, "Resíduos aguardando Auto-Merge Nível V"), createPaginationControls(selection, (delta) => { pagination.move(delta); draw(); }));
    }
    execute.disabled = state.busy || selected.size === 0;
  }
  const reset = () => { pagination.reset(); draw(); }, handleExecute = () => onExecute?.([...selected]);
  query.addEventListener("input", reset); execute.addEventListener("click", handleExecute);
  return { element, update(next) { if (state.provider !== next.provider || state.manga !== next.manga) { query.value = ""; selected.clear(); pagination.reset(); } state = next; draw(); },
    setExecution(next) { progress.update(next); state = { ...state, ...next }; draw(); }, clearSelection() { selected.clear(); draw(); },
    dispose() { query.removeEventListener("input", reset); execute.removeEventListener("click", handleExecute); } };
}
