import { mergeManualImageUrl } from "/_app/api/merge_manual.js";
import { showMessage } from "/_shared/messages/messages.js";
import { drawPageList, drawPageTags } from "/processamento/merge_manual/novos_merges_view.js";

export function createManualCutPreview({ page, canvas, selection, chosen, width, totalHeight, getState, onSelectPage }) {
  const ctx = canvas.getContext("2d");
  const baseCanvas = document.createElement("canvas");
  const baseContext = baseCanvas.getContext("2d");
  let basePromise;
  let baseReady = false;
  let imageErrorShown = false;
  canvas.width = baseCanvas.width = width;
  canvas.height = baseCanvas.height = totalHeight;
  drawPageList(page, chosen, selection, getState().cuts, getState().rulerColors, (selectedPage) => {
    onSelectPage(selectedPage);
    const offset = chosen.slice(0, chosen.indexOf(selectedPage)).reduce((sum, item) => sum + item.pending_height, 0);
    page.querySelector(".manual-cut-canvas-wrap").scrollTo({ top: offset * getState().zoom / 100, behavior: "smooth" });
    draw();
  });

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
    const { zoom, cuts, highlightOdd, rulerColors, focusedPageFile } = getState();
    canvas.style.width = `${width * zoom / 100}px`;
    page.querySelector("[data-zoom-value]").textContent = `${zoom}%`;
    page.querySelector("[data-focus-zoom]").textContent = `${zoom}%`;
    drawPageTags(page, chosen, width, totalHeight, zoom, cuts, highlightOdd, rulerColors, focusedPageFile);
    loadBase().then(() => {
      ctx.clearRect(0, 0, width, totalHeight);
      ctx.drawImage(baseCanvas, 0, 0);
    }).catch((error) => {
      if (imageErrorShown) return;
      imageErrorShown = true;
      showMessage({ title: "Falha ao carregar prévia", message: error.message });
    });
  }
  return { draw };
}
