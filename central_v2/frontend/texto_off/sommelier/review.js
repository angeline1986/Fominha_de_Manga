import { fetchBubbleSommelier, fetchBubbleSommelierReview } from "/_app/api/textoff.js";
import { createPageNavigation, pageNavigationMarkup } from "/texto_off/comparison/page_navigation.js";
import { element, pageCandidateCount, drawReviewMain } from "/texto_off/sommelier/review_content.js";

function backButton(onBack) {
  const button = element("button", "sommelier-review-back", "← Voltar para Curadoria");
  button.type = "button";
  button.addEventListener("click", onBack);
  return button;
}

export function renderBubbleSommelierReview(container, { provider, manga, chapter, onBack }) {
  let disposed = false;
  let requestId = 0;
  let request;
  let report;
  let activePageId = null;
  let currentChapter = chapter;
  let chapters = [];
  let navigation;
  let activeFilter = "all";
  const root = element("section", "sommelier-review-page");
  container.replaceChildren(root);

  function showLoading() {
    root.replaceChildren(
      backButton(onBack),
      element("p", "sommelier-review-state", `Carregando revisão do capítulo ${currentChapter}…`),
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
      navigation?.selectPage(-1);
      drawReviewMain(root, null, { provider, manga, chapter: currentChapter, activeFilter });
      return;
    }
    if (!matches.some((page) => page.page_id === activePageId)) activePageId = matches[0].page_id;

    for (const page of matches) {
      const candidateCount = pageCandidateCount(page);
      const item = element("button", `sommelier-review-page-item${page.page_id === activePageId ? " is-active" : ""}`);
      item.type = "button";
      item.setAttribute("aria-current", String(page.page_id === activePageId));
      item.addEventListener("click", () => {
        if (activePageId === page.page_id) return;
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

    navigation?.selectPage(pages.findIndex((page) => page.page_id === activePageId));
    drawReviewMain(root, pages.find((page) => page.page_id === activePageId) ?? null,
      { provider, manga, chapter: currentChapter, activeFilter });
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
      `Capítulo ${report.chapter ?? currentChapter} · ${summary.balloons ?? 0} balões catalogados em ${pages.length} páginas`,
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
    pageControls.innerHTML = pageNavigationMarkup();
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
    sidebar.append(filters, element("h2", "sommelier-review-pages-heading", "Páginas"), pageControls, pagesList);
    workspace.append(sidebar, main);
    root.replaceChildren(header, workspace);
    navigation = createPageNavigation(root, { chapter: currentChapter, chapters,
      onChapterChange(next) { currentChapter = next; activePageId = null; load(); },
      onPageChange(index) {
        const page = pages[index];
        if (page && page.page_id !== activePageId) { activePageId = page.page_id; drawSidebar(); }
      },
    });
    navigation.setPages(pages);
    drawSidebar();
  }

  async function load() {
    const id = ++requestId;
    request?.abort();
    request = new AbortController();
    showLoading();
    try {
      if (!chapters.length) {
        const catalog = await fetchBubbleSommelier(provider, manga, request.signal);
        chapters = (catalog.chapters || []).filter((row) => row.sommelier?.analyzed);
      }
      const data = await fetchBubbleSommelierReview(provider, manga, currentChapter, request.signal);
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
