import { bubbleSommelierCropUrl } from "/_app/api/textoff.js";

export function element(tag, className, text) {
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

export function pageCandidateCount(page) {
  return page.bubbles.filter((bubble) => bubble.candidate === true).length;
}

export function drawReviewMain(root, page, { provider, manga, chapter, activeFilter }) {
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
