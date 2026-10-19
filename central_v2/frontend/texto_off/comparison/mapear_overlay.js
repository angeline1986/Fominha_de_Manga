const LABELS = {
  soft_gradient: "Gradiente",
  saturated_styled: "Cor decorativa",
  irregular_outline: "Contorno irregular",
  transparent_balloon: "Balão transparente",
};

export function createMapearOverlay(layer, list) {
  let candidates = [];
  function highlight(id) {
    layer.querySelectorAll("[data-candidate-id]").forEach((item) => {
      item.classList.toggle("is-highlighted", item.dataset.candidateId === id);
    });
    list.querySelectorAll("[data-candidate-id]").forEach((item) => {
      item.classList.toggle("is-highlighted", item.dataset.candidateId === id);
    });
  }
  function render(next, width, height) {
    candidates = Array.isArray(next) ? next : [];
    layer.replaceChildren();
    list.replaceChildren();
    candidates.forEach((candidate, index) => {
      const id = String(index);
      const type = Object.hasOwn(LABELS, candidate.candidate_type)
        ? candidate.candidate_type : "irregular_outline";
      const boxData = candidate.box || {
        left: candidate.bbox[0] / width, top: candidate.bbox[1] / height,
        width: candidate.bbox[2] / width, height: candidate.bbox[3] / height,
      };
      const box = document.createElement("span");
      box.className = `mapear-candidate-box is-${type}`;
      box.dataset.candidateId = id;
      box.style.left = `${boxData.left * 100}%`;
      box.style.top = `${boxData.top * 100}%`;
      box.style.width = `${boxData.width * 100}%`;
      box.style.height = `${boxData.height * 100}%`;
      box.title = `${LABELS[type]} ${index + 1}`;
      const number = document.createElement("span");
      number.className = "mapear-candidate-number";
      number.textContent = String(index + 1);
      box.append(number);
      layer.append(box);

      const item = document.createElement("button");
      item.type = "button";
      item.className = `mapear-candidate-item is-${type}`;
      item.dataset.candidateId = id;
      item.append(number.cloneNode(true));
      const detail = document.createElement("span");
      detail.className = "mapear-candidate-detail";
      const name = document.createElement("strong");
      name.textContent = LABELS[type];
      const score = document.createElement("small");
      score.textContent = type === "transparent_balloon"
        ? `Balão ${candidate.balloon} · reconhecimento Nível I`
        : `Confiança ${Math.round(Number(candidate.segmenter_confidence || 0) * 100)}%`;
      detail.append(name, score);
      item.append(detail);
      list.append(item);
    });
    highlight(null);
  }
  function syncHighlight(event) {
    const target = event.target.closest("[data-candidate-id]");
    if (target) highlight(target.dataset.candidateId);
  }
  function clearHighlight(event) {
    const from = event.target.closest("[data-candidate-id]");
    const to = event.relatedTarget?.closest?.("[data-candidate-id]");
    if (from && !to) highlight(null);
  }
  list.addEventListener("pointerover", syncHighlight);
  list.addEventListener("pointerout", clearHighlight);
  list.addEventListener("focusin", syncHighlight);
  list.addEventListener("focusout", clearHighlight);
  return {
    render,
    clear() { layer.replaceChildren(); list.replaceChildren(); candidates = []; },
    dispose() {
      list.removeEventListener("pointerover", syncHighlight);
      list.removeEventListener("pointerout", clearHighlight);
      list.removeEventListener("focusin", syncHighlight);
      list.removeEventListener("focusout", clearHighlight);
    },
  };
}
