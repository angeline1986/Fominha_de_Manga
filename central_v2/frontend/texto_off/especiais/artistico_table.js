import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchSpecialTreatments } from "/_app/api/textoff.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { paginationConfig } from "/_shared/pagination/config.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createComparisonLauncher } from "/texto_off/comparison/launcher.js";
import { createSpecialTreatmentExecution } from "/texto_off/especiais/special_treatment_execution.js";
import { createArtisticPreview } from "/texto_off/especiais/artistico_preview.js";
import { createArtisticRows } from "/texto_off/especiais/artistico_rows.js";
import { artisticCounts, artisticGroups, artisticKey, artisticSelected } from "/texto_off/especiais/artistico_model.js";
import { WORKLISTS, executableOccurrences, executionSelection } from "/texto_off/especiais/special_worklist_policy.js";

const FILTERS = [["all", "Todos"], ["pending", "Pendentes"], ["completed", "Concluídos"]];

export function renderSpecialWorklist(container, treatment = "estilizado") {
  const config = WORKLISTS[treatment];
  if (!config) throw new Error("Tratamento especial inválido.");
  const root = document.createElement("section");
  root.className = "auto-merge-page artistico-page";
  root.innerHTML = `<header class="artistico-heading"><h1>Pincel & Retoques <span>/ ${config.label}</span></h1>
    <p>Gerencie os tratamentos por capítulo, página e ocorrência</p></header>
    <div class="artistico-panel"><div class="artistico-toolbar">
      <label class="artistico-search"><span class="visually-hidden">Buscar capítulo, página ou ocorrência</span>
        <input type="search" data-query placeholder="Buscar capítulo, página ou ocorrência..."></label>
      <div class="artistico-filters" data-filters role="group" aria-label="Filtrar por situação"></div>
      <button class="btn artistico-execute" type="button" data-execute disabled>Executar
        <span class="artistico-execute-count" data-count hidden></span></button></div>
      <p class="artistico-message" data-status role="status" aria-live="polite"></p>
      <div class="artistico-results" data-results></div>
      <div class="artistico-footer" data-footer></div></div>`;
  container.replaceChildren(root);
  const query = root.querySelector("[data-query]");
  const filters = root.querySelector("[data-filters]");
  const results = root.querySelector("[data-results]");
  const footer = root.querySelector("[data-footer]");
  const status = root.querySelector("[data-status]");
  const execute = root.querySelector("[data-execute]");
  const count = root.querySelector("[data-count]");
  const progress = createJobProgress(`Tratamento ${config.label}`);
  root.querySelector(".artistico-toolbar").after(progress.element);
  const review = createComparisonLauncher(root, config.step, config.mode, config.mode);
  const preview = createArtisticPreview();
  const openCh = new Set(), openPages = new Set(), selected = new Set(), choices = new Map();
  const sizeLabel = document.createElement("label");
  sizeLabel.className = "artistico-page-size"; sizeLabel.textContent = "Exibir:";
  const size = document.createElement("select");
  size.setAttribute("aria-label", "Capítulos por página");
  paginationConfig.pageSizeOptions.forEach((value) =>
    size.append(new Option(String(value), String(value))));
  size.value = String(paginationConfig.pageSize); sizeLabel.append(size);
  let pagination = createPagination(), rows = [], filter = "all", phase = "idle";
  let error = "", controller, disposed = false, busy = false, initialized = false;

  function updateExecute() {
    const selection = treatment === "estilizado"
      ? { items: artisticSelected(rows, selected, choices), canExecute: true, reason: "" }
      : executionSelection(rows, treatment, selected, choices);
    execute.disabled = busy || phase !== "ready" || !selection.items.length || !selection.canExecute;
    count.textContent = String(selection.items.length);
    count.hidden = !selection.items.length;
    if (phase === "ready") {
      status.textContent = selection.reason;
      status.hidden = !selection.reason;
    }
  }
  function draw() {
    root.setAttribute("aria-busy", String(phase === "loading"));
    status.textContent = phase === "idle" ? "Selecione uma obra para consultar os tratamentos."
      : phase === "loading" ? "Consultando tratamentos…" : phase === "error" ? error : "";
    status.hidden = !status.textContent;
    const counts = artisticCounts(rows);
    filters.replaceChildren(...FILTERS.map(([key, title]) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "artistico-filter";
      button.classList.toggle("active", filter === key);
      button.setAttribute("aria-pressed", String(filter === key));
      button.append(document.createTextNode(title),
        Object.assign(document.createElement("span"), {
          className: "artistico-filter-count", textContent: `(${counts[key]})`,
        }));
      button.addEventListener("click", () => { filter = key; pagination.reset(); draw(); });
      return button;
    }));
    const groups = artisticGroups(rows, query.value, filter);
    const page = pagination.select(groups);
    if (query.value.trim()) page.rows.forEach((group) => {
      openCh.add(group.chapter.chapter);
      group.pages.forEach((item) => openPages.add(artisticKey(group.chapter.chapter, item.name, "")));
    });
    const state = { openCh, openPages, selected, choices, preview, review, draw,
      treatment, label: config.label,
      eligible: (chapter, item) => executableOccurrences(chapter, treatment).includes(item),
      busy: () => busy, restore: { busy: () => busy,
        setBusy(value) { busy = value; updateExecute(); }, reload: load },
      reexecute(chapter, item) { runTreatment([chapter], false, true,
        [{ chapter, page: item.page, id: item.id, expected_sha256: item.expected_sha256,
          roi: item.roi, current_filter: item.current_filter,
          requested_filter: item.requested_filter }]); },
      reexecuteChapter(chapter) { runTreatment([chapter], false, true); },
    };
    preview.hide();
    results.replaceChildren(createArtisticRows(page.rows, state));
    footer.replaceChildren(createPaginationControls(page, (delta) => {
      pagination.move(delta); draw();
    }, { leading: sizeLabel }));
    updateExecute();
  }
  async function load() {
    controller?.abort(); controller = new AbortController();
    const request = controller;
    const { provider, manga } = getContext();
    if (!provider || !manga) { rows = []; phase = "idle"; draw(); return; }
    phase = "loading"; draw();
    try {
      const data = await fetchSpecialTreatments(provider, manga, treatment, request.signal);
      if (disposed || request !== controller || request.signal.aborted) return;
      rows = data.chapters;
      const valid = new Set(rows.flatMap((chapter) => (chapter.occurrences || [])
        .map((item) => artisticKey(chapter.chapter, item.page, item.id))));
      const eligible = new Set(rows.flatMap((chapter) => executableOccurrences(chapter, treatment)
        .map((item) => artisticKey(chapter.chapter, item.page, item.id))));
      for (const key of selected) if (!eligible.has(key)) selected.delete(key);
      for (const key of choices.keys()) if (!valid.has(key)) choices.delete(key);
      if (!initialized && rows.length) {
        initialized = true; openCh.add(rows[0].chapter);
        if (rows[0].pages[0]) openPages.add(artisticKey(rows[0].chapter, rows[0].pages[0], ""));
      }
      phase = "ready"; draw();
    } catch (cause) {
      if (disposed || request !== controller || cause.name === "AbortError") return;
      rows = []; phase = "error"; error = cause.message; draw();
    }
  }
  const runTreatment = createSpecialTreatmentExecution({
    setBusy(value) { busy = value; updateExecute(); }, reload: load, progress,
    treatment, title: `tratamento ${config.label}`, retryTitle: `o tratamento ${config.label}`,
  });
  const onExecute = () => {
    if (busy || execute.disabled) return;
    if (treatment === "estilizado") {
      const items = artisticSelected(rows, selected, choices);
      runTreatment([...new Set(items.map((item) => item.chapter))],
        items.some((item) => item.status === "failed"), false, items);
    } else {
      const selection = executionSelection(rows, treatment, selected, choices);
      if (selection.canExecute) runTreatment(selection.chapters, selection.retry);
    }
  };
  const onQuery = () => { pagination.reset(); draw(); };
  const onSize = () => { pagination = createPagination(Number(size.value)); draw(); };
  query.addEventListener("input", onQuery);
  size.addEventListener("change", onSize);
  execute.addEventListener("click", onExecute);
  const unsubscribe = subscribeContext(() => {
    query.value = ""; filter = "all"; rows = []; initialized = false;
    openCh.clear(); openPages.clear(); selected.clear(); choices.clear();
    pagination.reset(); load();
  });
  load();
  return () => {
    disposed = true; controller?.abort(); unsubscribe();
    query.removeEventListener("input", onQuery); size.removeEventListener("change", onSize);
    execute.removeEventListener("click", onExecute);
    review.dispose(); preview.dispose(); root.remove();
  };
}

export const renderArtisticTable = (container) => renderSpecialWorklist(container, "estilizado");
