import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { balanceamentoImageUrl } from "/_app/api/balanceamento.js";

export function createBalanceCutsView(handlers) {
  const element = document.createElement("section");
  element.className = "balance-cuts-page focus-mode-root";
  element.innerHTML = `<header class="balance-heading"><button type="button" class="btn" data-back>← Validar Estado</button><div><h1>Novos Cortes</h1><p data-subtitle>Selecione uma sequência de merges contíguos na validação.</p></div></header>
    <div class="balance-cuts-toolbar"><div data-toolbar></div><button type="button" class="btn balance-focus-toggle" data-focus-toggle aria-label="Modo Foco" aria-pressed="false">${iconMarkup("focus-exit")} Foco</button></div><div class="balance-cuts-editor" data-editor></div>
    <aside class="focus-mode-dock focus-mode-compact" data-focus-dock aria-label="Controles do editor em foco">
      <button type="button" data-focus-exit aria-label="Sair do Modo Foco" title="Sair do Modo Foco"><span>×</span></button><span data-focus-divider></span>
      <div class="focus-mode-zoom"><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><output data-dock-zoom>50%</output><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><button type="button" data-zoom="reset" aria-label="Visualizar em escala 1 para 1">1:1</button></div>
    </aside>`;
  const toolbar = element.querySelector("[data-toolbar]");
  const editorHost = element.querySelector("[data-editor]");
  const subtitle = element.querySelector("[data-subtitle]");
  let state = { selection: null, draft: null, zoom: 50, activeCut: 0, cuts: [], busy: false };
  const disposeFocusMode = bindFocusMode(element, { button: element.querySelector("[data-focus-toggle]") });
  element.addEventListener("click", onClick);
  editorHost.addEventListener("pointerdown", onPointerDown);
  element.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => {
    const zoom = button.dataset.zoom === "reset" ? 100 : clamp(state.zoom + (button.dataset.zoom === "+" ? 10 : -10), 30, 200);
    update({ zoom });
    handlers.onZoom(zoom);
  }));
  element.querySelector("[data-back]").addEventListener("click", handlers.onBack);

  function update(next) {
    state = { ...state, ...next };
    if (Object.hasOwn(next, "draft")) state.cuts = cutValues(next.draft);
    subtitle.textContent = state.selection
      ? `Cap. ${state.selection.chapter} · ${state.selection.merges.length} merges selecionados`
      : "Selecione uma sequência de merges contíguos na validação.";
    element.querySelectorAll("[data-dock-zoom]").forEach((node) => { node.textContent = `${state.zoom}%`; });
    drawToolbar(); drawEditor();
  }

  function drawToolbar() {
    const zoom = `<div class="zoom-control"><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><output>${state.zoom}%</output><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><button type="button" data-zoom="reset" aria-label="Visualizar em escala 1 para 1">1:1</button></div>`;
    toolbar.innerHTML = zoom;
    element.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => {
      const zoom = button.dataset.zoom === "reset" ? 100 : clamp(state.zoom + (button.dataset.zoom === "+" ? 10 : -10), 30, 200);
      update({ zoom }); handlers.onZoom(zoom);
    }));
  }

  function drawEditor() {
    const selection = state.selection;
    if (!selection) { editorHost.innerHTML = `<div class="balance-empty">Volte a Validar Estado, escolha merges contíguos e abra Novos Cortes.</div>`; return; }
    const draft = state.draft;
    if (!draft) {
      editorHost.innerHTML = `<section class="balance-card"><h2>Região selecionada</h2><p>${escapeHtml(selection.merges.join(" · "))}</p><p class="balance-muted">A preparação cria uma prévia a partir das imagens originais e carrega as fronteiras atuais como cortes iniciais.</p><button type="button" class="btn primary" data-prepare ${state.busy ? "disabled" : ""}>Preparar editor</button></section>`;
      return;
    }
    const start = Number(draft.region?.global_start);
    const end = Number(draft.region?.global_end);
    const total = end - start;
    const sourceUrl = balanceamentoImageUrl(selection.provider, selection.manga, selection.chapter, draft.source_preview || "manual-source.png", "editor", draft.proposal_id);
    const lines = state.cuts.map((cut, index) => `<button type="button" class="balance-cut-line ${index === state.activeCut ? "is-active" : ""}" data-cut-index="${index}" style="top:${100 * (cut - start) / total}%" aria-label="Corte ${index + 1}"><span>Corte ${index + 1}</span></button>`).join("");
    const labels = (draft.source_slices || []).map((slice) => `<span style="top:${100 * (slice.global_start - start) / total}%;height:${100 * (slice.global_end - slice.global_start) / total}%">${escapeHtml(slice.file)}</span>`).join("");
    editorHost.innerHTML = `<section class="balance-card"><div class="balance-editor-heading"><div><h2>Editar cortes</h2><p>Arraste uma linha ou selecione-a e clique na imagem para posicioná-la.</p></div><div class="balance-cut-count"><button type="button" data-cut="remove" aria-label="Remover corte" ${!state.cuts.length || state.busy ? "disabled" : ""}>−</button><output>${state.cuts.length}</output><button type="button" data-cut="add" aria-label="Adicionar corte" ${state.busy ? "disabled" : ""}>+</button></div></div>
      <div class="balance-workarea"><div class="balance-slice-labels">${labels}</div><div class="balance-image-viewport"><div class="balance-image-wrap" data-stage style="width:${state.zoom}%"><img src="${sourceUrl}" alt="Região selecionada para balanceamento" draggable="false">${lines}</div></div></div>
      <div class="balance-actions"><span>${state.cuts.length + 1} segmentos previstos</span><button type="button" class="btn primary" data-generate ${state.busy || !validCuts(state.cuts, start, end) ? "disabled" : ""}>Gerar proposta manual</button></div>
      ${draft.status === "EFETIVADO" ? `<p class="balance-success">Esta proposta já foi aplicada ao MERGE oficial.</p>` : ""}</section>${proposalMarkup(selection, draft, state.busy)}`;
  }

  function onClick(event) {
    if (event.target.closest("[data-prepare]")) handlers.onPrepare();
    if (event.target.closest("[data-generate]")) handlers.onGenerate([...state.cuts]);
    const line = event.target.closest("[data-cut-index]");
    if (line) update({ activeCut: Number(line.dataset.cutIndex) });
    const control = event.target.closest("[data-cut]");
    if (control) adjustCuts(control.dataset.cut);
    if (event.target.closest("[data-apply]")) handlers.onApply();
  }

  function onPointerDown(event) {
    const stage = event.target.closest("[data-stage]");
    if (!stage || !state.cuts.length) return;
    event.preventDefault();
    const line = event.target.closest("[data-cut-index]");
    if (line) state.activeCut = Number(line.dataset.cutIndex);
    const move = (pointer) => {
      const bounds = stage.getBoundingClientRect();
      const value = Math.round(Number(state.draft.region.global_start) + (pointer.clientY - bounds.top) / bounds.height * (Number(state.draft.region.global_end) - Number(state.draft.region.global_start)));
      const index = state.activeCut;
      const lower = index > 0 ? state.cuts[index - 1] + 1 : Number(state.draft.region.global_start) + 1;
      const upper = index < state.cuts.length - 1 ? state.cuts[index + 1] - 1 : Number(state.draft.region.global_end) - 1;
      if (lower > upper) return;
      const cut = clamp(value, lower, upper);
      state.cuts.splice(state.activeCut, 1);
      state.activeCut = state.cuts.findIndex((current) => current > cut);
      if (state.activeCut < 0) state.activeCut = state.cuts.length;
      state.cuts.splice(state.activeCut, 0, cut);
      stage.querySelectorAll("[data-cut-index]").forEach((item, index) => {
        item.style.top = `${100 * (state.cuts[index] - Number(state.draft.region.global_start)) / (Number(state.draft.region.global_end) - Number(state.draft.region.global_start))}%`;
        item.classList.toggle("is-active", index === state.activeCut);
      });
    };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); drawEditor(); };
    move(event);
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up, { once: true });
  }

  function adjustCuts(action) {
    if (action === "remove") { state.cuts.splice(Math.min(state.activeCut, state.cuts.length - 1), 1); state.activeCut = Math.max(0, state.cuts.length - 1); }
    else if (state.cuts.length === 0) state.cuts.push(Math.round((Number(state.draft.region.global_start) + Number(state.draft.region.global_end)) / 2));
    else {
      const bounds = [Number(state.draft.region.global_start), ...state.cuts, Number(state.draft.region.global_end)];
      let gap = 0; for (let i = 1; i < bounds.length - 1; i += 1) if (bounds[i + 1] - bounds[i] > bounds[gap + 1] - bounds[gap]) gap = i;
      if (bounds[gap + 1] - bounds[gap] < 2) return;
      const cut = Math.round((bounds[gap] + bounds[gap + 1]) / 2);
      state.cuts.push(cut); state.cuts.sort((a, b) => a - b); state.activeCut = state.cuts.indexOf(cut);
    }
    update({ cuts: [...state.cuts] });
  }

  update({});
  return { element, update, dispose() { disposeFocusMode(); element.removeEventListener("click", onClick); editorHost.removeEventListener("pointerdown", onPointerDown); } };
}

function cutValues(draft) {
  return (draft?.cuts || []).map((cut) => Number(cut.selected_y)).filter(Number.isFinite).sort((a, b) => a - b);
}
function validCuts(cuts, start, end) { return cuts.length > 0 && cuts.every((cut, index) => cut > start && cut < end && (!index || cut > cuts[index - 1])); }
function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
function proposalMarkup(selection, draft, busy) {
  if (!draft.artifacts?.length) return "";
  const cards = draft.artifacts.map((item, index) => `<figure><img loading="lazy" src="${balanceamentoImageUrl(selection.provider, selection.manga, selection.chapter, item.file, "proposal", draft.proposal_id)}" alt="Segmento ${index + 1} da proposta"><figcaption>Segmento ${index + 1} · ${Number(item.height).toLocaleString("pt-BR")} px</figcaption></figure>`).join("");
  return `<section class="balance-card"><div class="balance-editor-heading"><div><h2>Resultado da proposta</h2><p>A proposta ainda não altera o MERGE oficial.</p></div><button type="button" class="btn primary" data-apply ${busy || draft.status !== "PROPOSTA_GERADA" ? "disabled" : ""}>Aplicar composição final</button></div><div class="balance-result-grid">${cards}</div></section>`;
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
