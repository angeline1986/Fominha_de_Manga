import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchBubbleSommelier, startBubbleSommelier, waitForTextoffJob } from "/_app/api/textoff.js";
import { renderBubbleSommelierReview } from "./review.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { createJobProgress } from "/_shared/progress/progress.js";

const FILTERS = [
  ["all", "ALL"],
  ["pending", "PENDENTE"],
  ["analyzed", "ANALISADO"],
  ["candidates", "CANDIDATOS"],
];

export function aggregateSommelierProgress(job, chapters, pagesByChapter) {
  const jobProgress = job.progress || job;
  const chapterIndex = chapters.indexOf(job.chapter);
  const completedBefore = chapterIndex < 0
    ? 0
    : chapters.slice(0, chapterIndex).reduce((sum, chapter) => sum + (pagesByChapter.get(chapter) || 0), 0);
  const chapterPages = pagesByChapter.get(job.chapter) || 0;
  const completedInChapter = jobProgress.stage === "completed"
    ? chapterPages
    : Math.max(0, Math.min(chapterPages, Number(jobProgress.completed) || 0));
  const total = [...pagesByChapter.values()].reduce((sum, count) => sum + count, 0);
  const completed = Math.min(total, completedBefore + completedInChapter);
  return {
    busy: job.status !== "failed",
    title: `Curadoria de Balões · ${job.status}`,
    message: jobProgress.message || "Preparando Curadoria…",
    percent: total ? Math.round(completed * 100 / total) : 0,
    completed,
    total,
  };
}

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
    <div data-list-view>
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
      <label class="sommelier-profile">
        <span>Perfil</span>
        <select data-profile aria-label="Perfil">
          <option value="">Selecione o perfil</option>
          <option value="poc_a_v1">poc_a_v1</option>
          <option value="poc_b_v1">poc_b_v1</option>
        </select>
      </label>
      <button class="auto-merge-execute sommelier-execute" type="button" data-execute
              title="Selecione capítulos e um perfil">Executar Curadoria</button>
    </div>
    <div data-progress></div>
    <p class="auto-merge-status" data-status role="status" aria-live="polite"></p>
    <div class="auto-merge-results" data-results></div>
    </div>
    <div data-review-host hidden></div>
  `;
  container.replaceChildren(root);

  const query = root.querySelector("[data-query]");
  const filters = root.querySelector(".auto-merge-filters");
  const status = root.querySelector("[data-status]");
  const results = root.querySelector("[data-results]");
  const execute = root.querySelector("[data-execute]");
  const profile = root.querySelector("[data-profile]");
  const listView = root.querySelector("[data-list-view]");
  const reviewHost = root.querySelector("[data-review-host]");
  const progress = createJobProgress("Curadoria de Balões", { inline: true, countUnit: "páginas" });
  root.querySelector("[data-progress]").append(progress.element);
  let closeReview;
  let executionBusy = false;

  function leaveReview() {
    closeReview?.();
    closeReview = undefined;
    reviewHost.replaceChildren();
    reviewHost.hidden = true;
    listView.hidden = false;
  }

  function openReview(chapter) {
    if (closeReview) return;
    const { provider, manga } = getContext();
    listView.hidden = true;
    reviewHost.hidden = false;
    closeReview = renderBubbleSommelierReview(reviewHost, {
      provider,
      manga,
      chapter,
      onBack: leaveReview,
    });
  }

  function updateExecuteState() {
    execute.disabled = executionBusy || selected.size === 0 || profile.value === "";
  }

  const matches = (row, key) => {
    if (key === "all") return true;
    if (key === "pending") return !row.sommelier?.analyzed;
    if (key === "analyzed") return Boolean(row.sommelier?.analyzed);
    if (key === "candidates") {
      return Boolean(row.sommelier?.analyzed && row.sommelier.candidates > 0);
    }
    return false;
  };

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
          updateExecuteState();
        });
        return input;
      }},
      { id: "chapter", label: "Capítulo", render: (row) => row.chapter },
      { id: "merges", label: "MERGES", render: (row) => row.merge_valid ? row.merge_count : "—" },
      { id: "balloons", label: "BALÕES", render: (row) => row.sommelier?.balloons ?? "—" },
      { id: "candidates", label: "CANDIDATOS", render: (row) => row.sommelier?.candidates ?? "—" },
      { id: "profile", label: "PERFIL", render: (row) => row.sommelier?.analyzed ? row.sommelier.profile_id : "—" },
      { id: "review", label: "REVISAR", render: (row) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn sommelier-review";
        button.innerHTML = iconMarkup("eye");
        button.setAttribute("aria-label", "Visualizar capítulo");
        button.disabled = !row.sommelier?.analyzed;
        button.title = row.sommelier?.analyzed ? "Visualizar resultado da curadoria" : "Disponível após a análise do BubbleSommelier";
        button.addEventListener("click", () => openReview(row.chapter));
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
    updateExecuteState();
  }

  execute.addEventListener("click", async () => {
    if (!selected.size || !profile.value || execute.disabled) return;
    const { provider, manga } = getContext();
    const chapters = [...selected];
    const pagesByChapter = new Map(chapters.map((chapter) => [
      chapter, Math.max(0, Number(rows.find((row) => row.chapter === chapter)?.merge_count) || 0),
    ]));
    const totalPages = [...pagesByChapter.values()].reduce((sum, count) => sum + count, 0);
    executionBusy = true;
    updateExecuteState();
    status.textContent = "";
    status.hidden = true;
    progress.update({ busy: true, title: "Curadoria de Balões · queued",
      message: "Na fila para execução…", percent: 0, completed: 0, total: totalPages });
    try {
      const { job } = await startBubbleSommelier(provider, manga, chapters, profile.value);
      await waitForTextoffJob(job, (current) => {
        progress.update(aggregateSommelierProgress(current, chapters, pagesByChapter));
      });
      progress.update({ busy: true, title: "Curadoria de Balões · completed",
        message: "Execução concluída; atualizando resultados…",
        percent: 100, completed: totalPages, total: totalPages });
      selected.clear();
      await load();
      status.textContent = "Curadoria concluída.";
      status.hidden = false;
    } catch (error) {
      progress.update({ busy: false });
      status.textContent = error.message;
      status.hidden = false;
    } finally {
      progress.update({ busy: false });
      executionBusy = false;
      updateExecuteState();
    }
  });

  profile.addEventListener("change", updateExecuteState);

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
    leaveReview();
    query.value = "";
    activeFilter = "all";
    selected.clear();
    profile.value = "";
    pagination.reset();
    updateExecuteState();
    load();
  });

  draw();
  load();

  return () => {
    disposed = true;
    leaveReview();
    requestId += 1;
    request?.abort();
    unsubscribe();
    query.removeEventListener("input", onQuery);
    profile.removeEventListener("change", updateExecuteState);
    root.remove();
  };
}
