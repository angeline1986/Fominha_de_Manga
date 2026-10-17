import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls, createPageSizeControl } from "/_shared/pagination/pagination.js";
import { comboState, resultSummary, stageState, MAX_CHAPTERS } from "/texto_off/combo_turbo/model.js";
import { canExecute, isSelectable, progressPresentation, resultVisible } from "/texto_off/combo_turbo/behavior.js";

const labels = { REUSED: "Reutilizável", PLANNED: "Pendente", BLOCKED: "Bloqueado",
  ELIGIBLE: "Elegível",
  NO_WORK: "Sem trabalho", RUNNING: "Executando", COMPLETED: "Concluído",
  FAILED: "Falha", PARTIAL: "Parcial", INTERRUPTED: "Interrompido", QUEUED: "Na fila" };
labels.UNKNOWN = "Planeje para consultar";
const stages = { PREPARING: "Preparando", SOLIDOS: "Sólidos", GLASS: "Glass",
  COMPOSING: "Composição", VALIDATING: "Validando", PUBLISHING_ISOLATED: "Publicação isolada",
  COMPLETED: "Concluído", FAILED: "Falha", INTERRUPTED: "Interrompido" };
const jobStatus = { queued: "Na fila", running: "Executando", completed: "Concluído",
  partial: "Parcial", blocked: "Bloqueado", failed: "Falha", no_work: "Sem trabalho",
  interrupted: "Interrompido" };
const cell = (status) => {
  const value = document.createElement("span");
  value.className = `combo-state combo-state--${String(status || "unknown").toLowerCase()}`;
  value.textContent = labels[status] || status || "Aguardando plano";
  return value;
};

