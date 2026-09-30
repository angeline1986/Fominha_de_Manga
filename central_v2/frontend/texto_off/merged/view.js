import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createMergedColumns } from "/texto_off/merged/columns.js";

const FILTERS = [
  ["all", "Todos"], ["pending", "Sem resultado"],
  ["processed", "Com resultado"], ["invalid", "MERGE inválido"],
];

export function createMergedView(onExecute, { title = "Texto Off — Merged", mode, description = "", onInspect } = {}) {
  const element = document.createElement("section");
  element.className = "auto-merge-page textoff-merged-page";
  element.innerHTML = `
    <header><h1 title="Executa Cleaner V2 sobre os artefatos do MERGE oficial.">${title}</h1></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span><input type="search" data-query placeholder="Buscar capítulo..."></label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos"></div>
      <button class="auto-merge-execute" type="button" data-execute>Executar ${title.replace("Texto Off — ", "")}</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>
  `;
  const query = element.querySelector("[data-query]");
  if (description) {
    const note = document.createElement("p");
    note.className = "textoff-level-description";
    note.textContent = description;
    element.querySelector("header").after(note);
  }
  const status = element.querySelector(".auto-merge-status");
  const execute = element.querySelector("[data-execute]");
  const results = element.querySelector(".auto-merge-results");
  const filters = element.querySelector(".auto-merge-filters");
  const pagination = createPagination();
  const selected = new Set();
  const progress = createJobProgress(title);
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [], manga: null, busy: false };
  let selectedFilter = "pending";

  function matches(row) {
    return selectedFilter === "all"
      || (selectedFilter === "pending" && row.selectable && !row.cleaned)
      || (selectedFilter === "processed" && row.cleaned)
      || (selectedFilter === "invalid" && !row.selectable);
  }

  function drawFilters() {
    filters.replaceChildren();
    for (const [key, label] of FILTERS) {
      const button = document.createElement("button");
      button.className = "auto-merge-filter-button";
      const count = state.chapters.filter((row) => {
        if (key === "all") return true;
        if (key === "pending") return row.selectable && !row.cleaned;
        if (key === "processed") return row.cleaned;
        return !row.selectable;
      }).length;
      button.type = "button";
      button.textContent = `${label} (${count})`;
      button.classList.toggle("active", key === selectedFilter);
      button.setAttribute("aria-pressed", String(key === selectedFilter));
      button.addEventListener("click", () => { selectedFilter = key; pagination.reset(); draw(); });
      filters.append(button);
    }
  }

  function draw() {
    results.replaceChildren();
    element.setAttribute("aria-busy", String(state.status === "loading"));
    if (state.status === "idle") status.textContent = "Selecione uma obra para consultar os MERGEs oficiais.";
    else if (state.status === "loading") status.textContent = `Consultando ${state.manga}…`;
    else if (state.status === "error") status.textContent = state.error;
    else status.textContent = "";
    status.hidden = state.status === "ready";
    drawFilters();
    const term = query.value.trim().toLocaleLowerCase("pt-BR");
    const rows = state.chapters.filter((row) => row.chapter.toLocaleLowerCase("pt-BR").includes(term) && matches(row));
    const selection = pagination.select(rows);
    const pageChapters = selection.rows.map((row) => row.chapter);
    const columns = createMergedColumns({
      rows: selection.rows, selected, pageChapters,
      mode,
      onInspect,
      onSelect: (chapter, checked) => { checked ? selected.add(chapter) : selected.delete(chapter); draw(); },
      onSelectPage: (checked) => {
        selection.rows.filter((row) => row.selectable).forEach((row) => checked ? selected.add(row.chapter) : selected.delete(row.chapter));
        draw();
      },
    });
    results.append(createTable(columns, selection.rows, `Capítulos para ${title}`, {
      emptyMessage: state.status === "ready" ? "Nenhum capítulo corresponde ao filtro." : "",
    }));
    if (rows.length) results.append(createPaginationControls(selection, (delta) => { pagination.move(delta); draw(); }));
    execute.disabled = state.busy || selected.size === 0;
  }

  function resetAndDraw() { pagination.reset(); draw(); }
  function handleExecute() { onExecute?.([...selected]); }
  query.addEventListener("input", resetAndDraw);
  execute.addEventListener("click", handleExecute);
  return {
    element,
    update(next) {
      if (state.provider !== next.provider || state.manga !== next.manga) {
        query.value = ""; selectedFilter = "pending"; selected.clear(); pagination.reset();
      }
      state = { ...next, busy: state.busy };
      draw();
    },
    setExecution(job) { state.busy = Boolean(job.busy); progress.update(job); draw(); },
    clearSelection() { selected.clear(); draw(); },
    inspect(chapter) {
      const row = state.chapters.find((item) => item.chapter === String(chapter));
      if (row) onInspect?.(row);
    },
    dispose() {
      query.removeEventListener("input", resetAndDraw);
      execute.removeEventListener("click", handleExecute);
    },
  };
}
