// Read-only display controls for the shared Degradê comparison slider.
import { iconMarkup } from "/_shared/icons/icons.js";

export function bindDegradeViewTools(host, slider) {
  const controls = document.createElement("div");
  controls.className = "comparison-degrade-tools";
  controls.setAttribute("aria-label", "Visão da comparação Degradê");
  for (const [value, label] of [["before", "Antes"], ["dual", "Dupla"], ["after", "Depois"]]) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn comparison-view-button";
    button.dataset.view = value; button.textContent = label;
    button.setAttribute("aria-pressed", String(value === "dual"));
    controls.append(button);
  }
  const ruler = document.createElement("button");
  ruler.type = "button"; ruler.className = "btn comparison-view-button";
  ruler.dataset.rulers = ""; ruler.innerHTML = `${iconMarkup("ruler")} Régua`;
  ruler.setAttribute("aria-pressed", "false");
  controls.append(ruler); host.append(controls);
  function onClick(event) {
    const button = event.target.closest("[data-view], [data-rulers]");
    if (!button) return;
    if (button.hasAttribute("data-view")) {
      slider.setView(button.dataset.view);
      controls.querySelectorAll("[data-view]").forEach((item) => {
        item.setAttribute("aria-pressed", String(item === button));
      });
    } else {
      const active = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(active));
      slider.setRulers(active);
    }
  }
  controls.addEventListener("click", onClick);
  return () => { controls.removeEventListener("click", onClick); controls.remove(); };
}
