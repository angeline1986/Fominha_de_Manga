export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
export function splitAt(clientX, left, width) {
  return width > 0 ? clamp((clientX - left) / width * 100, 0, 100) : 50;
}

import { SIDE_BY_SIDE_GAP } from "/texto_off/comparison/model.js";

export function createSlider(viewport, onState) {
  const stage = document.createElement("div");
  stage.className = "comparison-stage";
  const frame = document.createElement("div");
  frame.className = "comparison-frame";
  frame.innerHTML = `<div class="comparison-after"><span class="comparison-image-label">AUTO CLEANER</span></div><div class="comparison-before"><span class="comparison-image-label">ORIGINAL</span></div>
    <div class="comparison-divider" role="slider" tabindex="0" aria-label="Divisor Antes e Depois"
      aria-valuemin="0" aria-valuemax="100" aria-valuenow="50"><span aria-hidden="true">↔</span></div>`;
  stage.append(frame); viewport.append(stage);
  const handle = frame.querySelector(".comparison-divider");
  let split = 50, zoom = 0.4, x = 0, y = 0, width = 0, height = 0;
  let ready = false, revision = 0, disposed = false, raf = 0, drag = null, space = false;
  let interactionMode = "normal", mode = "split", afterOverlay = null;
  let images = [];
  function paint() {
    raf = 0;
    frame.style.setProperty("--split-position", `${split}%`);
    frame.style.setProperty("--pan-x", `${x}px`); frame.style.setProperty("--pan-y", `${y}px`);
    handle.setAttribute("aria-valuenow", String(Math.round(split)));
    handle.setAttribute("aria-valuetext", `${Math.round(split)}% da imagem original visível`);
  }
  function schedule() { if (!raf) raf = requestAnimationFrame(paint); }
  function layout() {
    if (!ready) return;
    const side = frame.classList.contains("is-side-by-side");
    const imageWidth = width * zoom;
    const frameWidth = imageWidth * (side ? 2 : 1) + (side ? SIDE_BY_SIDE_GAP : 0);
    const frameHeight = height * zoom;
    frame.style.width = `${frameWidth}px`; frame.style.height = `${frameHeight}px`;
    schedule();
  }
  function down(event) {
    if (!ready || drag || ![0, 1].includes(event.button)) return;
    if (event.target?.closest?.(".comparison-after-overlay")) return;
    if (interactionMode === "residue-selection" && event.button === 0) return;
    const wantsPan = space || event.button === 1;
    const pan = wantsPan && zoom > 1;
    if (!pan && frame.classList.contains("is-side-by-side")) return;
    event.preventDefault();
    drag = { id: event.pointerId, pan, startX: event.clientX, startY: event.clientY, x, y,
      rect: frame.getBoundingClientRect() };
    viewport.setPointerCapture(event.pointerId); handle.focus({ preventScroll: true });
    if (!pan) { split = splitAt(event.clientX, drag.rect.left, drag.rect.width); schedule(); }
  }
  function move(event) {
    if (!drag || event.pointerId !== drag.id) return;
    if (drag.pan) { x = drag.x + event.clientX - drag.startX; y = drag.y + event.clientY - drag.startY; }
    else split = splitAt(event.clientX, drag.rect.left, drag.rect.width);
    schedule();
  }
  function end(event) {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null;
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
  }
  function keydown(event) {
    if (event.code === "Space") { event.preventDefault(); space = true; return; }
    if (!ready || interactionMode !== "normal") return;
    const delta = event.shiftKey ? 10 : 1;
    if (event.key === "ArrowLeft") split = clamp(split - delta, 0, 100);
    else if (event.key === "ArrowRight") split = clamp(split + delta, 0, 100);
    else if (event.key === "Home") split = 0;
    else if (event.key === "End") split = 100;
    else return;
    event.preventDefault(); schedule();
  }
  function keyup(event) { if (event.code === "Space") space = false; }
  function blur() { space = false; }
  viewport.addEventListener("pointerdown", down); viewport.addEventListener("pointermove", move);
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) viewport.addEventListener(type, end);
  handle.addEventListener("keydown", keydown); handle.addEventListener("keyup", keyup); handle.addEventListener("blur", blur);
  return {
    async load(beforeUrl, afterUrl) {
      const id = ++revision;
      const canvas = viewport.closest?.(".comparison-canvas-viewport");
      ready = false; frame.hidden = true; drag = null; onState("loading");
      images.forEach((img) => { img.removeAttribute("src"); img.remove(); }); images = [new Image(), new Image()];
      const pair = images;
      pair[0].alt = "Imagem original"; pair[1].alt = "Imagem Auto Cleaner";
      pair.forEach((img) => { img.draggable = false; });
      pair[0].src = beforeUrl; pair[1].src = afterUrl;
      try {
        await Promise.all(pair.map((img) => img.decode()));
        if (disposed || revision !== id) return;
        if (!pair[0].naturalWidth || pair[0].naturalWidth !== pair[1].naturalWidth
            || pair[0].naturalHeight !== pair[1].naturalHeight) {
          throw new Error("As imagens têm dimensões diferentes. A comparação foi bloqueada para evitar desalinhamento.");
        }
        width = pair[0].naturalWidth; height = pair[0].naturalHeight;
        pair[0].className = "comparison-image"; pair[1].className = "comparison-image";
        frame.querySelector(".comparison-before").prepend(pair[0]);
        frame.querySelector(".comparison-after").prepend(pair[1]);
        split = 50; x = 0; y = 0; ready = true; frame.hidden = false; layout();
        if (canvas) { canvas.scrollTop = 0; canvas.scrollLeft = 0; }
        onState("ready");
      } catch (error) {
        if (!disposed && revision === id) onState("error", error.message.includes("dimensões")
          ? error.message : "Não foi possível carregar as duas imagens. Tente novamente.");
      }
    },
    zoom(value) { zoom = clamp(value, 0.2, 2); layout(); return zoom; },
    getZoom() { return zoom; },
    setMode(nextMode) {
      mode = nextMode;
      frame.classList.toggle("is-side-by-side", mode === "side"); layout();
    },
    getImageMetrics() { return { naturalWidth: width, naturalHeight: height, zoom, mode }; },
    mountAfterOverlay(element) {
      if (afterOverlay && afterOverlay !== element) afterOverlay.remove();
      afterOverlay = element;
      element.classList.add("comparison-after-overlay");
      frame.append(element);
    },
    setInteractionMode(nextMode) {
      if (!["normal", "residue-selection"].includes(nextMode)) throw new TypeError("Modo de interação inválido.");
      interactionMode = nextMode;
      frame.classList.toggle("is-residue-selection", nextMode === "residue-selection");
      if (nextMode !== "normal" && drag) {
        const pointerId = drag.id; drag = null;
        if (viewport.hasPointerCapture(pointerId)) viewport.releasePointerCapture(pointerId);
      }
    },
    dispose() {
      disposed = true; revision++; cancelAnimationFrame(raf);
      images.forEach((img) => { img.removeAttribute("src"); img.remove(); });
      viewport.removeEventListener("pointerdown", down); viewport.removeEventListener("pointermove", move);
      for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) viewport.removeEventListener(type, end);
      handle.removeEventListener("keydown", keydown); handle.removeEventListener("keyup", keyup);
      handle.removeEventListener("blur", blur); stage.remove();
      afterOverlay = null;
    },
  };
}
