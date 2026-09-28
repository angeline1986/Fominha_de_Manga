import { getMergeManualSelection } from "/_app/state/merge_manual.js";
import { generateMergeManualProposal, mergeManualImageUrl } from "/_app/api/merge_manual.js";

export function render(container) {
  const selection = getMergeManualSelection();
  const page = document.createElement("section");
  page.className = "manual-cut-page";
  container.replaceChildren(page);
  if (!selection) {
    page.innerHTML = "<h1>Novos Cortes</h1><p>Selecione primeiro uma faixa na página Validar Faixa.</p>";
    return;
  }

  page.innerHTML = `
    <header><h1>Novos Cortes · Cap. ${escapeHtml(selection.chapter)}</h1>
      <p>${escapeHtml(selection.start)} → ${escapeHtml(selection.end)} · Clique na prévia para adicionar réguas de corte.</p></header>
    <div class="manual-cut-toolbar"><button type="button" data-back>← Voltar à faixa</button><span data-cut-count>0 cortes</span>
      <button type="button" data-clear>Limpar réguas</button>
      <button type="button" data-submit>Gerar proposta</button></div>
    <p class="manual-cut-status" role="status" aria-live="polite"></p>
    <div class="manual-cut-canvas-wrap"><canvas aria-label="Prévia vertical para posicionar as réguas de corte"></canvas></div>
  `;
  const canvas = page.querySelector("canvas");
  const ctx = canvas.getContext("2d");
  const status = page.querySelector(".manual-cut-status");
  const cuts = [];
  const block = selection.pendingBlock;
  const pages = block.pages;
  const first = pages.findIndex((item) => item.file === selection.start);
  const last = pages.findIndex((item) => item.file === selection.end);
  const chosen = pages.slice(first, last + 1);
  let totalHeight = chosen.reduce((sum, item) => sum + item.pending_height, 0);
  const width = chosen[0]?.width || 1;
  canvas.width = width;
  canvas.height = totalHeight;
  const baseCanvas = document.createElement("canvas");
  const baseContext = baseCanvas.getContext("2d");
  baseCanvas.width = width;
  baseCanvas.height = totalHeight;

  async function loadImages() {
    await loadBase();
    drawCuts();
  }

  function drawCuts() {
    loadBase().then(() => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(baseCanvas, 0, 0);
      ctx.save(); ctx.strokeStyle = "#188AB4"; ctx.lineWidth = Math.max(3, width / 350);
      ctx.setLineDash([Math.max(8, width / 100), Math.max(5, width / 180)]);
      for (const cut of cuts) { ctx.beginPath(); ctx.moveTo(0, cut); ctx.lineTo(width, cut); ctx.stroke(); }
      ctx.restore();
    }).catch((error) => { status.textContent = error.message; });
  }

  let baseReady = false;
  async function loadBase() {
    if (baseReady) return;
    let y = 0;
    for (const item of chosen) {
      const image = new Image();
      image.src = mergeManualImageUrl(selection.provider, selection.manga, selection.chapter, item.file);
      await image.decode();
      baseContext.drawImage(image, 0, item.source_y_start, width, item.pending_height, 0, y, width, item.pending_height);
      y += item.pending_height;
    }
    baseReady = true;
  }

  function renderCuts() {
    page.querySelector("[data-cut-count]").textContent = `${cuts.length} corte(s)`;
    drawCuts();
  }

  function onCanvasClick(event) {
    const bounds = canvas.getBoundingClientRect();
    const y = Math.round((event.clientY - bounds.top) * canvas.height / bounds.height);
    if (y <= 0 || y >= canvas.height || cuts.includes(y)) return;
    cuts.push(y); cuts.sort((a, b) => a - b); renderCuts();
  }
  canvas.addEventListener("click", onCanvasClick);
  page.querySelector("[data-back]").addEventListener("click", () => {
    container.dispatchEvent(new CustomEvent("menu:action", { bubbles: true, detail: { action: "validar-faixa" } }));
  });
  page.querySelector("[data-clear]").addEventListener("click", () => { cuts.length = 0; renderCuts(); });
  page.querySelector("[data-submit]").addEventListener("click", async (event) => {
    event.currentTarget.disabled = true;
    status.textContent = "Gerando proposta e validando as fontes…";
    try {
      const result = await generateMergeManualProposal({
        provider: selection.provider, manga: selection.manga, chapter: selection.chapter,
        block_id: selection.blockId, start: selection.start, end: selection.end,
      }, cuts);
      status.textContent = `Proposta ${result.proposal_id} gerada com ${result.outputs?.length || 0} bloco(s).`;
    } catch (error) {
      status.textContent = error.message;
    } finally { event.currentTarget.disabled = false; }
  });
  loadImages().catch((error) => { status.textContent = `Não foi possível carregar a prévia: ${error.message}`; });
  return () => { canvas.removeEventListener("click", onCanvasClick); };
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
