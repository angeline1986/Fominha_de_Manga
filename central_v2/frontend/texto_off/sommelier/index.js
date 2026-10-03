import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchBubbleSommelier, startBubbleSommelier, waitForTextoffJob } from "/_app/api/textoff.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { iconMarkup } from "/_shared/icons/icons.js";

const FILTERS = [
  ["all", "ALL"],
  ["pending", "PENDENTE"],
  ["analyzed", "ANALISADO"],
  ["special", "ESPECIAL"],
];

function filterButton(label, count, active, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "auto-merge-filter-button";
  button.classList.toggle("active", active);
  button.textContent = `${label} (${count})`;
  button.setAttribute("aria-pressed", String(active));
  button.addEventListener("click", onClick);
  return button;
}

function statusOf(row) {
  if (row.sommelier?.special > 0) return "special";
  if (row.sommelier?.analyzed) return "analyzed";
  return "pending";
}

export function render(container) {
  let disposed = false;
  let requestId = 0;
  let request;
  let rows = [];
  let activeFilter = "all";
  const selected = new Set();
  const pagination = createPagination();

  const root = document.createElement("section");
  root.className = "auto-merge-page textoff-merged-page cleaner-overview sommelier-page";
  root.innerHTML = `
    <header>
      <h1 class="textoff-page-title-hint" data-tooltip="Pré-análise antes da limpeza"
          tabindex="0" aria-description="Pré-análise antes da limpeza">Curadoria de Balões</h1>
    </header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search">
        <span class="visually-hidden">Buscar capítulo</span>
        <input type="search" data-query placeholder="Buscar capítulo">
      </label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar curadoria"></div>
      <button class="auto-merge-execute sommelier-execute" type="button" data-execute
              title="Será habilitado com a integração do BubbleSommelier">Executar Curadoria</button>
    </div>
    <p class="auto-merge-status" data-status role="status" aria-live="polite"></p>
    <div class="auto-merge-results" data-results></div>
  `;
  container.replaceChildren(root);

  const query = root.querySelector("[data-query]");
  const filters = root.querySelector(".auto-merge-filters");
  const status = root.querySelector("[data-status]");
  const results = root.querySelector("[data-results]");
  const execute = root.querySelector("[data-execute]");

  const matches = (row, key) => key === "all" || statusOf(row) === key;

  function drawFilters() {
    filters.replaceChildren();
    for (const [key, label] of FILTERS) {
      const count = rows.filter((row) => matches(row, key)).length;
      filters.append(filterButton(label, count, activeFilter === key, () => {
        activeFilter = key;
        pagination.reset();
        draw();
      }));
    }
  }

  function draw() {
    drawFilters();
    const term = query.value.trim().toLocaleLowerCase("pt-BR");
    const visible = rows.filter((row) =>
      row.chapter.toLocaleLowerCase("pt-BR").includes(term) && matches(row, activeFilter));
    const page = pagination.select(visible);

    const columns = [
      { id: "select", label: "", render: (row) => {
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = selected.has(row.chapter);
        input.setAttribute("aria-label", `Selecionar capítulo ${row.chapter}`);
        input.addEventListener("change", () => {
          if (input.checked) selected.add(row.chapter);
          else selected.delete(row.chapter);
          execute.disabled = selected.size === 0;
        });
        return input;
      }},
      { id: "chapter", label: "Capítulo", render: (row) => row.chapter },
      { id: "merges", label: "MERGES", render: (row) => row.merge_valid ? row.merge_count : "—" },
      { id: "balloons", label: "BALÕES", render: (row) => row.sommelier?.balloons ?? "—" },
      { id: "normal", label: "NORMAIS", render: (row) => row.sommelier?.normal ?? "—" },
      { id: "special", label: "ESPECIAIS", render: (row) => row.sommelier?.special ?? "—" },
      { id: "review", label: "REVISAR", render: (row) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn sommelier-review";
        button.innerHTML = iconMarkup("eye");
        button.setAttribute("aria-label", "Visualizar capítulo");
        button.disabled = !row.sommelier?.analyzed;
        button.title = row.sommelier?.analyzed ? "Visualizar resultado da curadoria" : "Disponível após a análise do BubbleSommelier";
        return button;
      }},
    ];

    results.replaceChildren(createTable(columns, page.rows, "Capítulos para Curadoria de Balões", {
      emptyMessage: rows.length ? "Nenhum capítulo corresponde ao filtro." : "",
    }));
    if (visible.length) results.append(createPaginationControls(page, (delta) => {
      pagination.move(delta);
      draw();
    }));
    execute.disabled = selected.size === 0;
  }

  execute.addEventListener("click", async () => {
    if (!selected.size || execute.disabled) return;
    const { provider, manga } = getContext();
    execute.disabled = true;
    status.textContent = `Executando Curadoria em ${selected.size} capítulo(s)…`;
    status.hidden = false;
    try {
      const { job } = await startBubbleSommelier(provider, manga, [...selected]);
      await waitForTextoffJob(job, (current) => {
        const done = current.completed ?? current.done ?? 0;
        const total = current.total ?? selected.size;
        status.textContent = `Curadoria em andamento: ${done}/${total}`;
      });
      selected.clear();
      status.textContent = "Curadoria concluída.";
      await load();
    } catch (error) {
      status.textContent = error.message;
      status.hidden = false;
      execute.disabled = selected.size === 0;
    }
  });

  async function load() {
    const id = ++requestId;
    request?.abort();
    request = new AbortController();
    const { provider, manga } = getContext();

    if (!provider || !manga) {
      rows = [];
      status.textContent = "Selecione uma obra para consultar os capítulos.";
      status.hidden = false;
      draw();
      return;
    }

    status.textContent = `Consultando ${manga}…`;
    status.hidden = false;
    try {
      const data = await fetchBubbleSommelier(provider, manga, request.signal);
      if (disposed || id !== requestId) return;
      rows = data.chapters || [];
      status.textContent = "";
      status.hidden = true;
      draw();
    } catch (error) {
      if (!disposed && id === requestId && error.name !== "AbortError") {
        rows = [];
        status.textContent = error.message;
        status.hidden = false;
        draw();
      }
    }
  }

  const onQuery = () => { pagination.reset(); draw(); };
  query.addEventListener("input", onQuery);

  const unsubscribe = subscribeContext(() => {
    query.value = "";
    activeFilter = "all";
    selected.clear();
    pagination.reset();
    load();
  });

  draw();
  load();

  return () => {
    disposed = true;
    requestId += 1;
    request?.abort();
    unsubscribe();
    query.removeEventListener("input", onQuery);
    root.remove();
  };
}
