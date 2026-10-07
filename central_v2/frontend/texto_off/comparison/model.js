import { paginationConfig } from "/_shared/pagination/config.js";

export const COMPARISON_PAGE_SIZE = paginationConfig.inspectionPageSize;
export const INITIAL_ZOOM = 40;
export const MIN_ZOOM = 20;
export const MAX_ZOOM = 200;
export const ZOOM_STEP = 10;
export const TRIPTYCH_PANEL_GAP = 18;

export const COMPARISON_MODES = Object.freeze({
  level1: Object.freeze({
    layout: "pair", heading: "AUTO-CLEANER · PASSO 1", title: "Auto-Cleaner — Passo 1",
    sides: ["before", "after"], panels: [["before", "ORIGINAL"], ["after", "AUTO-CLEANER I"]],
    catalogPanelIndex: 1,
  }),
  level2: Object.freeze({
    layout: "pair", heading: "AUTO-CLEANER · PASSO 2", title: "Auto-Cleaner — Passo 2",
    sides: ["before", "after"], panels: [["before", "AUTO-CLEANER I"], ["after", "AUTO-CLEANER II"]],
    catalogPanelIndex: 1,
  }),
  check: Object.freeze({
    layout: "pair", heading: "AUTO-CLEANER CHECK · REVISÃO", title: "Auto-Cleaner Check",
    sides: ["before", "after"], panels: [["before", "ORIGINAL"], ["after", "ÁREA PARA REVISÃO"]],
    catalogPanelIndex: 1,
  }),
  before_after: Object.freeze({
    layout: "triptych", heading: "AUDITORIA DE QUALIDADE · ANTES & DEPOIS", title: "Antes & Depois",
    sides: ["original", "level1", "level2"],
    panels: [["original", "ORIGINAL"], ["level1", "AUTO-CLEANER I"], ["level2", "AUTO-CLEANER II"]],
    catalogPanelIndex: 1,
  }),
  preview: Object.freeze({
    layout: "pair", heading: "COMPARAÇÃO EXPERIMENTAL", title: "Antes & Depois",
    sides: ["before", "after"], panels: [["before", "ORIGINAL"], ["after", "RESULTADO"]],
    catalogPanelIndex: 1,
  }),
  degrade: Object.freeze({
    layout: "pair", heading: "PINCEL & RETOQUES · DEGRADÊ", title: "Revisão Degradê",
    sides: ["before", "after"], panels: [["before", "ANTES"], ["after", "DEPOIS"]],
    catalogPanelIndex: 1,
  }),
  suave: Object.freeze({
    layout: "pair", heading: "PINCEL & RETOQUES · SUAVE", title: "Revisão Suave",
    sides: ["before", "after"], panels: [["before", "ANTES"], ["after", "DEPOIS"]],
    catalogPanelIndex: 1,
  }),
});

export function level2StatusText(status) {
  return ({ changed: "Nível II: com alterações", no_change: "Nível II: analisado sem alterações",
    not_candidate: "Nível II: página não candidata", pending: "Nível II: aguardando análise",
    unavailable: "Nível II: pré-requisito indisponível" })[status]
    || "Nível II: status indisponível";
}

export function comparisonModeForStep(step) {
  if (step === "1") return "level1";
  if (step === "2") return "level2";
  if (step === "3" || step === "4") return "preview";
  throw new TypeError("Passo de comparação inválido.");
}

export function comparisonModeConfig(mode) {
  const config = COMPARISON_MODES[mode];
  if (!config) throw new TypeError("Modo de comparação inválido.");
  return config;
}

export function filterComparisonPages(pages, query) {
  const term = String(query || "").trim().toLocaleLowerCase("pt-BR");
  return pages.map((page, originalIndex) => ({ page, originalIndex }))
    .filter(({ page }) => page.name.toLocaleLowerCase("pt-BR").includes(term));
}

export function pageComparisonItems(items, page) {
  const pages = Math.max(1, Math.ceil(items.length / COMPARISON_PAGE_SIZE));
  const current = Math.max(1, Math.min(pages, Math.floor(Number(page) || 1)));
  const offset = (current - 1) * COMPARISON_PAGE_SIZE;
  return { rows: items.slice(offset, offset + COMPARISON_PAGE_SIZE), page: current,
    pages, total: items.length, start: items.length ? offset + 1 : 0,
    end: Math.min(offset + COMPARISON_PAGE_SIZE, items.length) };
}

export function clampZoom(current, action) {
  if (action === "one") return 100;
  const delta = action === "+" ? ZOOM_STEP : -ZOOM_STEP;
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(current) + delta));
}
