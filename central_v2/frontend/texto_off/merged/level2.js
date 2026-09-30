import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergedTextoff } from "/_app/api/textoff.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createMergedExecution } from "/texto_off/merged/execution.js";

const FILTERS = [
  ["all", "Todos"], ["pending", "Pendentes"], ["processed", "Processados"],
  ["unchanged", "Sem alteração"], ["none", "Sem candidatos"],
  ["missing", "Atualizar Nível I"], ["invalid", "MERGE inválido"],
];

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
    { id: "chapter", label: "Cap.", render: (row) => row.chapter },
    { id: "merges", label: "Merges", render: (row) => row.merge_valid ? row.merge_count : "—" },
    { id: "candidates", label: "Candidatas Nível II", render: (row) => row.cleaned ? `${row.transparent_page_count} / ${row.merge_count}` : "—" },
    { id: "balloons", label: "Balões transp.", render: (row) => row.cleaned ? row.transparent_balloons : "—" },
    { id: "residue", label: "Resíduos adiados", render: (row) => row.cleaned ? row.deferred_components : "—" },
    { id: "pages-with-text", label: "Pág. com texto", render: (row) => ["processed", "no_change"].includes(row.level2_status) ? row.level2_pages_with_text : "—" },
    { id: "changed-pixels", label: "Pixels alterados", render: (row) => ["processed", "no_change"].includes(row.level2_status) ? row.level2_changed_pixels : "—" },
    {
      id: "textoff-status",
      label: "Situação",
      render: (row) => ({
        pending: "Pendente para Nível II",
        processed: "Nível II concluído",
        no_change: "Sem alteração — revisar resultado",
        no_candidates: "Sem candidatos",
        missing_level1: "Atualize o Nível I",
        invalid_merge: "MERGE inválido",
      })[row.level2_status] || "—",
      className: (row) => `textoff-status ${["pending", "no_change"].includes(row.level2_status) ? "is-pending" : row.level2_status === "invalid_merge" ? "is-invalid" : "is-done"}`,
    },
  ];
}

export function createMergedLevel2View(onRun) {
  const element = document.createElement("section");
  element.className = "auto-merge-page auto-merge-level2 textoff-merged-page textoff-merged-level2-page";
  element.innerHTML = `
    <header><h1 title="Casos transparentes adiados pelo Nível I, preparados para a rodada específica do Nível II.">Texto Off — Merged Nível II</h1></header>
    <p class="textoff-level-description">Acompanha os balões transparentes preservados pelo Nível I e prepara a rodada especializada. O refinamento do Legado não é aplicado aqui.</p>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span><input type="search" data-query placeholder="Buscar capítulo..."></label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos"></div>
      <button class="auto-merge-execute" type="button" data-execute>Executar Nível II</button>
    </div>
    <p class="auto-merge-status" role="status" aria-live="polite"></p>
    <div class="auto-merge-results"></div>
  `;
  const query = element.querySelector("[data-query]");
  const filters = element.querySelector(".auto-merge-filters");
  const status = element.querySelector(".auto-merge-status");
  const results = element.querySelector(".auto-merge-results");
  const execute = element.querySelector("[data-execute]");
  const pagination = createPagination();
  const selected = new Set();
  const progress = createJobProgress("Texto Off — Merged Nível II");
  element.querySelector(".auto-merge-toolbar").after(progress.element);
  let state = { status: "idle", chapters: [] };
  let selectedFilter = "pending";
  let executionBusy = false;

  function match(row, filter = selectedFilter) {
    return filter === "all" || row.level2_status === ({pending: "pending", processed: "processed",
      unchanged: "no_change", none: "no_candidates", missing: "missing_level1", invalid: "invalid_merge"})[filter];
  }

  function draw() {
    filters.replaceChildren();
    for (const [key, label] of FILTERS) {
      const button = document.createElement("button");
      const count = state.chapters.filter((row) => match(row, key)).length;
      button.type = "button";
      button.textContent = `${label} (${count})`;
      button.classList.toggle("active", selectedFilter === key);
      button.setAttribute("aria-pressed", String(selectedFilter === key));
      button.addEventListener("click", () => { selectedFilter = key; pagination.reset(); draw(); });
      filters.append(button);
    }

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
    clearSelection() { selected.clear(); draw(); },
    dispose() { query.removeEventListener("input", onQuery); execute.removeEventListener("click", handleExecute); },
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
    onComplete: async () => { view.clearSelection(); await load(); },
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
