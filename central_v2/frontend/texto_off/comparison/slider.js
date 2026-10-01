export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
export function splitAt(clientX, left, width) {
  return width > 0 ? clamp((clientX - left) / width * 100, 0, 100) : 50;
}

export function createSlider(viewport, onState) {
  const frame = document.createElement("div");
  frame.className = "comparison-frame";
  frame.innerHTML = `<span class="comparison-label is-before">ORIGINAL</span><span class="comparison-label is-after">TEXTO OFF</span><div class="comparison-after"></div><div class="comparison-before"></div>
    <div class="comparison-divider" role="slider" tabindex="0" aria-label="Divisor Antes e Depois"
      aria-valuemin="0" aria-valuemax="100" aria-valuenow="50"><span></span></div>`;
  viewport.append(frame);
  const handle = frame.querySelector(".comparison-divider");
  let split = 50, zoom = 1, x = 0, y = 0, width = 0, height = 0;
  let ready = false, revision = 0, disposed = false, raf = 0, drag = null, space = false;
  let images = [];
  function paint() {
    raf = 0;
    frame.style.setProperty("--split-position", `${split}%`);
    frame.style.setProperty("--pan-x", `${x}px`);
    frame.style.setProperty("--pan-y", `${y}px`);
    handle.setAttribute("aria-valuenow", String(Math.round(split)));
    handle.setAttribute("aria-valuetext", `${Math.round(split)}% da entrada visível`);
  }
  function schedule() { if (!raf) raf = requestAnimationFrame(paint); }
  function layout() {
    if (!ready) return;
    const sideBySide = frame.classList.contains("is-side-by-side");
    const scale = Math.min((viewport.clientWidth - 32) / (width * (sideBySide ? 2 : 1)),
      (viewport.clientHeight - 32) / height);
    frame.style.width = `${Math.max(1, width * scale * zoom * (frame.classList.contains("is-side-by-side") ? 2 : 1))}px`;
    frame.style.height = `${Math.max(1, height * scale * zoom)}px`;
    schedule();
  }
  const observer = new ResizeObserver(layout);
  observer.observe(viewport);
  function down(event) {
    if (!ready || drag || ![0, 1].includes(event.button)) return;
    event.preventDefault();
    const wantsPan = space || event.button === 1;
    const pan = wantsPan && zoom > 1;
    if (!pan && frame.classList.contains("is-side-by-side")) return;
    drag = { id: event.pointerId, pan, startX: event.clientX, startY: event.clientY, x, y,
      rect: frame.getBoundingClientRect() };
    viewport.setPointerCapture(event.pointerId);
    handle.focus({ preventScroll: true });
    if (!pan) { split = splitAt(event.clientX, drag.rect.left, drag.rect.width); schedule(); }
  }
  function move(event) {
    if (!drag || event.pointerId !== drag.id) return;
    if (drag.pan) {
      x = drag.x + event.clientX - drag.startX;
      y = drag.y + event.clientY - drag.startY;
    } else split = splitAt(event.clientX, drag.rect.left, drag.rect.width);
    schedule();
  }
  function end(event) {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null;
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
  }
  function keydown(event) {
    if (event.code === "Space") { event.preventDefault(); space = true; return; }
    if (!ready) return;
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
  viewport.addEventListener("pointerdown", down);
  viewport.addEventListener("pointermove", move);
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) viewport.addEventListener(type, end);
  handle.addEventListener("keydown", keydown);
  handle.addEventListener("keyup", keyup);
  handle.addEventListener("blur", blur);
  return {
    async load(beforeUrl, afterUrl) {
      const id = ++revision;
      ready = false; frame.hidden = true; drag = null; onState("loading");
      images.forEach((img) => img.removeAttribute("src"));
      images = [new Image(), new Image()];
      const pair = images;
      pair[0].alt = "Entrada do processamento"; pair[1].alt = "Resultado do processamento";
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
        frame.querySelector(".comparison-before").replaceChildren(pair[0]);
        frame.querySelector(".comparison-after").replaceChildren(pair[1]);
        split = 50; zoom = 1; x = 0; y = 0;
        ready = true; frame.hidden = false; layout(); onState("ready");
      } catch (error) {
        if (!disposed && revision === id) onState("error", error.message.includes("dimensões")
          ? error.message : "Não foi possível carregar as duas imagens. Tente novamente.");
      }
    },
    zoom(value) { zoom = clamp(value, 1, 8); layout(); return zoom; },
    getZoom() { return zoom; },
    setMode(mode) { frame.classList.toggle("is-side-by-side", mode === "side"); layout(); },
    fit() { zoom = 1; x = 0; y = 0; layout(); },
    pan(dx, dy) { x += dx; y += dy; schedule(); },
    dispose() {
      disposed = true; revision++; observer.disconnect(); cancelAnimationFrame(raf);
      images.forEach((img) => img.removeAttribute("src"));
      viewport.removeEventListener("pointerdown", down); viewport.removeEventListener("pointermove", move);
      for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) viewport.removeEventListener(type, end);
      handle.removeEventListener("keydown", keydown); handle.removeEventListener("keyup", keyup);
      handle.removeEventListener("blur", blur); frame.remove();
    },
  };
}
