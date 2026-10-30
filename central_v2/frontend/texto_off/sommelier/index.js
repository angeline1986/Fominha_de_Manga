import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchBubbleSommelier, startBubbleSommelier, waitForTextoffJob } from "/_app/api/textoff.js";
import { renderBubbleSommelierReview } from "./review.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls, createPageSizeControl } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { showMessage, showOperationSummary } from "/_shared/messages/messages.js";
import { sommelierMarkup } from "/texto_off/sommelier/markup.js";
import { sommelierColumns } from "/texto_off/sommelier/table_columns.js";
import { aggregateSommelierProgress, operationSummary, SOMMELIER_NAME } from "/texto_off/sommelier/progress_model.js";
import { drawSommelierFilters, matchesSommelierRow } from "/texto_off/sommelier/filters.js";

export { aggregateSommelierProgress } from "/texto_off/sommelier/progress_model.js";

export function render(container) {
  let disposed = false;
  let requestId = 0;
  let request;
  let rows = [];
  let activeFilter = "all";
  const selected = new Set();
  let pagination = createPagination();
  const pageSize = createPageSizeControl((size) => { pagination = createPagination(size); draw(); });

  const root = document.createElement("section");
  root.className = "auto-merge-page textoff-merged-page cleaner-overview sommelier-page";
  root.innerHTML = sommelierMarkup();
  container.replaceChildren(root);

  const query = root.querySelector("[data-query]");
  const filters = root.querySelector(".auto-merge-filters");
  const status = root.querySelector("[data-status]");
  const results = root.querySelector("[data-results]");
  const execute = root.querySelector("[data-execute]");
  const profile = root.querySelector("[data-profile]");
  const listView = root.querySelector("[data-list-view]");
  const reviewHost = root.querySelector("[data-review-host]");
  const progress = createJobProgress(SOMMELIER_NAME, { countUnit: "páginas" });
  root.querySelector(".auto-merge-toolbar").after(progress.element);
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

  function draw() {
    drawSommelierFilters(filters, rows, activeFilter, (key) => {
      activeFilter = key;
      pagination.reset();
      draw();
    });
    const term = query.value.trim().toLocaleLowerCase("pt-BR");
    const visible = rows.filter((row) =>
      row.chapter.toLocaleLowerCase("pt-BR").includes(term) && matchesSommelierRow(row, activeFilter));
    const page = pagination.select(visible);

    const columns = sommelierColumns({ page, selected, executionBusy, draw, openReview });

    results.replaceChildren(createTable(columns, page.rows, "Capítulos para Bubble Sommelier", {
      emptyMessage: rows.length ? "Nenhum capítulo corresponde ao filtro." : "",
    }));
    results.append(createPaginationControls(page, (delta) => {
      pagination.move(delta);
      draw();
    }, { leading: pageSize.element }));
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
    progress.update({ busy: true, title: `${SOMMELIER_NAME} · queued`,
      message: "Na fila para execução…", percent: 0, completed: 0, total: totalPages });
    try {
      const { job } = await startBubbleSommelier(provider, manga, chapters, profile.value);
      const jobResults = await waitForTextoffJob(job, (current) => {
        progress.update(aggregateSommelierProgress(current, chapters, pagesByChapter));
      });
      progress.update({ busy: true, title: `${SOMMELIER_NAME} · completed`,
        message: "Execução concluída; atualizando resultados…",
        percent: 100, completed: totalPages, total: totalPages });
      selected.clear();
      await load();
      await showOperationSummary({
        title: "Resumo do Bubble Sommelier",
        summary: operationSummary(jobResults),
      });
    } catch (error) {
      await showMessage({ title: "Falha no Bubble Sommelier", message: error.message });
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
