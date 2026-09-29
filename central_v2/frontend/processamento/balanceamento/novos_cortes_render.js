import { balanceamentoImageUrl } from "/_app/api/balanceamento.js";
import { escapeHtml } from "/_shared/dom/sanitize.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { isOddPage } from "/_shared/pages/page_number.js";

export function cutValues(draft) {
  return (draft?.cuts || []).map((cut) => Number(cut.selected_y)).filter(Number.isFinite).sort((a, b) => a - b);
}

export function validCuts(cuts, start, end) {
  return cuts.length > 0 && cuts.every((cut, index) => cut > start && cut < end && (!index || cut > cuts[index - 1]));
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function renderCutsEditor({ element, editorHost, preview, focusButton, state, actions }) {
  const previousCanvas = editorHost.querySelector("[data-canvas]");
  const previousStage = editorHost.querySelector("[data-stage]");
  const previousImage = previousStage?.querySelector("img");
  const scroll = previousCanvas ? { top: previousCanvas.scrollTop, left: previousCanvas.scrollLeft } : null;
  const mergeScroll = editorHost.querySelector("[data-merges]")?.scrollTop ?? 0;
  const selection = state.selection;
  const draft = state.draft;
  const start = Number(draft?.region?.global_start);
  const end = Number(draft?.region?.global_end);
  const total = end - start;
  const mergeRows = (selection?.merges || []).map((file) => {
    const range = (draft?.merge_ranges || []).find((item) => item.file === file);
    const labels = range ? state.cuts.map((cut, index) => cut > Number(range.global_start) && cut <= Number(range.global_end)
      ? `<small class="manual-cut-cut-label" style="color:${state.rulerColors[index]}">Corte ${index + 1}</small>` : "").join("") : "";
    return `<div class="manual-cut-page-item balance-cuts-merge" data-merge-preview="${escapeHtml(file)}"><span>${escapeHtml(file)}</span>${labels}</div>`;
  }).join("");
  const rulers = state.cuts.map((_, index) => `<button type="button" data-ruler="${index}" class="manual-cut-ruler-button ${index === state.activeCut ? "active" : ""}" style="--ruler-color:${state.rulerColors[index]}">${iconMarkup("ruler")}<strong>${index + 1}</strong><i></i></button>`).join("");
  const focusRulers = state.cuts.map((_, index) => `<button type="button" data-focus-ruler="${index}" class="${index === state.activeCut ? "is-active" : ""}" style="--ruler-color:${state.rulerColors[index]}" aria-label="Selecionar régua ${index + 1}" aria-pressed="${index === state.activeCut}">${index + 1}</button>`).join("");
  const lines = state.cuts.map((cut, index) => `<button type="button" class="manual-cut-ruler-line balance-cut-line ${index === state.activeCut ? "is-active" : ""}" data-cut-index="${index}" style="--ruler-color:${state.rulerColors[index]};top:${100 * (cut - start) / total}%" aria-label="Régua ${index + 1}"><b>Régua ${index + 1}</b></button>`).join("");
  const highlights = state.highlightOdd ? pageHighlights(draft?.source_slices || [], start, total) : "";
  const sourceUrl = draft && selection ? balanceamentoImageUrl(selection.provider, selection.manga, selection.chapter, draft.source_preview || "manual-source.png", "editor", draft.proposal_id) : "";
  const image = draft ? `<div class="manual-cut-strip balance-image-wrap" data-stage style="width:${state.zoom}%">${highlights}<img src="${sourceUrl}" alt="Região selecionada para balanceamento" draggable="false">${lines}</div>` : `<p class="balance-canvas-empty">${selection ? state.busy ? "Preparando a prévia dos merges selecionados…" : "A prévia ainda não está disponível." : "Volte a Validar Balanceamento e escolha merges contíguos."}</p>`;
  const count = rulerCount(state);
  const action = editorAction(state, start, end);
  const result = draft ? proposalMarkup(selection, draft, state.busy, state.resultZoom) : "";

  editorHost.querySelector("[data-color-popover]")?.remove();
  editorHost.innerHTML = editorMarkup({ mergeRows, rulers, count, action, image, result, state });
  restoreEditorState({ editorHost, previousImage, previousStage, scroll, mergeScroll, state, focusButton });
  element.querySelector("[data-focus-rulers]").innerHTML = focusRulers;
  element.querySelector("[data-dock-zoom]").textContent = `${state.zoom}%`;
  syncFocusMarker(element, state.highlightOdd);
  const colorPopover = element.querySelector("[data-color-popover]");
  if (colorPopover.parentElement !== document.body) document.body.append(colorPopover);
  colorPopover.querySelector("[data-color-close]").onclick = actions.closeColorPicker;
  bindDock(element, actions);
  return colorPopover;
}

function rulerCount(state) {
  return `<div class="manual-cut-ruler-count"><button type="button" data-cut="remove" aria-label="Remover régua" ${!state.cuts.length || state.busy ? "disabled" : ""}>−</button><output>${state.cuts.length}</output><button type="button" data-cut="add" aria-label="Adicionar régua" ${state.busy || !state.draft ? "disabled" : ""}>+</button></div>`;
}

function editorAction(state, start, end) {
  if (!state.draft) return `<button type="button" class="btn primary" data-prepare ${!state.selection || state.busy ? "disabled" : ""}>${state.busy ? "Preparando editor…" : "Preparar editor"}</button>`;
  return `<button type="button" class="btn primary" data-generate ${state.busy || !validCuts(state.cuts, start, end) ? "disabled" : ""}>✂ Gerar proposta</button>`;
}

function editorMarkup({ mergeRows, rulers, count, action, image, result, state }) {
  return `<div class="manual-cut-workspace balance-cuts-workspace">
    <aside class="manual-cut-panel"><div class="manual-cut-panel-toolbar"><div class="manual-cut-panel-heading"><h2>Réguas</h2></div><div class="manual-cut-panel-tools">${count}<button type="button" class="manual-cut-marker ${state.highlightOdd ? "is-active" : ""}" data-highlight aria-label="Alternar marca-texto" aria-pressed="${state.highlightOdd}"><i class="fa-solid fa-highlighter text-xs" aria-hidden="true"></i></button></div></div>
      <div class="balance-ruler-select"><span>Réguas ativas</span><div data-rulers>${rulers}</div></div><div class="manual-cut-color-popover" data-color-popover hidden><div><strong data-color-title></strong><button type="button" data-color-close aria-label="Fechar seletor de cores">×</button></div><div class="manual-cut-color-options" data-color-options></div></div>
      <div class="manual-cut-pages-heading"><strong>Merges selecionados</strong></div><div class="balance-cuts-merge-list" data-merges>${mergeRows}</div><div class="manual-cut-actions"><p role="status" aria-live="polite">${state.busy ? "Processando…" : ""}</p>${action}</div>
    </aside><section class="manual-cut-viewer"><div class="manual-cut-viewer-toolbar"><strong>Visualizador de emendas</strong><div><div class="zoom-control"><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><output data-zoom-value>${state.zoom}%</output><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><button type="button" data-zoom="reset" aria-label="Visualizar em escala 1 para 1">1:1</button></div><span data-focus-toggle-slot></span></div></div><div class="manual-cut-canvas-wrap ${state.draft ? "" : "is-empty"}" data-canvas>${image}</div><p class="manual-cut-hint">Clique na prévia para posicionar a régua selecionada. Arraste uma régua para ajustá-la.</p></section></div>${result}`;
}

function restoreEditorState({ editorHost, previousImage, previousStage, scroll, mergeScroll, state, focusButton }) {
  const nextCanvas = editorHost.querySelector("[data-canvas]");
  const nextStage = editorHost.querySelector("[data-stage]");
  const nextImage = nextStage?.querySelector("img");
  if (previousImage && nextStage && nextImage && previousImage.getAttribute("src") === nextImage.getAttribute("src")) {
    const children = Array.from(nextStage.childNodes);
    children[children.indexOf(nextImage)] = previousImage;
    previousStage.replaceChildren(...children);
    previousStage.style.width = `${state.zoom}%`;
    nextStage.replaceWith(previousStage);
  }
  if (scroll && nextCanvas) { nextCanvas.scrollTop = scroll.top; nextCanvas.scrollLeft = scroll.left; }
  const mergeList = editorHost.querySelector("[data-merges]");
  if (mergeList) mergeList.scrollTop = mergeScroll;
  editorHost.querySelector("[data-focus-toggle-slot]").append(focusButton);
}

function syncFocusMarker(element, highlight) {
  const marker = element.querySelector("[data-focus-highlight]");
  marker.classList.toggle("is-active", highlight);
  marker.setAttribute("aria-pressed", String(highlight));
}

function bindDock(element, actions) {
  element.querySelectorAll("[data-focus-ruler]").forEach((button) => button.addEventListener("click", () => actions.selectRuler(Number(button.dataset.focusRuler))));
  element.querySelector("[data-focus-add-ruler]").onclick = () => actions.adjustCuts("add");
  element.querySelector("[data-focus-highlight]").onclick = actions.toggleHighlight;
  element.querySelector("[data-focus-submit]").onclick = actions.submitProposal;
}

function pageHighlights(slices, start, total) {
  let cursor = start;
  return slices.map((slice) => {
    const height = Number(slice.height_px ?? slice.height ?? slice.pending_height ?? 0);
    const top = cursor;
    cursor += height;
    if (!height || !isOddPage(slice.file || "")) return "";
    return `<span class="manual-cut-page-highlight" style="top:${100 * (top - start) / total}%;height:${100 * height / total}%"></span>`;
  }).join("");
}

function proposalMarkup(selection, draft, busy, resultZoom) {
  if (!draft.artifacts?.length) return "";
  const cards = draft.artifacts.map((item) => `<figure><figcaption>${escapeHtml(item.file)}</figcaption><img loading="lazy" style="width:${resultZoom}%" src="${balanceamentoImageUrl(selection.provider, selection.manga, selection.chapter, item.file, "proposal", draft.proposal_id)}" alt="${escapeHtml(item.file)}"></figure>`).join("");
  return `<section class="balance-card balance-result-card"><div class="balance-editor-heading"><div><h2>Resultado da proposta</h2><p>A proposta ainda não altera o MERGE oficial.</p></div><div class="balance-result-actions"><div class="zoom-control" aria-label="Zoom do resultado"><button type="button" data-result-zoom="-" aria-label="Diminuir zoom do resultado">−</button><output>${resultZoom}%</output><button type="button" data-result-zoom="+" aria-label="Aumentar zoom do resultado">+</button><button type="button" data-result-zoom="reset" aria-label="Restaurar zoom do resultado">1:1</button></div><button type="button" class="btn primary" data-apply ${busy || draft.status !== "PROPOSTA_GERADA" ? "disabled" : ""}>Aplicar composição final</button></div></div><div class="balance-result-viewport"><div class="balance-result-grid" style="--result-zoom:${resultZoom}%">${cards}</div></div></section>`;
}
