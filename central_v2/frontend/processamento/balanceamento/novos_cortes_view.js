import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { balanceamentoImageUrl } from "/_app/api/balanceamento.js";
import { defaultRulerColors, rulerPalette } from "/processamento/merge_manual/novos_merges_view.js";
import { clamp, cutValues, renderCutsEditor, validCuts } from "/processamento/balanceamento/novos_cortes_render.js";

export function createBalanceCutsView(handlers) {
  const element = document.createElement("section");
  element.className = "manual-cut-page focus-mode-root balance-cuts-page";
  element.innerHTML = `<header class="manual-cut-header">
      <button type="button" class="manual-cut-back btn" data-back>← Validar Balanceamento</button>
      <div><h1>Balanceamento · Novos Cortes</h1><p data-subtitle>Selecione merges para ajustar.</p></div>
      <span class="manual-cut-isolated">Proposta isolada</span>
    </header><div data-editor></div>
    <div class="balance-hover-preview balance-cuts-preview" role="tooltip" hidden><img alt=""></div>
    <aside class="focus-mode-dock" data-focus-dock aria-label="Ferramentas do modo foco">
      <button type="button" data-focus-exit aria-label="Sair do Modo Foco" title="Sair do Modo Foco">${iconMarkup("focus-exit")}</button>
      <span data-focus-divider></span><div data-focus-rulers aria-label="Réguas ativas"></div>
      <button type="button" data-focus-add-ruler aria-label="Adicionar régua" title="Adicionar régua">+</button>
      <span data-focus-divider></span><button type="button" class="focus-mode-marker is-active" data-focus-highlight aria-label="Alternar marca-texto" aria-pressed="true"><i class="fa-solid fa-highlighter text-xs" aria-hidden="true"></i></button>
      <span data-focus-divider></span><div class="focus-mode-zoom"><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><output data-dock-zoom>50%</output><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><button type="button" data-zoom="reset" aria-label="Visualizar em escala 1 para 1">1:1</button></div>
      <span data-focus-divider></span><button type="button" class="focus-mode-primary" data-focus-submit aria-label="Gerar proposta" title="Gerar proposta">✂</button>
    </aside>`;

  const editorHost = element.querySelector("[data-editor]");
  const subtitle = element.querySelector("[data-subtitle]");
  const preview = element.querySelector(".balance-cuts-preview");
  const focusButton = document.createElement("button");
  focusButton.type = "button";
  focusButton.className = "manual-cut-toolbar-button";
  focusButton.setAttribute("aria-label", "Modo Foco");
  focusButton.setAttribute("aria-pressed", "false");
  focusButton.innerHTML = `${iconMarkup("focus-exit")} Foco`;
  let state = { selection: null, draft: null, zoom: 50, resultZoom: 100, activeCut: 0, cuts: [], rulerColors: [...defaultRulerColors], highlightOdd: true, busy: false };
  let colorPopover;
  let disposeFocusMode = () => {};
  element.addEventListener("click", onClick);
  editorHost.addEventListener("pointerdown", onPointerDown);
  editorHost.addEventListener("pointerover", onPreviewOver);
  editorHost.addEventListener("pointerout", onPreviewOut);
  document.addEventListener("pointerdown", onOutsideColorPicker);
  disposeFocusMode = bindFocusMode(element, { button: focusButton });

  function update(next) {
    state = { ...state, ...next };
    if (Object.hasOwn(next, "draft")) {
      state.cuts = cutValues(next.draft);
      state.rulerColors = next.draft?.ruler_colors?.length ? [...next.draft.ruler_colors] : [...state.rulerColors];
      while (state.rulerColors.length < state.cuts.length) state.rulerColors.push(defaultRulerColors[state.rulerColors.length % defaultRulerColors.length]);
      state.activeCut = Math.min(state.activeCut, Math.max(0, state.cuts.length - 1));
    }
    const selection = state.selection;
    subtitle.textContent = selection
      ? `Cap. ${selection.chapter} · ${selection.merges.length} merges selecionados`
      : "Selecione merges para ajustar.";
    drawEditor();
  }

  function drawEditor() {
    colorPopover = renderCutsEditor({
      element, editorHost, preview, focusButton, state,
      actions: {
        closeColorPicker,
        selectRuler,
        adjustCuts,
        toggleHighlight,
        submitProposal,
      },
    });
  }

  function onClick(event) {
    const resultZoom = event.target.closest("[data-result-zoom]");
    if (resultZoom) {
      const direction = resultZoom.dataset.resultZoom;
      state.resultZoom = direction === "reset" ? 100 : clamp(state.resultZoom + (direction === "+" ? 10 : -10), 30, 200);
      drawEditor();
      return;
    }
    const zoom = event.target.closest("[data-zoom]");
    if (zoom) { adjustZoom(zoom.dataset.zoom); return; }
    if (event.target.closest("[data-back]")) { handlers.onBack(); return; }
    if (event.target.closest("[data-prepare]")) { handlers.onPrepare([...state.rulerColors]); return; }
    if (event.target.closest("[data-generate]")) { submitProposal(); return; }
    if (event.target.closest("[data-apply]")) { handlers.onApply(); return; }
    const ruler = event.target.closest("[data-ruler]");
    if (ruler) { selectRuler(Number(ruler.dataset.ruler), ruler); return; }
    const line = event.target.closest("[data-cut-index]");
    if (line) { state.activeCut = Number(line.dataset.cutIndex); drawEditor(); return; }
    if (event.target.closest("[data-highlight]")) { toggleHighlight(); return; }
    const control = event.target.closest("[data-cut]");
    if (control) adjustCuts(control.dataset.cut);
  }

  function onPointerDown(event) {
    const stage = event.target.closest("[data-stage]");
    if (!stage || !state.draft || !state.cuts.length) return;
    event.preventDefault();
    const line = event.target.closest("[data-cut-index]");
    if (line) state.activeCut = Number(line.dataset.cutIndex);
    const bounds = stage.getBoundingClientRect();
    const move = (pointer) => {
      const y = Math.round(startY() + (pointer.clientY - bounds.top) / bounds.height * (endY() - startY()));
      const index = state.activeCut;
      const lower = index > 0 ? state.cuts[index - 1] + 1 : startY() + 1;
      const upper = index < state.cuts.length - 1 ? state.cuts[index + 1] - 1 : endY() - 1;
      if (lower > upper) return;
      state.cuts[index] = clamp(y, lower, upper);
      const active = stage.querySelector(`[data-cut-index="${index}"]`);
      active.style.top = `${100 * (state.cuts[index] - startY()) / (endY() - startY())}%`;
    };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); drawEditor(); };
    move(event);
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up, { once: true });
  }

  function onPreviewOver(event) {
    const row = event.target.closest("[data-merge-preview]");
    if (!row || row.contains(event.relatedTarget)) return;
    const selection = state.selection;
    if (!selection) return;
    const rect = row.getBoundingClientRect();
    const image = preview.querySelector("img");
    image.src = balanceamentoImageUrl(selection.provider, selection.manga, selection.chapter, row.dataset.mergePreview, "merge");
    image.alt = row.dataset.mergePreview;
    preview.hidden = false;
    const width = preview.getBoundingClientRect().width || 180;
    const height = preview.getBoundingClientRect().height || 280;
    preview.style.left = `${rect.right + width + 12 < innerWidth ? rect.right + 12 : Math.max(8, rect.left - width - 12)}px`;
    preview.style.top = `${Math.max(8, Math.min(rect.top, innerHeight - height - 8))}px`;
  }

  function onPreviewOut(event) {
    if (event.target.closest("[data-merge-preview]") && !event.target.closest("[data-merge-preview]").contains(event.relatedTarget)) preview.hidden = true;
  }

  function selectRuler(index, anchor) {
    state.activeCut = index;
    drawEditor();
    if (anchor) openColorPicker(editorHost.querySelector(`[data-ruler="${index}"]`), index);
  }

  function openColorPicker(anchor, index) {
    colorPopover.querySelector("[data-color-title]").textContent = `Cor da Régua ${index + 1}`;
    colorPopover.querySelector("[data-color-options]").innerHTML = rulerPalette.map((color) => `<button type="button" data-color="${color.value}" class="${state.rulerColors[index] === color.value ? "selected" : ""}" aria-label="${color.name}" title="Selecionar cor"><i style="--swatch:${color.value}"></i></button>`).join("");
    const rect = anchor.getBoundingClientRect();
    colorPopover.hidden = false;
    colorPopover.style.left = `${Math.max(12, Math.min(innerWidth - 248, rect.left))}px`;
    colorPopover.style.top = `${Math.max(12, Math.min(innerHeight - 170, rect.bottom + 8))}px`;
    colorPopover.querySelectorAll("[data-color]").forEach((button) => button.addEventListener("click", () => {
      state.rulerColors[index] = button.dataset.color;
      closeColorPicker(); drawEditor();
    }));
  }

  function closeColorPicker() { if (colorPopover) colorPopover.hidden = true; }
  function onOutsideColorPicker(event) {
    if (colorPopover && !colorPopover.contains(event.target) && !event.target.closest("[data-ruler]")) closeColorPicker();
  }
  function toggleHighlight() {
    state.highlightOdd = !state.highlightOdd;
    drawEditor();
  }
  function adjustZoom(direction) {
    state.zoom = direction === "reset" ? 100 : clamp(state.zoom + (direction === "+" ? 10 : -10), 30, 200);
    drawEditor(); handlers.onZoom(state.zoom);
  }
  function adjustCuts(direction) {
    if (!state.draft) return;
    if (direction === "remove") {
      state.cuts.splice(state.activeCut, 1);
      state.rulerColors.splice(state.activeCut, 1);
      state.activeCut = Math.max(0, Math.min(state.activeCut, state.cuts.length - 1));
    } else {
      const bounds = [startY(), ...state.cuts, endY()];
      let gap = 0;
      for (let index = 1; index < bounds.length - 1; index += 1) if (bounds[index + 1] - bounds[index] > bounds[gap + 1] - bounds[gap]) gap = index;
      if (bounds[gap + 1] - bounds[gap] < 2) return;
      const cut = Math.round((bounds[gap] + bounds[gap + 1]) / 2);
      state.cuts.push(cut); state.cuts.sort((a, b) => a - b);
      state.rulerColors.splice(state.cuts.indexOf(cut), 0, defaultRulerColors[state.cuts.length % defaultRulerColors.length]);
      state.activeCut = state.cuts.indexOf(cut);
    }
    drawEditor();
  }
  function submitProposal() { if (state.cuts.length && validCuts(state.cuts, startY(), endY())) handlers.onGenerate([...state.cuts], [...state.rulerColors]); }
  function startY() { return Number(state.draft.region.global_start); }
  function endY() { return Number(state.draft.region.global_end); }

  update({});
  return { element, update, dispose() { disposeFocusMode(); document.removeEventListener("pointerdown", onOutsideColorPicker); colorPopover?.remove(); preview.remove(); element.removeEventListener("click", onClick); editorHost.removeEventListener("pointerdown", onPointerDown); editorHost.removeEventListener("pointerover", onPreviewOver); editorHost.removeEventListener("pointerout", onPreviewOut); } };
}
