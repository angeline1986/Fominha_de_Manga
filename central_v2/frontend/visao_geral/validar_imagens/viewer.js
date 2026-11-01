import { validationImageUrl } from "/_app/api/image_validation.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";

export function createValidationViewer({ onBack, onApply }) {
  const element = document.createElement("section");
  element.className = "image-validation image-validation-viewer";
  let zoom = 100;
  let zoomMode = "fit";
  let disposeFocus = null;

  function imageWidth(image) {
    return zoomMode === "native"
      ? `${Math.round(Number(image.dataset.nativeWidth) * zoom / 100)}px`
      : `${zoom}%`;
  }

  function update(row, context) {
    const focused = element.classList.contains("is-focus-mode");
    disposeFocus?.();
    element.replaceChildren();
    const heading = document.createElement("header");
    heading.className = "image-validation-viewer-section";
    const sectionName = document.createElement("span");
    sectionName.textContent = "VALIDAR IMAGENS";
    const back = document.createElement("button");
    back.className = "btn";
    back.type = "button";
    back.innerHTML = `${iconMarkup("back")} Voltar à tabela`;
    back.addEventListener("click", onBack);
    heading.append(sectionName, back);
    const workspace = document.createElement("div");
    workspace.className = "image-validation-workspace";
    const toolbar = document.createElement("header");
    toolbar.className = "image-validation-viewer-toolbar";
    const title = document.createElement("div");
    title.className = "image-validation-viewer-title";
    const name = document.createElement("h1");
    name.textContent = "Validar Imagens — Revisão";
    const summary = document.createElement("span");
    summary.textContent = row.images.length === 1
      ? `Cap. ${row.chapter} · ${row.images[0].file} · 1 de 1 divergência`
      : `Cap. ${row.chapter} · ${row.images.length} páginas divergentes`;
    title.append(name, summary);
    const controls = document.createElement("div");
    controls.className = "image-validation-zoom";
    controls.setAttribute("aria-label", "Controles de zoom");
    const zoomText = document.createElement("output");
    zoomText.textContent = `${zoom}%`;
    function setZoom(value, mode = zoomMode) {
      zoom = Math.min(150, Math.max(50, value));
      zoomMode = mode;
      zoomText.textContent = `${zoom}%`;
      element.querySelectorAll(".image-validation-stage img").forEach((img) => {
        img.style.width = imageWidth(img);
      });
    }
    for (const [symbol, change, name] of [["−", -10, "Diminuir zoom"], ["+", 10, "Aumentar zoom"]]) {
      const button = document.createElement("button");
      button.className = "btn";
      button.type = "button";
      button.textContent = symbol;
      button.setAttribute("aria-label", name);
      button.addEventListener("click", () => setZoom(zoom + change));
      if (change < 0) controls.append(button, zoomText);
      else controls.append(button);
    }
    const nativeZoom = document.createElement("button");
    nativeZoom.className = "btn image-validation-zoom-reset";
    nativeZoom.type = "button";
    nativeZoom.textContent = "1:1";
    nativeZoom.setAttribute("aria-label", "Visualizar em escala 1 para 1");
    nativeZoom.addEventListener("click", () => setZoom(100, "native"));
    controls.append(nativeZoom);
    const toolbarControls = document.createElement("div");
    toolbarControls.className = "image-validation-viewer-controls";
    const focus = document.createElement("button");
    focus.className = "btn image-validation-focus";
    focus.type = "button";
    focus.innerHTML = `${iconMarkup("focus-exit")} Foco`;
    focus.setAttribute("aria-label", "Modo Foco");
    focus.setAttribute("aria-pressed", "false");
    toolbarControls.append(controls, focus);
    toolbar.append(title, toolbarControls);
    workspace.append(toolbar);
    element.append(heading, workspace);
    disposeFocus = bindFocusMode(element, { button: focus, active: focused });

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
        imageElement.dataset.nativeWidth = String(kind === "original" ? image.width : row.dominant_width);
        imageElement.style.width = imageWidth(imageElement);
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
      workspace.append(section);
    }
  }

  return { element, update, dispose() { disposeFocus?.(); disposeFocus = null; } };
}
