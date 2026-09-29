import { rulerPalette } from "/_shared/rulers/palette.js";

export function createRulerColorPicker(popover, colors, onChange) {
  function open(anchor, index) {
    popover.querySelector("[data-color-title]").textContent = `Cor da Régua ${index + 1}`;
    popover.querySelector("[data-color-options]").innerHTML = rulerPalette.map((color) =>
      `<button type="button" data-color="${color.value}" class="${colors[index] === color.value ? "selected" : ""}" aria-label="${color.name}" title="Selecionar cor"><i style="--swatch:${color.value}"></i></button>`
    ).join("");
    const bounds = anchor.getBoundingClientRect();
    popover.hidden = false;
    popover.style.left = `${Math.max(12, Math.min(window.innerWidth - 248, bounds.left))}px`;
    popover.style.top = `${Math.max(12, Math.min(window.innerHeight - 170, bounds.bottom + 8))}px`;
    popover.querySelectorAll("[data-color]").forEach((button) => button.addEventListener("click", () => {
      colors[index] = button.dataset.color;
      close();
      onChange();
    }));
  }

  function close() {
    popover.hidden = true;
  }

  function onOutside(event) {
    if (!popover.contains(event.target) && !event.target.closest("[data-ruler]")) close();
  }

  return { open, close, onOutside };
}
