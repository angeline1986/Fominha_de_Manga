import {
  bubbleSommelierCropUrl,
  fetchBubbleSommelierReview,
} from "/_app/api/textoff.js";

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
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
  const button = makeElement("button", "sommelier-review-back", "← Voltar para Curadoria");
  button.type = "button";
  button.addEventListener("click", onBack);
  return button;
}

export function renderBubbleSommelierReview(container, { provider, manga, chapter, onBack }) {
  let disposed = false;
  let requestId = 0;
  let request;
  let report;
  let activeFilter = "all";
  const root = makeElement("section", "sommelier-review-page");
  container.replaceChildren(root);

  function showLoading() {
    root.replaceChildren(
      backButton(onBack),
      makeElement("p", "sommelier-review-state", `Carregando revisão do capítulo ${chapter}…`),
    );
  }

  function showError(error) {
    const message = makeElement(
      "p",
      "sommelier-review-error",
      `Não foi possível carregar a revisão: ${error?.message || "erro desconhecido"}`,
    );
    const retry = makeElement("button", "sommelier-review-retry", "Tentar novamente");
    retry.type = "button";
    retry.addEventListener("click", load);
    root.replaceChildren(backButton(onBack), message, retry);
  }

  function draw() {
    const pages = Array.isArray(report?.pages) ? report.pages : [];
    const bubbles = pages.flatMap((page) =>
      (Array.isArray(page.bubbles) ? page.bubbles : []).map((bubble) => ({ page, bubble })));
    const candidates = bubbles.filter(({ bubble }) => bubble.candidate === true);
    const visible = activeFilter === "candidates" ? candidates : bubbles;
    const summary = report.summary || {};

    const header = makeElement("header", "sommelier-review-header");
    header.append(
      backButton(onBack),
      makeElement("h2", "", `Revisão da Curadoria — Capítulo ${chapter}`),
    );

    const summaryNode = makeElement("dl", "sommelier-review-summary");
    const summaryValues = [
      ["PERFIL", report.profile_id ?? "—"],
      ["BALÕES", summary.balloons ?? bubbles.length],
      ["CANDIDATOS", summary.candidates ?? candidates.length],
      ["COVERAGE ≥ 0.75", summary.coverage_ge_075 ?? "—"],
    ];
    for (const [label, value] of summaryValues) {
      const item = makeElement("div", "sommelier-review-summary-item");
      item.append(makeElement("dt", "", label), makeElement("dd", "", String(value)));
      summaryNode.append(item);
    }

    const filters = makeElement("div", "sommelier-review-filters");
    filters.setAttribute("role", "group");
    filters.setAttribute("aria-label", "Filtrar crops");
    for (const [key, label, count] of [
      ["all", "TODOS", bubbles.length],
      ["candidates", "CANDIDATOS", candidates.length],
    ]) {
      const button = makeElement("button", "sommelier-review-filter", `${label} (${count})`);
      button.type = "button";
      button.classList.toggle("active", activeFilter === key);
      button.setAttribute("aria-pressed", String(activeFilter === key));
      button.addEventListener("click", () => {
        activeFilter = key;
        draw();
      });
      filters.append(button);
    }

    const content = makeElement("div", "sommelier-review-content");
    if (!bubbles.length) {
      content.append(makeElement("p", "sommelier-review-empty", "Nenhum balão disponível para revisão."));
    } else if (!visible.length && activeFilter === "candidates") {
      content.append(makeElement("p", "sommelier-review-empty", "Nenhum candidato neste capítulo."));
    } else {
      const byPage = new Map();
      for (const item of visible) {
        const pageId = item.page.page_id ?? "Página sem identificação";
        if (!byPage.has(pageId)) byPage.set(pageId, []);
        byPage.get(pageId).push(item.bubble);
      }
      for (const [pageId, pageBubbles] of byPage) {
        const group = makeElement("section", "sommelier-review-group");
        group.append(makeElement("h3", "", `Página ${pageId}`));
        const grid = makeElement("div", "sommelier-crop-grid");
        for (const bubble of pageBubbles) {
          const card = makeElement("article", "sommelier-crop-card");
          const image = document.createElement("img");
          image.className = "sommelier-crop-image";
          image.loading = "lazy";
          image.alt = `Crop ${bubble.identity} — página ${pageId}`;
          image.src = bubbleSommelierCropUrl(provider, manga, chapter, bubble.identity);
          card.append(image);

          const details = makeElement("div", "sommelier-crop-details");
          const title = `Bubble ${String(bubble.bubble_index ?? "—").padStart(2, "0")}`;
          details.append(makeElement("h4", "", title));
          const identity = makeElement("p", "sommelier-crop-identity", bubble.identity ?? "Identidade ausente");
          identity.title = bubble.identity ?? "";
          details.append(identity);
          const metrics = bubble.metrics || {};
          const values = makeElement("dl", "sommelier-crop-metrics");
          for (const [label, value] of [
            ["Confidence", formatPercent(bubble.confidence)],
            ["Coverage", formatPercent(metrics.coverage)],
            ["Luma MAD", formatNumber(metrics.lumaMad)],
          ]) {
            const item = makeElement("div", "");
            item.append(makeElement("dt", "", label), makeElement("dd", "", value));
            values.append(item);
          }
          details.append(values);
          if (bubble.candidate === true) {
            details.append(makeElement("span", "sommelier-crop-candidate", "CANDIDATO"));
          }
          card.append(details);
          grid.append(card);
        }
        group.append(grid);
        content.append(group);
      }
    }
    root.replaceChildren(header, summaryNode, filters, content);
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
