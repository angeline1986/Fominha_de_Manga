import { getMergeManualSelection } from "/_app/state/merge_manual.js";
import { generateMergeManualProposal, mergeManualImageUrl } from "/_app/api/merge_manual.js";
import { defaultRulerColors, drawPageList, drawPageTags, escapeHtml, rulerPalette, rulerIconMarkup, updatePageCutLabels } from "/processamento/merge_manual/novos_merges_view.js";

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
  const cuts = [];
  const rulerColors = [...defaultRulerColors];
  let activeRuler = 0;
  let zoom = 50;
  let baseReady = false;
  let basePromise;
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
        <div class="manual-cut-viewer-toolbar"><strong>Visualizador de emendas</strong><div class="zoom-control"><button data-zoom="-" aria-label="Diminuir zoom">−</button><output data-zoom-value>50%</output><button data-zoom="+" aria-label="Aumentar zoom">+</button><button class="zoom-control-reset" data-reset aria-label="Visualizar em escala 1 para 1">1:1</button></div></div>
        <div class="manual-cut-canvas-wrap"><div class="manual-cut-strip"><canvas aria-label="Prévia vertical para posicionar as réguas de corte"></canvas><div class="manual-cut-page-tags" data-page-tags></div></div></div>
        <p class="manual-cut-hint">Clique na prévia para posicionar a régua selecionada. Arraste uma régua para ajustá-la.</p>
      </section>
    </div>`;

  const canvas = page.querySelector("canvas");
  const ctx = canvas.getContext("2d");
  const baseCanvas = document.createElement("canvas");
  const baseContext = baseCanvas.getContext("2d");
  const status = page.querySelector("[data-status]");
  canvas.width = baseCanvas.width = width;
  canvas.height = baseCanvas.height = totalHeight;
  drawPageTags(page, chosen, width, totalHeight, zoom, cuts, highlightOdd, rulerColors, focusedPageFile);
  drawPageList(page, chosen, selection, cuts, rulerColors, (selectedPage) => {
    focusedPageFile = selectedPage.file;
    const pageOffset = chosen.slice(0, chosen.indexOf(selectedPage))
      .reduce((sum, item) => sum + item.pending_height, 0);
    drawPageTags(page, chosen, width, totalHeight, zoom, cuts, highlightOdd, rulerColors, focusedPageFile);
    const viewer = page.querySelector(".manual-cut-canvas-wrap");
    viewer.scrollTo({ top: pageOffset * zoom / 100, behavior: "smooth" });
  });
  const colorPopover = page.querySelector("[data-color-popover]");
  document.body.append(colorPopover);

  async function loadBase() {
    if (baseReady) return;
    if (!basePromise) basePromise = (async () => {
      let y = 0;
      for (const item of chosen) {
        const image = new Image();
        image.src = mergeManualImageUrl(selection.provider, selection.manga, selection.chapter, item.file);
        await image.decode();
        baseContext.drawImage(image, 0, item.source_y_start, width, item.pending_height, 0, y, width, item.pending_height);
        y += item.pending_height;
      }
      baseReady = true;
    })();
    return basePromise;
  }

  function draw() {
    canvas.style.width = `${width * zoom / 100}px`;
    page.querySelector("[data-zoom-value]").textContent = `${zoom}%`;
    drawPageTags(page, chosen, width, totalHeight, zoom, cuts, highlightOdd, rulerColors, focusedPageFile);
    loadBase().then(() => {
      ctx.clearRect(0, 0, width, totalHeight);
      ctx.drawImage(baseCanvas, 0, 0);
    }).catch((error) => { status.textContent = `Não foi possível carregar a prévia: ${error.message}`; });
  }

  function updateRulers() {
    page.querySelector("[data-ruler-count]").textContent = String(cuts.length);
    page.querySelector("[data-rulers]").innerHTML = cuts.map((_, index) => `<button type="button" data-ruler="${index}" class="manual-cut-ruler-button ${index === activeRuler ? "active" : ""}" style="--ruler-color:${rulerColors[index]}">${rulerIconMarkup(rulerColors[index])}<strong>${index + 1}</strong><i></i></button>`).join("");
    page.querySelectorAll("[data-ruler]").forEach((button) => button.addEventListener("click", () => {
      activeRuler = Number(button.dataset.ruler); updateRulers(); draw();
      openColorPicker(page.querySelector(`[data-ruler="${activeRuler}"]`), activeRuler);
    }));
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
    if (!cuts.length) { status.textContent = "Adicione uma régua antes de posicionar o corte."; return; }
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
    highlightOdd = !highlightOdd;
    event.currentTarget.classList.toggle("is-active", highlightOdd);
    event.currentTarget.setAttribute("aria-pressed", String(highlightOdd));
    draw();
  });
  page.querySelectorAll("[data-count]").forEach((button) => button.addEventListener("click", () => changeRulerCount(Number(button.dataset.count))));
  page.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => { zoom = Math.max(30, Math.min(150, zoom + (button.dataset.zoom === "+" ? 10 : -10))); draw(); }));
  page.querySelector("[data-reset]").addEventListener("click", () => { zoom = 100; draw(); });
  page.querySelector("[data-submit]").addEventListener("click", submitProposal);
  colorPopover.querySelector("[data-color-close]").addEventListener("click", closeColorPicker);
  document.addEventListener("pointerdown", onOutsideColorPicker);
  draw();

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
    if (delta > 0 && cuts.length < rulerColors.length) {
      cuts.push(Math.round(totalHeight * (cuts.length + 1) / (cuts.length + 2)));
      rulerColors.push(defaultRulerColors[rulerColors.length]);
      activeRuler = cuts.length - 1;
    } else if (delta < 0 && cuts.length) {
      cuts.splice(activeRuler, 1); rulerColors.splice(activeRuler, 1);
      activeRuler = Math.max(0, Math.min(activeRuler, cuts.length - 1));
    }
    updateRulers();
  }

  async function submitProposal(event) {
    const button = event.currentTarget;
    button.disabled = true; status.textContent = "Gerando proposta e validando as fontes…";
    try {
      const result = await generateMergeManualProposal({ provider: selection.provider, manga: selection.manga,
        chapter: selection.chapter, block_id: selection.blockId, start: selection.start, end: selection.end }, cuts.filter(Number.isInteger));
      status.textContent = `Proposta ${result.proposal_id} gerada com ${result.outputs?.length || 0} bloco(s).`;
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  }
  return () => {
    canvas.removeEventListener("pointerdown", onPointerDown);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerup", onPointerUp);
    document.removeEventListener("pointerdown", onOutsideColorPicker);
    colorPopover.remove();
  };
}

function navigate(container, action) { container.dispatchEvent(new CustomEvent("menu:action", { bubbles: true, detail: { action } })); }
