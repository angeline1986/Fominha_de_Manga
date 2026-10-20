import { fetchComparison, comparisonImageUrl } from "/_app/api/comparison.js";

export function createSolidAreaPreview(getContext) {
  const card = document.createElement("aside");
  card.className = "solid-area-preview";
  card.setAttribute("role", "tooltip");
  card.hidden = true;
  const heading = document.createElement("strong");
  const canvas = document.createElement("canvas");
  canvas.width = 240; canvas.height = 155;
  const note = document.createElement("small");
  card.append(heading, canvas, note);
  document.body.append(card);
  const comparisons = new Map();
  let current = null;

  function hide() { current = null; card.hidden = true; }
  function position(button) {
    const rect = button.getBoundingClientRect();
    const width = card.offsetWidth || 268, height = card.offsetHeight || 220;
    const left = rect.right + width + 12 < innerWidth ? rect.right + 12 : rect.left - width - 12;
    card.style.left = `${Math.max(8, Math.min(left, innerWidth - width - 8))}px`;
    card.style.top = `${Math.max(8, Math.min(rect.top - 30, innerHeight - height - 8))}px`;
  }
  function comparison(context) {
    const key = `${context.provider}\u0000${context.manga}\u0000${context.chapter}`;
    if (!comparisons.has(key)) comparisons.set(key, fetchComparison({
      provider: context.provider, manga: context.manga, chapter: context.chapter,
      step: "1", comparisonMode: "check", scope: "check",
    }).catch((error) => { comparisons.delete(key); throw error; }));
    return comparisons.get(key);
  }
  async function show(button, area) {
    const ticket = { button, area }; current = ticket;
    const number = Number.isInteger(area.number) && area.number > 0 ? area.number : area.ordinal;
    heading.textContent = `Balão ${String(number).padStart(2, "0")} · Cap. ${area.chapter}`;
    note.textContent = area.page;
    const context = getContext();
    card.hidden = false; position(button);
    try {
      const result = await comparison({ ...context, chapter: area.chapter });
      if (current !== ticket) return;
      const page = result.pages?.find((item) => item.name === area.page);
      if (!page || !area.box_pixels) { note.textContent = "Prévia indisponível para esta área."; return; }
      const image = new Image();
      image.onload = () => {
        if (current !== ticket) return;
        drawCrop(canvas, image, area.box_pixels);
        note.textContent = `${area.page} · Área ${number}`;
        position(button);
      };
      image.onerror = () => { if (current === ticket) note.textContent = "Prévia indisponível."; };
      image.src = comparisonImageUrl({ ...context, chapter: area.chapter,
        step: "1", comparisonMode: "check", scope: "check" }, page, "after");
    } catch {
      if (current === ticket) note.textContent = "Prévia indisponível para esta página.";
    }
  }
  function drawCrop(target, image, box) {
    const x = Math.max(0, Math.min(image.naturalWidth, box.x));
    const y = Math.max(0, Math.min(image.naturalHeight, box.y));
    const width = Math.min(image.naturalWidth - x, box.width);
    const height = Math.min(image.naturalHeight - y, box.height);
    if (width <= 0 || height <= 0) return;
    const margin = Math.max(12, Math.round(Math.max(width, height) * 0.12));
    const left = Math.max(0, x - margin), top = Math.max(0, y - margin);
    const cropWidth = Math.min(image.naturalWidth - left, width + margin * 2);
    const cropHeight = Math.min(image.naturalHeight - top, height + margin * 2);
    const scale = Math.min(target.width / cropWidth, target.height / cropHeight);
    const outWidth = cropWidth * scale, outHeight = cropHeight * scale;
    const context = target.getContext("2d");
    context.clearRect(0, 0, target.width, target.height);
    context.drawImage(image, left, top, cropWidth, cropHeight,
      (target.width - outWidth) / 2, (target.height - outHeight) / 2, outWidth, outHeight);
  }
  const onScroll = () => hide();
  window.addEventListener("scroll", onScroll, true);
  return { show, hide, dispose() {
    window.removeEventListener("scroll", onScroll, true);
    comparisons.clear(); card.remove();
  } };
}
