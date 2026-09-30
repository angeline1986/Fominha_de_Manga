import { mergedLevel3ImageUrl } from "/_app/api/textoff.js";

const LABELS = {
  soft_gradient: "Gradiente",
  saturated_styled: "Cor decorativa",
  irregular_outline: "Contorno irregular",
};

export function openCandidateReview({ provider, manga, chapter, pages }) {
  const previousFocus = document.activeElement;
  const dialog = document.createElement("dialog");
  dialog.className = "textoff-candidate-dialog";
  dialog.setAttribute("aria-labelledby", "textoff-candidate-title");
  const heading = document.createElement("header");
  const title = document.createElement("h2");
  title.id = "textoff-candidate-title";
  title.textContent = `Candidatos Nível III — Cap. ${chapter}`;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn";
  close.textContent = "Fechar";
  close.addEventListener("click", () => dialog.close());
  heading.append(title, close);

  const controls = document.createElement("div");
  controls.className = "textoff-candidate-controls";
  const label = document.createElement("label");
  label.textContent = "Página MERGE";
  const select = document.createElement("select");
  const imageFrame = document.createElement("figure");
  imageFrame.className = "textoff-candidate-image-frame";
  const image = document.createElement("img");
  image.alt = "Página MERGE original com regiões candidatas destacadas";
  const overlay = document.createElement("div");
  overlay.className = "textoff-candidate-overlay";
  const list = document.createElement("ol");
  list.className = "textoff-candidate-list";
  imageFrame.append(image, overlay);
  label.append(select);
  controls.append(label);
  dialog.append(heading, controls, imageFrame, list);

  pages.forEach((page, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${page.source} (${page.candidates.length})`;
    select.append(option);
  });
  function drawCandidates(page) {
    if (!image.naturalWidth || !image.naturalHeight) return;
    overlay.replaceChildren();
    list.replaceChildren();
    page.candidates.forEach((candidate, index) => {
      const [x, y, width, height] = candidate.bbox;
      const box = document.createElement("span");
      box.className = `textoff-candidate-box is-${candidate.candidate_type}`;
      box.textContent = String(index + 1);
      box.style.left = `${x / image.naturalWidth * 100}%`;
      box.style.top = `${y / image.naturalHeight * 100}%`;
      box.style.width = `${width / image.naturalWidth * 100}%`;
      box.style.height = `${height / image.naturalHeight * 100}%`;
      box.title = `${LABELS[candidate.candidate_type] || candidate.candidate_type} ${index + 1}`;
      overlay.append(box);
      const item = document.createElement("li");
      const confidence = Number(candidate.segmenter_confidence || 0);
      item.textContent = `${LABELS[candidate.candidate_type] || candidate.candidate_type} · região ${index + 1} · confiança ${Math.round(confidence * 100)}%`;
      list.append(item);
    });
  }
  function showPage() {
    const page = pages[Number(select.value)];
    if (!page) return;
    image.alt = `MERGE ${page.source}; ${page.candidates.length} regiões candidatas destacadas`;
    if (image.dataset.source === page.source) {
      drawCandidates(page);
      return;
    }
    image.dataset.source = page.source;
    image.onload = () => drawCandidates(pages[Number(select.value)]);
    image.src = mergedLevel3ImageUrl(provider, manga, chapter, page.source);
    list.replaceChildren();
    overlay.replaceChildren();
  }
  select.addEventListener("change", showPage);
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (previousFocus?.isConnected) previousFocus.focus();
  }, { once: true });
  document.body.append(dialog);
  dialog.showModal();
  showPage();
  close.focus();
  return dialog;
}
