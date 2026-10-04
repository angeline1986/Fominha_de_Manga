import {
  bubbleSommelierCropUrl,
  fetchBubbleSommelierReview,
} from "/_app/api/textoff.js";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatNumber(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("pt-BR", { maximumFractionDigits: digits })
    : "—";
}

function formatPercent(value) {
  const number = Number(value);
  return Number.isFinite(number)
    ? `${(number * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`
    : "—";
}

function backButton(onBack) {
  const button = element("button", "sommelier-review-back", "← Voltar para Curadoria");
  button.type = "button";
  button.addEventListener("click", onBack);
  return button;
}

function pageCandidateCount(page) {
  return page.bubbles.filter((bubble) => bubble.candidate === true).length;
}

export function renderBubbleSommelierReview(container, { provider, manga, chapter, onBack }) {
  let disposed = false;
  let requestId = 0;
  let request;
  let report;
  let activePageId = null;
  let activeFilter = "all";
  const root = element("section", "sommelier-review-page");
  container.replaceChildren(root);

  function showLoading() {
    root.replaceChildren(
      backButton(onBack),
      element("p", "sommelier-review-state", `Carregando revisão do capítulo ${chapter}…`),
    );
  }

  function showError(error) {
    const message = element(
      "p",
      "sommelier-review-error",
      `Não foi possível carregar a revisão: ${error?.message || "erro desconhecido"}`,
    );
    const retry = element("button", "sommelier-review-retry", "Tentar novamente");
    retry.type = "button";
    retry.addEventListener("click", load);
    root.replaceChildren(backButton(onBack), message, retry);
  }

  function drawMain(page) {
    const main = root.querySelector("[data-review-main]");
    main.replaceChildren();
    if (!page) {
      main.append(element("p", "sommelier-review-empty", "Nenhuma página corresponde à busca."));
      return;
    }

    const pageCandidates = pageCandidateCount(page);
    const subheadText = `${page.page_id} · ${page.bubbles.length} balões${pageCandidates ? ` · ${pageCandidates} candidatos` : ""}`;
    const subhead = element("div", "sommelier-review-page-heading");
    subhead.append(element("h2", "", subheadText));

    const table = element("div", "sommelier-review-table");
    const columns = element("div", "sommelier-review-columns");
    columns.setAttribute("aria-hidden", "true");
    for (const label of ["RECORTE", "IDENTIFICAÇÃO", "MÉTRICAS", "STATUS"]) {
      columns.append(element("span", "", label));
    }
    table.append(columns);

    const bubbles = activeFilter === "candidates"
      ? page.bubbles.filter((bubble) => bubble.candidate === true)
      : page.bubbles;
    if (!page.bubbles.length) {
      table.append(element("p", "sommelier-review-empty", "Nenhum balão disponível para revisão."));
    } else if (!bubbles.length && activeFilter === "candidates") {
      table.append(element("p", "sommelier-review-empty", "Nenhum candidato nesta página."));
    } else {
      const rows = element("div", "sommelier-review-rows");
      for (const bubble of bubbles) {
        const row = element("article", `sommelier-review-row${bubble.candidate === true ? " is-candidate" : ""}`);

        const crop = element("div", "sommelier-review-crop");
        const image = document.createElement("img");
        image.className = "sommelier-review-image";
        image.loading = "lazy";
        image.alt = `Crop ${bubble.identity} — ${page.page_id}`;
        image.src = bubbleSommelierCropUrl(provider, manga, chapter, bubble.identity);
        crop.append(image);

        const identity = element("div", "sommelier-review-identity");
        identity.append(
          element("strong", "", `Bubble ${String(bubble.bubble_index ?? "—").padStart(2, "0")}`),
          element("span", "", bubble.identity ?? "Identidade ausente"),
        );

        const metrics = element("dl", "sommelier-review-metrics");
        for (const [label, value] of [
          ["Conf.", formatPercent(bubble.confidence)],
          ["Coverage", formatPercent(bubble.metrics?.coverage)],
          ["Luma MAD", formatNumber(bubble.metrics?.lumaMad)],
        ]) {
          const metric = element("div", "sommelier-review-metric");
          metric.append(element("dt", "", label), element("dd", "", value));
          metrics.append(metric);
        }

        const status = element("div", "sommelier-review-status");
        status.append(bubble.candidate === true
          ? element("span", "sommelier-review-candidate", "CANDIDATO")
          : element("span", "sommelier-review-not-candidate", "—"));
        row.append(crop, identity, metrics, status);
        rows.append(row);
      }
      table.append(rows);
    }
    main.append(subhead, table);
  }

  function drawSidebar() {
    const pages = Array.isArray(report.pages) ? report.pages : [];
    const list = root.querySelector("[data-review-pages]");
    const query = root.querySelector("[data-page-query]").value.trim().toLocaleLowerCase("pt-BR");
    const matches = pages.filter((page) => page.page_id.toLocaleLowerCase("pt-BR").includes(query));
    list.replaceChildren();

    if (!pages.length) {
      list.append(element("p", "sommelier-review-empty", "Nenhuma página disponível."));
      root.querySelector("[data-review-main]").replaceChildren(
        element("p", "sommelier-review-empty", "Nenhum balão disponível para revisão."),
      );
      return;
    }

    if (!matches.length) {
      list.append(element("p", "sommelier-review-empty", "Nenhuma página corresponde à busca."));
      drawMain(null);
      return;
    }

    for (const page of matches) {
      const candidateCount = pageCandidateCount(page);
      const item = element("button", `sommelier-review-page-item${page.page_id === activePageId ? " is-active" : ""}`);
      item.type = "button";
      item.setAttribute("aria-current", String(page.page_id === activePageId));
      item.addEventListener("click", () => {
        activePageId = page.page_id;
        drawSidebar();
      });
      item.append(element("span", "sommelier-review-page-name", page.page_id));
      const counts = element("span", "sommelier-review-page-counts");
      counts.append(element("span", "sommelier-review-total", String(page.bubbles.length)));
      if (candidateCount) counts.append(element("span", "sommelier-review-candidate-count", `●${candidateCount}`));
      item.append(counts);
      list.append(item);
    }

    drawMain(pages.find((page) => page.page_id === activePageId) ?? null);
  }

  function draw() {
    const pages = Array.isArray(report.pages) ? report.pages : [];
    const summary = report.summary || {};
    activePageId = pages[0]?.page_id ?? null;

    const header = element("header", "sommelier-review-top-header");
    const title = element("strong", "sommelier-review-global-title", "CLASSIFICAÇÃO & TRIAGEM DE BALÕES");
    const chapterSummary = element(
      "div",
      "sommelier-review-global-summary",
      `Capítulo ${report.chapter ?? chapter} · ${summary.balloons ?? 0} balões catalogados em ${pages.length} páginas`,
    );
    const profile = element("span", "sommelier-review-profile", `Perfil: ${report.profile_id ?? "—"}`);
    const headingRight = element("div", "sommelier-review-heading-right");
    headingRight.append(chapterSummary, profile);
    header.append(title, headingRight);

    const workspace = element("div", "sommelier-review-workspace");
    const sidebar = element("aside", "sommelier-review-sidebar");
    const totalBubbles = pages.reduce((total, page) => total + page.bubbles.length, 0);
    const totalCandidates = pages.reduce((total, page) => total + pageCandidateCount(page), 0);
    const filters = element("div", "sommelier-review-filter-pills");
    filters.setAttribute("role", "group");
    filters.setAttribute("aria-label", "Filtrar balões");
    for (const [key, label, count] of [
      ["all", "Todos", totalBubbles],
      ["candidates", "Candidatos", totalCandidates],
    ]) {
      const button = element("button", `sommelier-review-filter-pill${activeFilter === key ? " is-active" : ""}`, `${label} (${count})`);
      button.type = "button";
      button.setAttribute("aria-pressed", String(activeFilter === key));
      button.addEventListener("click", () => {
        activeFilter = key;
        drawSidebar();
        for (const pill of filters.querySelectorAll("button")) {
          const active = pill === button;
          pill.classList.toggle("is-active", active);
          pill.setAttribute("aria-pressed", String(active));
        }
      });
      filters.append(button);
    }

    const pageControls = element("div", "sommelier-review-page-controls");
    pageControls.append(element("span", "sommelier-review-chapter-badge", `Cap. ${report.chapter ?? chapter}`));
    const search = document.createElement("input");
    search.className = "sommelier-review-page-search";
    search.type = "search";
    search.placeholder = "Busca Pág.";
    search.setAttribute("aria-label", "Busca Pág.");
    search.setAttribute("data-page-query", "");
    search.addEventListener("input", drawSidebar);
    pageControls.append(search);

    const pagesList = element("nav", "sommelier-review-page-list");
    pagesList.setAttribute("aria-label", "Páginas do capítulo");
    const main = element("main", "sommelier-review-main");
    main.setAttribute("data-review-main", "");
    pagesList.setAttribute("data-review-pages", "");
    sidebar.append(filters, pageControls, pagesList);
    workspace.append(sidebar, main);
    root.replaceChildren(header, workspace);
    drawSidebar();
  }

  async function load() {
    const id = ++requestId;
    request?.abort();
    request = new AbortController();
    showLoading();
    try {
      const data = await fetchBubbleSommelierReview(provider, manga, chapter, request.signal);
      if (disposed || id !== requestId) return;
      report = data;
      draw();
    } catch (error) {
      if (!disposed && id === requestId && error?.name !== "AbortError") showError(error);
    }
  }

  load();
  return () => {
    disposed = true;
    requestId += 1;
    request?.abort();
    root.remove();
  };
}
