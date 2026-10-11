/** Seleção experimental de ROI; coordenadas normalizadas e pixels naturais. */
export function normalizedPoint(clientX, clientY, rect) {
  const clamp = (value) => Math.max(0, Math.min(1, value));
  return {
    x: clamp((clientX - rect.left) / rect.width),
    y: clamp((clientY - rect.top) / rect.height),
  };
}

export function boxesToNaturalPixels(boxes, naturalWidth, naturalHeight) {
  const edge = (value, size) => Math.max(0, Math.min(size, Math.round(value * size)));
  return boxes.map((box) => {
    const x = edge(box.x, naturalWidth), y = edge(box.y, naturalHeight);
    const right = edge(box.x + box.w, naturalWidth);
    const bottom = edge(box.y + box.h, naturalHeight);
    return { x, y, width: right - x, height: bottom - y };
  }).filter((box) => box.width > 0 && box.height > 0);
}

export function connectRoiSelection({ image, button, panel }) {
  const frame = document.createElement("div");
  frame.className = "lab-roi-frame";
  image.parentNode.insertBefore(frame, image);
  frame.append(image);
  const overlay = document.createElement("div");
  overlay.className = "lab-roi-overlay";
  frame.append(overlay);
  const status = panel.querySelector(".lab-muted");
  const list = document.createElement("div");
  list.className = "lab-roi-list";
  status.after(list);
  let source = "", enabled = false, boxes = [], active = null;
  const point = (event) => {
    const r = image.getBoundingClientRect();
    return normalizedPoint(event.clientX, event.clientY, r);
  };
  const normalized = (a, b) => ({
    x: Math.min(a.x,b.x), y: Math.min(a.y,b.y),
    w: Math.abs(a.x-b.x), h: Math.abs(a.y-b.y),
  });
  const valid = (box) => box.w >= .004 && box.h >= .004;
  function paint() {
    overlay.replaceChildren();
    list.replaceChildren();
    for (const [i, box] of boxes.entries()) {
      const el = document.createElement("div");
      el.className = "lab-roi-box";
      el.style.left = `${box.x*100}%`;
      el.style.top = `${box.y*100}%`;
      el.style.width = `${box.w*100}%`;
      el.style.height = `${box.h*100}%`;
      const close = document.createElement("button");
      close.type = "button";
      close.className = "lab-roi-close";
      close.textContent = "×";
      close.title = `Excluir área ${i+1}`;
      close.setAttribute("aria-label", `Excluir área ${i+1}`);
      close.addEventListener("pointerdown", (event) => event.stopPropagation());
      close.addEventListener("click", (event) => {
        event.stopPropagation();
        boxes.splice(i, 1);
        paint();
      });
      el.append(close);
      overlay.append(el);
      const item = document.createElement("div");
      item.className = "lab-roi-item";
      const caption = document.createElement("span");
      caption.textContent = `Área ${i+1}: ${Math.round(box.w*image.naturalWidth)} × ${Math.round(box.h*image.naturalHeight)} px`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Excluir";
      remove.setAttribute("aria-label", `Excluir área ${i+1}`);
      remove.addEventListener("click", () => { boxes.splice(i,1); paint(); });
      item.append(caption, remove);
      list.append(item);
    }
    if (active) {
      const box = normalized(active.start,active.end);
      const el = document.createElement("div");
      el.className = "lab-roi-box is-drawing";
      el.style.left = `${box.x*100}%`;
      el.style.top = `${box.y*100}%`;
      el.style.width = `${box.w*100}%`;
      el.style.height = `${box.h*100}%`;
      overlay.append(el);
    }
    status.textContent = boxes.length ? `${boxes.length} área(s) selecionada(s).` : "Nenhuma área selecionada.";
    button.textContent = enabled ? "Encerrar seleção" : "Selecionar área";
    button.setAttribute("aria-pressed", String(enabled));
    frame.classList.toggle("is-selecting", enabled);
  }
  function pointerDown(event) {
    if (!enabled || event.button !== 0 || !image.naturalWidth) return;
    event.preventDefault();
    active = { id: event.pointerId, start: point(event), end: point(event) };
    overlay.setPointerCapture(event.pointerId);
    paint();
  }
  function pointerMove(event) {
    if (!active || event.pointerId !== active.id) return;
    active.end = point(event); paint();
  }
  function pointerEnd(event) {
    if (!active || event.pointerId !== active.id) return;
    const box = normalized(active.start,point(event));
    active = null;
    if (valid(box)) boxes.push(box);
    paint();
  }
  overlay.addEventListener("pointerdown",pointerDown);
  overlay.addEventListener("pointermove",pointerMove);
  overlay.addEventListener("pointerup",pointerEnd);
  overlay.addEventListener("pointercancel", () => { active=null; paint(); });
  button.disabled = true;
  const toggle = () => { if (button.disabled) return; enabled=!enabled; active=null; paint(); };
  button.addEventListener("click",toggle);
  function setSource(identity, available) {
    if (source !== identity) { source=identity; boxes=[]; active=null; enabled=false; }
    button.disabled = !available;
    if (!available) enabled=false;
    paint();
  }
  function getBoxesPixels() {
    return boxesToNaturalPixels(boxes, image.naturalWidth, image.naturalHeight);
  }
  paint();
  return { setSource, getBoxesPixels, dispose() {
    button.removeEventListener("click",toggle);
    overlay.remove(); list.remove(); frame.replaceWith(image);
  } };
}
