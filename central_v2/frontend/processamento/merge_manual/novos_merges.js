import { getMergeManualSelection, setMergeManualProposal, setMergeManualSelection } from "/_app/state/merge_manual.js";
import { generateMergeManualProposal } from "/_app/api/merge_manual.js";
import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { showMessage } from "/_shared/messages/messages.js";
import { defaultRulerColors, escapeHtml, rulerPalette, rulerIconMarkup, updatePageCutLabels } from "/processamento/merge_manual/novos_merges_view.js";
import { createManualCutPreview } from "/processamento/merge_manual/novos_merges_preview.js";

export function render(container) {
  const selection = getMergeManualSelection();
  const page = document.createElement("section");
  page.className = "manual-cut-page";
  container.replaceChildren(page);
  if (!selection) {
    page.innerHTML = "<h1>Novos Cortes</h1><p>Selecione primeiro uma faixa na página Validar Faixa.</p>";
    return;
  }

  const pages = selection.pendingBlock.pages;
  const first = pages.findIndex((item) => item.file === selection.start);
  const last = pages.findIndex((item) => item.file === selection.end);
  const chosen = pages.slice(first, last + 1);
  const width = chosen[0]?.width || 1;
  const totalHeight = chosen.reduce((sum, item) => sum + item.pending_height, 0);
  const cuts = [...(selection.cuts || [])];
  const rulerColors = [...(selection.rulerColors || defaultRulerColors)];
  while (rulerColors.length < cuts.length) rulerColors.push(defaultRulerColors[rulerColors.length % defaultRulerColors.length]);
  let activeRuler = Math.max(0, cuts.length - 1);
  let zoom = selection.editorZoom || 50;
  let dragging = false;
  let highlightOdd = true;
  let focusedPageFile = null;

  page.innerHTML = `
    <header class="manual-cut-header">
      <button type="button" class="manual-cut-back" data-back>← Voltar à faixa</button>
      <div><h1>Merge Manual · Cap. ${escapeHtml(selection.chapter)}</h1><p>${escapeHtml(selection.start)} → ${escapeHtml(selection.end)} · ${chosen.length} páginas residuais</p></div>
      <span class="manual-cut-isolated">Processamento isolado</span>
    </header>
    <div class="manual-cut-workspace">
      <aside class="manual-cut-panel">
        <div class="manual-cut-panel-toolbar">
          <div class="manual-cut-panel-heading"><h2>Réguas</h2></div>
          <div class="manual-cut-panel-tools"><div class="manual-cut-ruler-count"><button data-count="-1" aria-label="Remover régua">−</button><output data-ruler-count>0</output><button data-count="1" aria-label="Adicionar régua">+</button></div>
            <button type="button" class="manual-cut-marker ${highlightOdd ? "is-active" : ""}" data-highlight aria-label="Alternar marca-texto de páginas ímpares" aria-pressed="true"><i class="fa-solid fa-highlighter text-xs" aria-hidden="true"></i></button>
          </div>
        </div>
        <div class="manual-cut-ruler-select"><span>Réguas ativas</span><div data-rulers></div></div>
        <div class="manual-cut-color-popover" data-color-popover hidden><div><strong data-color-title></strong><button type="button" data-color-close aria-label="Fechar seletor de cores">×</button></div><div class="manual-cut-color-options" data-color-options></div></div>
        <div class="manual-cut-pages-heading"><strong>Páginas no bloco</strong></div>
        <div class="manual-cut-page-list" data-page-list></div>
        <div class="manual-cut-hover-preview" data-page-preview><span data-preview-label>Prévia da página</span><img alt="Prévia da página selecionada" hidden></div>
        <div class="manual-cut-actions"><p role="status" aria-live="polite" data-status></p><button type="button" data-submit>✂ Gerar proposta</button></div>
      </aside>
      <section class="manual-cut-viewer">
        <div class="manual-cut-viewer-toolbar"><strong>Visualizador de emendas</strong><div><div class="zoom-control"><button data-zoom="-" aria-label="Diminuir zoom">−</button><output data-zoom-value>50%</output><button data-zoom="+" aria-label="Aumentar zoom">+</button><button class="zoom-control-reset" data-reset aria-label="Visualizar em escala 1 para 1">1:1</button></div><button type="button" class="manual-cut-toolbar-button" data-focus-toggle aria-label="Modo Foco" aria-pressed="false">${iconMarkup("focus-exit")} Foco</button></div></div>
        <div class="manual-cut-canvas-wrap"><div class="manual-cut-strip"><canvas aria-label="Prévia vertical para posicionar as réguas de corte"></canvas><div class="manual-cut-page-tags" data-page-tags></div></div></div>
        <p class="manual-cut-hint">Clique na prévia para posicionar a régua selecionada. Arraste uma régua para ajustá-la.</p>
      </section>
    </div>
    <aside class="focus-mode-dock" data-focus-dock aria-label="Ferramentas do modo foco">
      <button type="button" data-focus-exit aria-label="Sair do Modo Foco" title="Sair do Modo Foco">${iconMarkup("focus-exit")}</button>
      <span data-focus-divider></span><div data-focus-rulers aria-label="Réguas ativas"></div>
      <button type="button" data-focus-add-ruler aria-label="Adicionar régua" title="Adicionar régua">+</button>
      <span data-focus-divider></span><button type="button" class="focus-mode-marker is-active" data-focus-highlight aria-label="Alternar marca-texto" aria-pressed="true"><i class="fa-solid fa-highlighter text-xs" aria-hidden="true"></i></button>
      <span data-focus-divider></span><div class="focus-mode-zoom"><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><output data-focus-zoom>50%</output><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><button type="button" data-reset aria-label="Visualizar em escala 1 para 1">1:1</button></div>
      <span data-focus-divider></span><button type="button" class="focus-mode-primary" data-focus-submit aria-label="Gerar proposta" title="Gerar proposta">✂</button>
    </aside>`;

  const canvas = page.querySelector("canvas");
  const status = page.querySelector("[data-status]");
  const disposeFocusMode = bindFocusMode(page, { button: page.querySelector("[data-focus-toggle]") });
  const preview = createManualCutPreview({ page, canvas, selection, chosen, width, totalHeight,
    getState: () => ({ zoom, cuts, highlightOdd, rulerColors, focusedPageFile }),
    onSelectPage: (selectedPage) => { focusedPageFile = selectedPage.file; },
  });
  const draw = preview.draw;
  const colorPopover = page.querySelector("[data-color-popover]");
  document.body.append(colorPopover);

  function updateRulers() {
    page.querySelector("[data-ruler-count]").textContent = String(cuts.length);
    page.querySelector("[data-rulers]").innerHTML = cuts.map((_, index) => `<button type="button" data-ruler="${index}" class="manual-cut-ruler-button ${index === activeRuler ? "active" : ""}" style="--ruler-color:${rulerColors[index]}">${rulerIconMarkup(rulerColors[index])}<strong>${index + 1}</strong><i></i></button>`).join("");
    page.querySelector("[data-focus-rulers]").innerHTML = cuts.map((_, index) => `<button type="button" data-focus-ruler="${index}" class="${index === activeRuler ? "is-active" : ""}" style="--ruler-color:${rulerColors[index]}" aria-label="Selecionar régua ${index + 1}" aria-pressed="${index === activeRuler}">${index + 1}</button>`).join("");
    page.querySelectorAll("[data-ruler]").forEach((button) => button.addEventListener("click", () => {
      activeRuler = Number(button.dataset.ruler); updateRulers(); draw();
      openColorPicker(page.querySelector(`.manual-cut-ruler-select [data-ruler="${activeRuler}"]`), activeRuler);
    }));
    page.querySelectorAll("[data-focus-ruler]").forEach((button) => button.addEventListener("click", () => { activeRuler = Number(button.dataset.focusRuler); updateRulers(); draw(); }));
    updatePageCutLabels(page, chosen, cuts, rulerColors);
    draw();
  }

  function locateCut(event) {
    const bounds = canvas.getBoundingClientRect();
    return Math.round((event.clientY - bounds.top) * canvas.height / bounds.height);
  }

  function onPointerDown(event) {
    const y = locateCut(event);
    const tolerance = Math.max(24, canvas.height * 12 / canvas.getBoundingClientRect().height);
    const nearest = cuts.findIndex((cut) => cut != null && Math.abs(cut - y) <= tolerance);
    if (nearest >= 0) activeRuler = nearest;
    if (!cuts.length) {
      showMessage({ title: "Nenhuma régua ativa", message: "Adicione uma régua antes de posicionar o corte." });
      return;
    }
    cuts[activeRuler] = Math.max(1, Math.min(totalHeight - 1, y));
    dragging = true; canvas.setPointerCapture(event.pointerId); updateRulers();
  }
  function onPointerMove(event) { if (dragging) { cuts[activeRuler] = Math.max(1, Math.min(totalHeight - 1, locateCut(event))); updateRulers(); } }
  function onPointerUp() { dragging = false; }

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  page.querySelector("[data-back]").addEventListener("click", () => navigate(container, "validar-faixa"));
  page.querySelector("[data-highlight]").addEventListener("click", (event) => {
    toggleHighlight(event.currentTarget);
  });
  page.querySelector("[data-focus-highlight]").addEventListener("click", (event) => toggleHighlight(event.currentTarget));
  page.querySelectorAll("[data-count]").forEach((button) => button.addEventListener("click", () => changeRulerCount(Number(button.dataset.count))));
  page.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => adjustZoom(button.dataset.zoom === "+" ? 10 : -10)));
  page.querySelectorAll("[data-reset]").forEach((button) => button.addEventListener("click", () => { zoom = 100; draw(); }));
  page.querySelector("[data-submit]").addEventListener("click", submitProposal);
  page.querySelector("[data-focus-add-ruler]").addEventListener("click", () => changeRulerCount(1));
  page.querySelector("[data-focus-submit]").addEventListener("click", submitProposal);
  colorPopover.querySelector("[data-color-close]").addEventListener("click", closeColorPicker);
  document.addEventListener("pointerdown", onOutsideColorPicker);
  updateRulers();
  draw();

  function toggleHighlight(button) {
    highlightOdd = !highlightOdd;
    page.querySelectorAll("[data-highlight], [data-focus-highlight]").forEach((item) => {
      item.classList.toggle("is-active", highlightOdd);
      item.setAttribute("aria-pressed", String(highlightOdd));
    });
    draw();
  }
  function adjustZoom(delta) { zoom = Math.max(30, Math.min(150, zoom + delta)); draw(); }

  function openColorPicker(anchor, index) {
    colorPopover.querySelector("[data-color-title]").textContent = `Cor da Régua ${index + 1}`;
    colorPopover.querySelector("[data-color-options]").innerHTML = rulerPalette.map((color) => `<button type="button" data-color="${color.value}" class="${rulerColors[index] === color.value ? "selected" : ""}" aria-label="${color.name}" title="Selecionar cor"><i style="--swatch:${color.value}"></i></button>`).join("");
    const bounds = anchor.getBoundingClientRect();
    colorPopover.hidden = false;
    colorPopover.style.left = `${Math.max(12, Math.min(window.innerWidth - 248, bounds.left))}px`;
    colorPopover.style.top = `${Math.max(12, Math.min(window.innerHeight - 170, bounds.bottom + 8))}px`;
    colorPopover.querySelectorAll("[data-color]").forEach((button) => button.addEventListener("click", () => {
      rulerColors[index] = button.dataset.color;
      closeColorPicker(); updateRulers();
    }));
  }

  function closeColorPicker() { colorPopover.hidden = true; }
  function onOutsideColorPicker(event) {
    if (!colorPopover.contains(event.target) && !event.target.closest("[data-ruler]")) closeColorPicker();
  }
  function changeRulerCount(delta) {
    if (delta > 0) {
      const colorIndex = cuts.length;
      while (rulerColors.length <= colorIndex) rulerColors.push(defaultRulerColors[colorIndex % defaultRulerColors.length]);
      cuts.push(Math.round(totalHeight * (cuts.length + 1) / (cuts.length + 2)));
      activeRuler = cuts.length - 1;
    } else if (delta < 0 && cuts.length) {
      cuts.splice(activeRuler, 1);
      rulerColors.splice(activeRuler, 1);
      activeRuler = Math.max(0, Math.min(activeRuler, cuts.length - 1));
    }
    updateRulers();
  }

  async function submitProposal(event) {
    const button = event.currentTarget || event;
    button.disabled = true; status.textContent = "Gerando proposta e validando as fontes…";
    try {
      const result = await generateMergeManualProposal({ provider: selection.provider, manga: selection.manga,
        chapter: selection.chapter, block_id: selection.blockId, start: selection.start, end: selection.end }, cuts.filter(Number.isInteger));
      setMergeManualSelection({ ...selection, cuts: [...cuts], rulerColors: [...rulerColors], editorZoom: zoom });
      setMergeManualProposal(result);
      navigate(container, "merge-manual-result");
    } catch (error) {
      status.textContent = "";
      await showMessage({ title: "Falha ao gerar proposta", message: error.message });
    }
    finally { button.disabled = false; }
  }

  return () => {
    canvas.removeEventListener("pointerdown", onPointerDown);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerup", onPointerUp);
    document.removeEventListener("pointerdown", onOutsideColorPicker);
    disposeFocusMode();
    colorPopover.remove();
  };
}
function navigate(container, action) { container.dispatchEvent(new CustomEvent("menu:action", { bubbles: true, detail: { action } })); }
