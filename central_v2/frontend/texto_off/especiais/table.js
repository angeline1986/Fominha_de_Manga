import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchSpecialTreatments } from "/_app/api/textoff.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { iconMarkup } from "/_shared/icons/icons.js";

const PAGES = {
  degrade: { title: "Pincel & Retoques — Degradê", empty: "Nenhum tratamento em degradê pendente." },
  estilizado: { title: "Pincel & Retoques — Artístico", empty: "Nenhum tratamento artístico pendente." },
  gradiente_suave: { title: "Pincel & Retoques — Suave", empty: "Nenhum tratamento suave pendente." },
};
const FILTERS = [["all", "TODOS"], ["pending", "PENDENTES"], ["completed", "CONCLUÍDOS"]];
const SIZES = [15, 20, 30, 40, 50];
const STATUS = { pending: "Pendente", processed: "Processado", no_change: "Sem alteração", failed: "Falha" };

export function matchesSpecialRow(row, term, filter) {
  const search = term.trim().toLocaleLowerCase("pt-BR");
  const matchesText = !search || row.chapter.toLocaleLowerCase("pt-BR").includes(search)
    || row.pages.some((page) => page.toLocaleLowerCase("pt-BR").includes(search));
  const matchesStatus = filter === "all" || (filter === "completed"
    ? ["processed", "no_change"].includes(row.status) : row.status === "pending");
  return matchesText && matchesStatus;
}

export function renderSpecialTable(container, treatment) {
  const page = PAGES[treatment];
  if (!page) throw new Error("Tratamento especial inválido.");
  const root = document.createElement("section");
  root.className = "auto-merge-page textoff-merged-page cleaner-overview sommelier-page special-treatment-table";
  root.innerHTML = `<header><h1 class="textoff-page-title-hint">${page.title}</h1></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo ou página</span><input type="search" data-query placeholder="Buscar capítulo ou página"></label>
      <div class="auto-merge-filters" data-filters role="group" aria-label="Filtrar capítulos"></div>
      <button class="auto-merge-execute" type="button" data-execute disabled>Executar</button>
    </div>
    <p class="auto-merge-status" data-status role="status" aria-live="polite"></p>
    <div class="auto-merge-results" data-results></div>`;
  container.replaceChildren(root);
  const query = root.querySelector("[data-query]");
  const filters = root.querySelector("[data-filters]");
  const results = root.querySelector("[data-results]");
  const status = root.querySelector("[data-status]");
  const sizeLabel = document.createElement("label");
  sizeLabel.className = "sommelier-profile";
  sizeLabel.textContent = "Exibir:";
  const size = document.createElement("select");
  size.setAttribute("aria-label", "Exibir itens por página");
  sizeLabel.append(size);
  for (const value of SIZES) {
    const option = document.createElement("option");
    option.value = String(value); option.textContent = String(value);
    size.append(option);
  }
  size.value = "15";
  let pagination = createPagination();
  let rows = [];
  const selectedChapters = new Set();
  let filter = "all", phase = "idle", error = "", controller, disposed = false;

  function draw() {
    root.setAttribute("aria-busy", String(phase === "loading"));
    status.textContent = phase === "idle" ? "Selecione uma obra para consultar os tratamentos."
      : phase === "loading" ? "Consultando tratamentos…" : phase === "error" ? error : "";
    filters.replaceChildren();
    for (const [key, label] of FILTERS) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "auto-merge-filter-button";
      button.textContent = `${label} (${rows.filter((row) => matchesSpecialRow(row, "", key)).length})`;
      button.classList.toggle("active", filter === key);
      button.setAttribute("aria-pressed", String(filter === key));
      button.addEventListener("click", () => { filter = key; pagination.reset(); draw(); });
      filters.append(button);
    }
    const visible = rows.filter((row) => matchesSpecialRow(row, query.value, filter));
    const selected = pagination.select(visible);
    const columns = [
      { id: "select", label: "", render: (row) => {
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = selectedChapters.has(row.chapter);
        input.setAttribute("aria-label", `Selecionar capítulo ${row.chapter}`);
        input.addEventListener("change", () => {
          if (input.checked) selectedChapters.add(row.chapter);
          else selectedChapters.delete(row.chapter);
        });
        return input;
      } },
      { id: "chapter", label: "Capítulo", render: (row) => row.chapter },
      { id: "pages", label: "PÁGINAS", render: (row) => row.page_count,
        title: (row) => row.pages.join(", ") },
      { id: "occurrences", label: "OCORRÊNCIAS", render: (row) => row.occurrence_count },
      { id: "status", label: "STATUS", render: (row) => STATUS[row.status] },
      { id: "review", label: "REVISAR", render: () => {
        const button = document.createElement("button");
        button.type = "button"; button.className = "btn sommelier-review";
        button.innerHTML = iconMarkup("eye");
        button.setAttribute("aria-label", "Revisão disponível após integração do tratamento");
        button.title = "Revisão disponível após integração do tratamento";
        button.disabled = true;
        return button;
      } },
    ];
    results.replaceChildren(createTable(columns, selected.rows, `Capítulos para ${page.title}`, {
      emptyMessage: phase === "ready" && !rows.length ? page.empty
        : phase === "ready" ? "Nenhum capítulo corresponde à busca ou ao filtro." : "",
    }));
    if (phase === "ready") results.append(createPaginationControls(selected, (delta) => {
      pagination.move(delta); draw();
    }, { leading: sizeLabel, hideEmptyActions: true }));
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
      rows = data.chapters; phase = "ready"; draw();
    } catch (cause) {
      if (disposed || request !== controller || cause.name === "AbortError") return;
      rows = []; phase = "error"; error = cause.message; draw();
    }
  }

  const onQuery = () => { pagination.reset(); draw(); };
  const onSize = () => { pagination = createPagination(Number(size.value)); draw(); };
  query.addEventListener("input", onQuery);
  size.addEventListener("change", onSize);
  const unsubscribe = subscribeContext(() => {
    query.value = ""; filter = "all"; selectedChapters.clear(); pagination.reset(); load();
  });
  load();
  return () => {
    disposed = true; controller?.abort(); unsubscribe();
    query.removeEventListener("input", onQuery); size.removeEventListener("change", onSize);
    root.remove();
  };
}
