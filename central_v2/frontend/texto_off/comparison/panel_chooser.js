const DEFAULT_PANELS = ["original", "level1", "level2", "final"];

export function normalizeVisiblePanels(value) {
  if (!Array.isArray(value)) return [...DEFAULT_PANELS];
  const selected = DEFAULT_PANELS.filter((key) => value.includes(key));
  return selected.length >= 2 ? selected : [...DEFAULT_PANELS];
}

export function panelChooserMarkup(mode) {
  if (mode !== "before_after") return "";
  const labels = ["Original", "Auto-Cleaner I", "Auto-Cleaner II", "Consolidado Final"];
  return `<div class="comparison-panel-chooser" data-panel-chooser>
    <button type="button" class="btn comparison-panel-button" data-panel-button
      aria-controls="comparison-panel-choices" aria-expanded="false">Quadros</button>
    <div class="comparison-panel-choices" id="comparison-panel-choices" data-panel-choices
      role="group" aria-label="Quadros visíveis" hidden>
      ${DEFAULT_PANELS.map((key, index) => `<label><input type="checkbox" data-panel="${key}" checked>
        <span>${labels[index]}</span></label>`).join("")}
    </div>
  </div>`;
}

export function bindPanelChooser(element, slider, savedPanels) {
  const root = element.querySelector("[data-panel-chooser]");
  const button = root.querySelector("[data-panel-button]");
  const choices = root.querySelector("[data-panel-choices]");
  const inputs = [...root.querySelectorAll("input[data-panel]")];
  let selected = normalizeVisiblePanels(savedPanels);

  function render() {
    inputs.forEach((input) => {
      input.checked = selected.includes(input.dataset.panel);
      input.disabled = selected.length === 2 && input.checked;
    });
    button.setAttribute("aria-label", `Quadros visíveis: ${selected.map((key) =>
      inputs.find((input) => input.dataset.panel === key)?.nextElementSibling?.textContent?.trim()
      || key).join(", ")}`);
    slider.setVisiblePanels?.(selected);
  }

  function close() {
    choices.hidden = true;
    button.setAttribute("aria-expanded", "false");
  }

  function toggle() {
    choices.hidden = !choices.hidden;
    button.setAttribute("aria-expanded", String(!choices.hidden));
  }

  function onChange(event) {
    const input = event.target.closest("input[data-panel]");
    if (!input) return;
    const next = DEFAULT_PANELS.filter((key) =>
      key === input.dataset.panel ? input.checked : selected.includes(key));
    if (next.length >= 2) selected = next;
    render();
  }

  function onKeyDown(event) {
    if (event.key !== "Escape" || choices.hidden) return;
    event.preventDefault();
    event.stopPropagation();
    close();
    button.focus();
  }

  button.addEventListener("click", toggle);
  root.addEventListener("change", onChange);
  root.addEventListener("keydown", onKeyDown);
  render();
  return {
    selected: () => [...selected],
    dispose() {
      button.removeEventListener("click", toggle);
      root.removeEventListener("change", onChange);
      root.removeEventListener("keydown", onKeyDown);
    },
  };
}
