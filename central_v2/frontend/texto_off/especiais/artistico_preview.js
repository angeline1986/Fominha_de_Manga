import { getContext } from "/_app/state/context.js";
import { styledPreviewImageUrl } from "/_app/api/textoff.js";

export function createArtisticPreview() {
  const card = document.createElement("aside");
  card.className = "artistico-preview";
  card.setAttribute("role", "tooltip");
  card.hidden = true;
  const heading = document.createElement("strong");
  const canvas = document.createElement("canvas");
  canvas.width = 240; canvas.height = 155;
  const note = document.createElement("small");
  card.append(heading, canvas, note);
  document.body.append(card);
  let current = null;

  function hide() { current = null; card.hidden = true; }
  function position(button) {
    const rect = button.getBoundingClientRect();
    const width = card.offsetWidth || 268, height = card.offsetHeight || 220;
    const left = rect.right + width + 12 < innerWidth ? rect.right + 12 : rect.left - width - 12;
    card.style.left = `${Math.max(8, Math.min(left, innerWidth - width - 8))}px`;
    card.style.top = `${Math.max(8, Math.min(rect.top - 30, innerHeight - height - 8))}px`;
  }
  function show(button, chapter, occurrence, ordinal) {
    const identity = { button, occurrence };
    current = identity;
    heading.textContent = `Balão ${String(ordinal).padStart(2, "0")} · ${chapter}`;
    note.textContent = `${occurrence.page} · ${occurrence.id}`;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    card.hidden = false; position(button);
    const box = occurrence.roi, source = occurrence.preview;
    if (!box || !source || !source.width || !source.height) {
      note.textContent = "Prévia indisponível para esta página.";
      return;
    }
    const image = new Image();
    image.onload = () => {
      if (current !== identity) return;
      if (image.naturalWidth !== source.width || image.naturalHeight !== source.height) {
        note.textContent = "Dimensões da página mudaram. Atualize a lista.";
        return;
      }
      const margin = Math.max(12, Math.round(Math.max(box.width, box.height) * 0.12));
      const x = Math.max(0, box.x - margin), y = Math.max(0, box.y - margin);
      const width = Math.min(source.width - x, box.width + margin * 2);
      const height = Math.min(source.height - y, box.height + margin * 2);
      if (width <= 0 || height <= 0) {
        note.textContent = "ROI fora das dimensões da página.";
        return;
      }
      const scale = Math.min(canvas.width / width, canvas.height / height);
      const outWidth = width * scale, outHeight = height * scale;
      context.drawImage(image, x, y, width, height,
        (canvas.width - outWidth) / 2, (canvas.height - outHeight) / 2, outWidth, outHeight);
      note.textContent = `${occurrence.id} · ROI ${box.x},${box.y} · ${box.width}×${box.height}`;
      position(button);
    };
    image.onerror = () => { if (current === identity) note.textContent = "Prévia indisponível."; };
    const { provider, manga } = getContext();
    image.src = styledPreviewImageUrl(provider, manga, chapter, occurrence.page,
      occurrence.id, source.sha256);
  }
  const onScroll = () => hide();
  window.addEventListener("scroll", onScroll, true);
  return { show, hide, dispose() { window.removeEventListener("scroll", onScroll, true); card.remove(); } };
}
