import { validationImageUrl } from "/_app/api/image_validation.js";

export function createValidationViewer({ onBack, onApply }) {
  const element = document.createElement("section");
  element.className = "image-validation image-validation-viewer";
  let zoom = 100;

  function update(row, context) {
    element.replaceChildren();
    const heading = document.createElement("header");
    heading.className = "image-validation-viewer-heading";
    const back = document.createElement("button");
    back.className = "btn";
    back.type = "button";
    back.textContent = "Voltar à tabela";
    back.addEventListener("click", onBack);
    const title = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = "VALIDAR IMAGENS";
    const h1 = document.createElement("h1");
    h1.textContent = `Capítulo ${row.chapter} · ${row.images.length} divergência(s)`;
    title.append(label, h1);
    const controls = document.createElement("div");
    controls.className = "image-validation-zoom";
    const zoomText = document.createElement("span");
    zoomText.textContent = `${zoom}%`;
    for (const [symbol, change, name] of [["−", -10, "Diminuir zoom"], ["+", 10, "Aumentar zoom"]]) {
      const button = document.createElement("button");
      button.className = "btn";
      button.type = "button";
      button.textContent = symbol;
      button.setAttribute("aria-label", name);
      button.addEventListener("click", () => {
        zoom = Math.min(150, Math.max(50, zoom + change));
        zoomText.textContent = `${zoom}%`;
        element.querySelectorAll(".image-validation-stage img").forEach((img) => {
          img.style.width = `${zoom}%`;
        });
      });
      if (change < 0) controls.append(button, zoomText);
      else controls.append(button);
    }
    heading.append(back, title, controls);
    element.append(heading);

    for (const image of row.images) {
      const proposedHeight = Math.max(1, Math.round(image.height * row.dominant_width / image.width));
      const section = document.createElement("article");
      section.className = "image-validation-divergence";
      const info = document.createElement("div");
      info.className = "image-validation-divergence-title";
      const filename = document.createElement("strong");
      filename.textContent = image.file;
      const difference = document.createElement("span");
      difference.textContent = `${image.difference_percent.toLocaleString("pt-BR")}% fora da largura dominante`;
      info.append(filename, difference);
      const comparison = document.createElement("div");
      comparison.className = "image-validation-compare";
      for (const [kind, label, dimensions] of [
        ["original", "ORIGINAL", `${image.width} × ${image.height} px`],
        ["proposed", "SOLUÇÃO PROPOSTA", `${row.dominant_width} × ${proposedHeight} px`],
      ]) {
        const card = document.createElement("div");
        card.className = "image-validation-card";
        const cardHead = document.createElement("div");
        cardHead.className = "image-validation-card-head";
        const strong = document.createElement("strong");
        strong.textContent = label;
        const size = document.createElement("span");
        size.textContent = dimensions;
        cardHead.append(strong, size);
        const stage = document.createElement("div");
        stage.className = "image-validation-stage";
        const imageElement = document.createElement("img");
        imageElement.alt = `${label.toLocaleLowerCase("pt-BR")} de ${image.file}`;
        imageElement.src = validationImageUrl(context.provider, context.manga, row.chapter, image.file, kind);
        imageElement.style.width = `${zoom}%`;
        stage.append(imageElement);
        card.append(cardHead, stage);
        comparison.append(card);
      }
      section.append(info, comparison);
      if (image.width < 300) {
        const warning = document.createElement("p");
        warning.className = "image-validation-warning";
        warning.textContent = "A ampliação corrige a largura, mas não recupera os detalhes perdidos na imagem de baixa resolução.";
        section.append(warning);
      }
      const actions = document.createElement("div");
      actions.className = "image-validation-actions";
      const note = document.createElement("span");
      note.textContent = "O original será preservado com o sufixo _old.";
      const apply = document.createElement("button");
      apply.className = "btn primary";
      apply.type = "button";
      apply.textContent = "Aplicar solução proposta";
      apply.addEventListener("click", () => onApply(row.chapter, image));
      actions.append(note, apply);
      section.append(actions);
      element.append(section);
    }
  }

  return { element, update };
}
