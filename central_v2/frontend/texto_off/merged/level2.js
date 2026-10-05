import { createComparisonLauncher } from "/texto_off/comparison/launcher.js";
import { matchesOutcome, drawOutcomeFilters } from "/texto_off/merged/outcome_filters.js";
import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergedTextoff } from "/_app/api/textoff.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createMergedExecution } from "/texto_off/merged/execution.js";
import { createOutcomeColumns } from "/texto_off/merged/outcome_columns.js";

function checkbox(label, checked, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = checked;
  input.setAttribute("aria-label", label);
  input.addEventListener("change", () => onChange(input.checked));
  return input;
}

function makeColumns({ rows, selected, pageChapters, onSelect, onSelectPage }) {
  const eligible = pageChapters.filter((chapter) => rows.find((row) => row.chapter === chapter)?.selectable);
  return [
    {
      id: "select",
      header: () => {
        const input = checkbox("Selecionar todos os capítulos elegíveis desta página",
          eligible.length > 0 && eligible.every((name) => selected.has(name)), onSelectPage);
        input.disabled = eligible.length === 0;
        return input;
      },
      render: (row) => {
        const input = checkbox(`Selecionar capítulo ${row.chapter}`, selected.has(row.chapter),
          (checked) => onSelect(row.chapter, checked));
        input.disabled = !row.selectable;
        return input;
      },
    },
    { id: "chapter", label: "Capítulo", render: (row) => row.chapter },
    ...createOutcomeColumns(),
  ];
}

export function createMergedLevel2View(onRun) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level2 textoff-merged-page textoff-merged-level2-page cleaner-outcomes";
  element.innerHTML = `
    <header><h1 class="textoff-page-title-hint" data-tooltip="Tratamento focado em páginas com balões transparentes." tabindex="0" aria-description="Tratamento focado em páginas com balões transparentes.">Auto-Cleaner — Passo 2: Balões Transparentes</h1></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span><input type="search" data-query placeholder="Buscar capítulo"></label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos"></div>
      <button class="auto-merge-execute" type="button" data-execute>Executar Passo 2</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>
  `;
  const query = element.querySelector("[data-query]");
  const filters = element.querySelector(".auto-merge-filters");
  const status = element.querySelector(".auto-merge-status");
  const results = element.querySelector(".auto-merge-results");
  const execute = element.querySelector("[data-execute]");
  const comparison = createComparisonLauncher(element, "2", "level2");
  const pagination = createPagination();
  const selected = new Set();
  const progress = createJobProgress("Texto Off — Merged Nível II");
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [] };
  let selectedFilter = "pending";
  let executionBusy = false;

  function match(row, filter = selectedFilter) {
    return matchesOutcome(row, filter);
  }

  function draw() {
    drawOutcomeFilters(filters, state.chapters, selectedFilter, (key) => {
      selectedFilter = key; pagination.reset(); draw();
    });

    if (state.status === "idle") status.textContent = "Selecione uma obra para consultar os resultados do Nível I.";
    else if (state.status === "loading") status.textContent = `Consultando ${state.manga}…`;
    else if (state.status === "error") status.textContent = state.error;
    else status.textContent = "";
    status.hidden = state.status === "ready";
    element.setAttribute("aria-busy", String(state.status === "loading"));

    const term = query.value.trim().toLocaleLowerCase("pt-BR");
    const rows = state.chapters.filter((row) => row.chapter.toLocaleLowerCase("pt-BR").includes(term) && match(row));
    const page = pagination.select(rows);
    const pageChapters = page.rows.map((row) => row.chapter);
    const columns = makeColumns({
      rows: page.rows, selected, pageChapters,
      onSelect: (chapter, checked) => { checked ? selected.add(chapter) : selected.delete(chapter); draw(); },
      onSelectPage: (checked) => {
        eligibleRows().filter((row) => pageChapters.includes(row.chapter))
          .forEach((row) => checked ? selected.add(row.chapter) : selected.delete(row.chapter));
        draw();
      },
    });
    columns.push(comparison.column);
    results.replaceChildren(createTable(columns, page.rows, "Casos para Texto Off Merged Nível II", {
      emptyMessage: state.status === "ready" ? "Nenhum capítulo corresponde ao filtro." : "",
    }));
    if (rows.length) results.append(createPaginationControls(page, (delta) => { pagination.move(delta); draw(); }));
    execute.disabled = executionBusy || selected.size === 0;
  }

  function eligibleRows() { return state.chapters.filter((row) => row.selectable); }

  const onQuery = () => { pagination.reset(); draw(); };
  const handleExecute = () => onRun?.([...selected]);
  query.addEventListener("input", onQuery);
  execute.addEventListener("click", handleExecute);
  draw();
  return {
    element,
    update(next) {
      if (state.provider !== next.provider || state.manga !== next.manga) {
        query.value = "";
        selectedFilter = "pending";
        selected.clear();
        pagination.reset();
      }
      state = next;
      draw();
    },
    setExecution(job) { executionBusy = Boolean(job.busy); progress.update(job); draw(); },
    completeSuccessfulExecution() {
      selected.clear();
      selectedFilter = "all";
      pagination.reset();
    },
    dispose() { comparison.dispose(); query.removeEventListener("input", onQuery); execute.removeEventListener("click", handleExecute); },
  };
}

export function render(container) {
  let requestId = 0;
  let controller;
  let disposed = false;
  let execution;
  const view = createMergedLevel2View((chapters) => execution.execute(chapters));
  container.replaceChildren(view.element);
  execution = createMergedExecution({
    level: "2",
    onStatus: view.setExecution,
    onComplete: async () => { view.completeSuccessfulExecution(); await load(); },
  });
  async function load() {
    const id = ++requestId;
    controller?.abort();
    controller = new AbortController();
    const { provider, manga } = getContext();
    if (!provider || !manga) return view.update({ status: "idle", provider, manga, chapters: [] });
    view.update({ status: "loading", provider, manga, chapters: [] });
    try {
      const result = await fetchMergedTextoff(provider, manga, controller.signal, "2");
      if (!disposed && id === requestId) view.update({ status: "ready", ...result });
    } catch (error) {
      if (!disposed && id === requestId && error.name !== "AbortError") {
        view.update({ status: "error", provider, manga, chapters: [], error: error.message });
      }
    }
  }
  const unsubscribe = subscribeContext(load);
  load();
  return () => { disposed = true; requestId += 1; controller?.abort(); unsubscribe(); execution.dispose(); view.dispose(); };
}
