// Accessible image previews for navigation controls.

let previewSequence = 0;

export function bindHoverPreview(container) {
  const preview = document.createElement("aside");
  preview.className = "navigation-hover-preview";
  preview.id = `navigation-hover-preview-${++previewSequence}`;
  preview.setAttribute("role", "tooltip");
  preview.hidden = true;
  document.body.append(preview);
  let activeButton = null;

  function position(button) {
    const anchor = button.getBoundingClientRect();
    const bounds = preview.getBoundingClientRect();
    const gap = 12;
    const left = anchor.right + bounds.width + gap <= window.innerWidth - 12
      ? anchor.right + gap : Math.max(12, anchor.left - bounds.width - gap);
    const top = Math.max(12, Math.min(
      anchor.top + (anchor.height - bounds.height) / 2,
      window.innerHeight - bounds.height - 12,
    ));
    preview.style.setProperty("--preview-left", `${left}px`);
    preview.style.setProperty("--preview-top", `${top}px`);
  }

  function show(button) {
    activeButton = button;
    const title = button.dataset.previewTitle;
    preview.replaceChildren();
    const heading = document.createElement("strong");
    heading.textContent = title;
    const examples = document.createElement("div");
    examples.className = "navigation-hover-preview-images";
    [["ANTES", button.dataset.previewBefore], ["DEPOIS", button.dataset.previewAfter]]
      .forEach(([label, src]) => {
        const figure = document.createElement("figure");
        const caption = document.createElement("figcaption");
        const image = document.createElement("img");
        caption.textContent = label;
        image.src = src;
        image.alt = `${title} — ${label.toLocaleLowerCase("pt-BR")}`;
        image.decoding = "async";
        figure.append(caption, image);
        examples.append(figure);
      });
    preview.append(heading, examples);
    preview.hidden = false;
    button.setAttribute("aria-describedby", preview.id);
    position(button);
  }

  function hide() {
    activeButton?.removeAttribute("aria-describedby");
    activeButton = null;
    preview.hidden = true;
  }

  function handlePointerOver(event) {
    const button = event.target.closest("[data-preview-before]");
    if (button && container.contains(button) && !button.contains(event.relatedTarget)) show(button);
  }

  function handlePointerOut(event) {
    const button = event.target.closest("[data-preview-before]");
    if (button === activeButton && !button.contains(event.relatedTarget)) hide();
  }

  function handleFocus(event) {
    const button = event.target.closest("[data-preview-before]");
    if (button && container.contains(button)) show(button);
  }

  function handleBlur(event) {
    if (activeButton && !activeButton.contains(event.relatedTarget)) hide();
  }

  function handleClick(event) {
    if (event.target.closest("[data-action]")) hide();
  }

  container.addEventListener("pointerover", handlePointerOver);
  container.addEventListener("pointerout", handlePointerOut);
  container.addEventListener("focusin", handleFocus);
  container.addEventListener("focusout", handleBlur);
  container.addEventListener("click", handleClick, true);
  window.addEventListener("resize", hide);
  window.addEventListener("scroll", hide, true);

  return () => {
    hide();
    preview.remove();
    container.removeEventListener("pointerover", handlePointerOver);
    container.removeEventListener("pointerout", handlePointerOut);
    container.removeEventListener("focusin", handleFocus);
    container.removeEventListener("focusout", handleBlur);
    container.removeEventListener("click", handleClick, true);
    window.removeEventListener("resize", hide);
    window.removeEventListener("scroll", hide, true);
  };
}
