import { comparisonModeConfig, TRIPTYCH_PANEL_GAP } from "/texto_off/comparison/model.js";

export function createSlider(viewport, onState, comparisonMode) {
  const mode = comparisonModeConfig(comparisonMode);
  const panelsConfig = mode.panels;
  const stage = document.createElement("div");
  stage.className = "comparison-stage";
  const frame = document.createElement("div");
  frame.className = `comparison-frame comparison-${mode.layout}`;
  frame.innerHTML = panelsConfig.map(([key, label]) => `<figure class="comparison-image-panel" data-stage="${key}">
    <figcaption><strong>${label}</strong><small data-stage-status></small></figcaption>
    <div class="comparison-image-holder"></div></figure>`).join("");
  stage.append(frame); viewport.append(stage);
  const panels = [...frame.querySelectorAll(".comparison-image-panel")];
  const holders = panels.map((panel) => panel.querySelector(".comparison-image-holder"));
  let images = [], zoom = 0.4, width = 0, height = 0, ready = false, revision = 0, disposed = false;
  let overlay = null, interactionMode = "normal";
  let view = "dual", rulers = false;

  function layout() {
    if (!ready) return;
    const imageWidth = width * zoom, imageHeight = height * zoom;
    frame.style.setProperty("--comparison-image-width", `${imageWidth}px`);
    frame.style.setProperty("--comparison-panel-gap", `${TRIPTYCH_PANEL_GAP}px`);
    const count = view === "dual" ? panels.length : 1;
    frame.style.width = `${imageWidth * count + TRIPTYCH_PANEL_GAP * (count - 1)}px`;
    frame.style.height = `${imageHeight + 44}px`;
    frame.style.gridTemplateColumns = `repeat(${count}, var(--comparison-image-width))`;
    frame.style.setProperty("--comparison-ruler-step", `${100 * zoom}px`);
    panels.forEach((panel, index) => {
      panel.hidden = view !== "dual" && index !== (view === "before" ? 0 : 1);
      panel.style.width = `${imageWidth}px`; panel.style.height = `${imageHeight + 44}px`;
    });
    frame.classList.toggle("has-rulers", rulers);
  }
  function clearImages() {
    images.forEach((image) => { image.removeAttribute("src"); image.remove(); });
    images = [];
  }
  function mountOverlay() {
    if (!overlay || !ready) return;
    holders[mode.catalogPanelIndex].append(overlay);
  }
  return {
    async load(urls, status = "") {
      const id = ++revision;
      const canvas = viewport.closest?.(".comparison-canvas-viewport");
      ready = false; frame.hidden = true; onState("loading"); clearImages();
      images = urls.map(() => new Image());
      const batch = images;
      batch.forEach((image, index) => { image.alt = `Imagem ${panelsConfig[index][1]}`; image.draggable = false; image.src = urls[index]; });
      try {
      if (batch.length !== panels.length) throw new Error(`A comparação exige ${panels.length} imagens.`);
        await Promise.all(batch.map((image) => image.decode()));
        if (disposed || revision !== id) return;
        if (!batch[0].naturalWidth || batch.some((image) => image.naturalWidth !== batch[0].naturalWidth
            || image.naturalHeight !== batch[0].naturalHeight)) {
          throw new Error("As imagens têm dimensões diferentes. A comparação foi bloqueada para evitar desalinhamento.");
        }
        width = batch[0].naturalWidth; height = batch[0].naturalHeight;
        batch.forEach((image, index) => { image.className = "comparison-image"; holders[index].replaceChildren(image); });
        panels.at(-1).querySelector("[data-stage-status]").textContent = status;
        ready = true; layout(); mountOverlay(); frame.hidden = false;
        if (canvas) { canvas.scrollTop = 0; canvas.scrollLeft = 0; }
        onState("ready");
      } catch (error) {
        if (!disposed && revision === id) onState("error", error.message.includes("dimensões")
          ? error.message : `Não foi possível carregar as ${panels.length} imagens. Tente novamente.`);
      }
    },
    zoom(value) { zoom = Math.max(0.2, Math.min(2, value)); layout(); return zoom; },
    setView(value) {
      if (!["dual", "before", "after"].includes(value) || panels.length !== 2) return;
      view = value; layout();
    },
    setRulers(value) { rulers = Boolean(value); layout(); },
    getZoom() { return zoom; },
    getImageMetrics() { return { naturalWidth: width, naturalHeight: height, zoom, mode: comparisonMode }; },
    mountAfterOverlay(element) { overlay?.remove(); overlay = element; element.classList.add("comparison-after-overlay"); mountOverlay(); },
    setInteractionMode(nextMode) {
      if (!["normal", "residue-selection"].includes(nextMode)) throw new TypeError("Modo de interação inválido.");
      interactionMode = nextMode;
      frame.classList.toggle("is-residue-selection", interactionMode === "residue-selection");
    },
    dispose() { disposed = true; revision++; clearImages(); stage.remove(); overlay = null; },
  };
}