export function createComboView(callbacks) {
  const element = document.createElement("section");
  element.className = "auto-merge-page combo-turbo-page";
  element.innerHTML = `<header><h1>Combo Turbo</h1><p>Execução automática: Sólidos + Glass</p>
      <small data-context></small><small class="combo-isolation-note">Execução e publicação somente na cópia isolada.</small></header>
    <div class="auto-merge-toolbar"><label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span>
      <input data-search type="search" placeholder="Buscar capítulo"></label>
      <label class="combo-filter-label">Situação: <select data-filter aria-label="Filtrar por situação">
        <option value="all">Todas</option><option value="eligible">Elegíveis</option>
        <option value="blocked">Bloqueados</option><option value="no-work">Sem trabalho</option>
      </select></label><button class="combo-secondary" data-refresh type="button">Atualizar</button></div>
    <p class="combo-message" data-message role="status" aria-live="polite"></p>
    <div class="combo-summary" data-summary></div>
    <div class="combo-select-all"><button class="combo-secondary" data-select-eligible type="button">Selecionar elegíveis</button></div>
    <div class="combo-table" data-table></div>
    <div class="combo-selection"><span data-selected></span>
      <div class="combo-actions"><button class="combo-secondary" data-plan type="button">Planejar</button>
        <button class="auto-merge-execute combo-run" data-run type="button">Executar</button></div></div>
    <section class="combo-current" data-current hidden><h2>Execução atual</h2>
      <div class="combo-current-meta" data-current-meta></div><progress data-progress aria-label="Progresso do job Combo"></progress>
      <p data-progress-text></p></section>
    <section class="combo-results" data-results hidden><h2>Resultados</h2>
      <p data-result-summary></p><div data-result-rows></div><p data-publication></p></section>`;
  const search = element.querySelector("[data-search]");
  const filter = element.querySelector("[data-filter]");
  const tableRoot = element.querySelector("[data-table]");
  let pagination = createPagination();
  const pageSize = createPageSizeControl((size) => { pagination = createPagination(size); draw(); });
  let state = { rows: [], selected: new Set(), page: 0, busy: false, planValid: false };

  function visibleRows() {
    const term = search.value.trim().toLocaleLowerCase("pt-BR");
    return state.rows.filter((row) => {
      const status = comboState(row);
      const statusMatch = filter.value === "all" || filter.value === "eligible" && status === "PLANNED"
        || filter.value === "blocked" && status === "BLOCKED"
        || filter.value === "no-work" && status === "NO_WORK";
      return statusMatch && String(row.chapter).toLocaleLowerCase("pt-BR").includes(term);
    });
  }

  function draw() {
    const selected = state.selected;
    const visible = visibleRows();
    const selection = pagination.select(visible);
    const current = selection.rows;
    const selectedEligible = current.filter((row) => comboState(row) === "PLANNED").map((row) => row.chapter);
    const columns = [
      { id: "select", header: () => checkbox("Selecionar elegíveis desta página",
        selectedEligible.length > 0 && selectedEligible.every((chapter) => selected.has(chapter)),
        state.busy || !selectedEligible.length, (checked) => callbacks.selectMany(selectedEligible, checked)),
        render: (row) => checkbox(`Selecionar capítulo ${row.chapter}`, selected.has(row.chapter),
          state.busy || !isSelectable(row), (checked) => callbacks.select(row.chapter, checked)) },
      { id: "chapter", label: "CAPÍTULO", render: (row) => String(row.chapter) },
      { id: "solids", label: "SÓLIDOS", render: (row) => cell(stageState(row, "SOLIDOS")) },
      { id: "glass", label: "GLASS", render: (row) => cell(stageState(row, "GLASS")) },
      { id: "combo", label: "COMBO", render: (row) => {
        const status = comboState(row), mark = cell(status === "PLANNED" ? "ELIGIBLE" : status);
        const reasons = [...new Set([...(row.reasons || []), ...(row.pages || []).flatMap((page) =>
          [...(page.stages?.SOLIDOS?.reasons || []), ...(page.stages?.GLASS?.reasons || [])])])];
        if (reasons.length) mark.title = reasons.join(" · ");
        return mark;
      } },
    ];
    tableRoot.replaceChildren(createTable(columns, current, "Elegibilidade do Combo Turbo", {
      emptyMessage: state.loading ? "Consultando elegibilidade…" : "Nenhum capítulo corresponde ao filtro.",
    }), createPaginationControls(selection, (delta) => { pagination.move(delta); draw(); },
      { leading: pageSize.element }));
    const summary = summarizeRows(state.rows);
    element.querySelector("[data-context]").textContent = state.provider && state.manga
      ? `${state.provider} · ${state.manga}` : "Selecione provider e obra na navegação.";
    element.querySelector("[data-summary]").textContent = `Capítulos: ${summary.total}    Elegíveis: ${summary.eligible}    Bloqueados: ${summary.blocked}`;
    element.querySelector("[data-selected]").textContent = `Selecionados: ${selected.size} de ${MAX_CHAPTERS}`;
    element.querySelector("[data-plan]").disabled = state.busy || state.loading || !selected.size;
    element.querySelector("[data-run]").disabled = !canExecute(state);
    element.querySelector("[data-refresh]").disabled = state.busy || state.loading;
    element.querySelector("[data-select-eligible]").disabled = state.busy || state.loading || summary.eligible === 0;
    drawJob();
  }

  function drawJob() {
    const job = state.job;
    const current = element.querySelector("[data-current]");
    current.hidden = !job;
    if (job) {
      element.querySelector("[data-current-meta]").textContent =
        `Capítulo ${job.chapter || "—"}     Etapa: ${stages[job.stage] || job.stage || "—"}     Estado: ${jobStatus[job.status] || job.status || "—"}`;
      const progress = progressPresentation(job);
      const bar = element.querySelector("[data-progress]");
      if (progress.percent === null) bar.removeAttribute("value");
      else bar.setAttribute("value", String(progress.percent));
      element.querySelector("[data-progress-text]").textContent =
        [progress.text, job.page].filter(Boolean).join(" · ");
    }
    drawResults();
  }

  function drawResults() {
    const result = state.result;
    const section = element.querySelector("[data-results]");
    section.hidden = !resultVisible(state.job, result);
    if (section.hidden) return;
    const summary = resultSummary(result);
    element.querySelector("[data-result-summary]").textContent =
      `${summary.counts.COMPOSED} páginas compostas · ${summary.counts.NO_WORK} sem trabalho · ` +
      `${summary.counts.BLOCKED} bloqueadas · ${summary.counts.CONFLICT} conflitos · ` +
      `${summary.counts.FAILED + summary.counts.INVALID} falhas · ${summary.reused} reutilizados · ${summary.executed} executados`;
    const rows = element.querySelector("[data-result-rows]");
    rows.replaceChildren(...(result.results || []).map((chapter) => {
      const line = document.createElement("p");
      const composed = (chapter.pages || []).filter((page) => page.status === "COMPOSED").length;
      line.textContent = `Cap. ${chapter.chapter}    ${labels[chapter.status] || chapter.status}    ${composed} páginas compostas`;
      const errors = [...(chapter.errors || []), ...(chapter.pages || []).flatMap((page) =>
        (page.reasons || []).map((reason) => ({ reason })))];
      if (errors.length) {
        const details = document.createElement("details");
        const summary = document.createElement("summary"); summary.textContent = "Ver motivos";
        const text = document.createElement("p");
        text.textContent = [...new Set(errors.map((error) => error.reason || error.detail).filter(Boolean))].join(" · ");
        details.append(summary, text); line.append(" ", details);
      }
      return line;
    }));
    const publication = (result.publication || []).map((row) =>
      `Cap. ${row.chapter}: ${row.status === "ALREADY_PUBLISHED" ? "Já publicado na cópia isolada" : `Publicação isolada: ${row.status}`}`);
    element.querySelector("[data-publication]").textContent = publication.join(" · ");
  }

  element.querySelector("[data-message]").textContent = "";
  element.querySelector("[data-refresh]").addEventListener("click", callbacks.refresh);
  element.querySelector("[data-plan]").addEventListener("click", callbacks.plan);
  element.querySelector("[data-run]").addEventListener("click", callbacks.run);
  element.querySelector("[data-select-eligible]").addEventListener("click", callbacks.selectEligible);
  search.addEventListener("input", () => { pagination.reset(); draw(); });
  filter.addEventListener("change", () => { pagination.reset(); draw(); });
  return { element, update(next) { state = { ...state, ...next }; draw(); }, draw };
}

function checkbox(label, checked, disabled, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox"; input.checked = checked; input.disabled = disabled;
  input.setAttribute("aria-label", label);
  input.addEventListener("change", () => onChange(input.checked));
  return input;
}

function summarizeRows(rows) {
  const summary = { total: rows.length, eligible: 0, blocked: 0 };
  rows.forEach((row) => {
    const state = comboState(row);
    if (state === "BLOCKED") summary.blocked++;
    else if (state === "PLANNED") summary.eligible++;
  });
  return summary;
}
