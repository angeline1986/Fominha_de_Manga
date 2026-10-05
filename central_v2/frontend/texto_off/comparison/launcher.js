import { getContext, subscribeContext } from "/_app/state/context.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { createComparisonScreen } from "/texto_off/comparison/screen.js";

export function canCompare(row, step) {
  if (step === "1") return row.cleaned === true;
  if (step === "2") return row.cleaned === true;
  return row.comparison_available === true;
}

export function createComparisonLauncher(origin, step) {
  let screen = null, unsubscribe = null, focus = null, scroll = 0;
  function close(restore = true) {
    unsubscribe?.(); unsubscribe = null;
    screen?.dispose(); screen?.element.remove(); screen = null;
    origin.classList.remove("comparison-origin-hidden");
    if (restore && origin.parentElement) {
      origin.parentElement.scrollTop = scroll;
      if (focus?.isConnected) focus.focus({ preventScroll: true });
    }
  }
  function open(row, button) {
    close(false);
    const { provider, manga } = getContext();
    focus = button;
    scroll = origin.parentElement.scrollTop;
    screen = createComparisonScreen({ provider, manga, chapter: row.chapter, step }, close);
    origin.classList.add("comparison-origin-hidden");
    origin.after(screen.element);
    screen.start();
    unsubscribe = subscribeContext(() => {
      const current = getContext();
      if (current.provider !== provider || current.manga !== manga) close(false);
    });
  }
  return {
    column: {
      id: "comparison",
      header() {
        const title = document.createElement("span");
        title.innerHTML = iconMarkup("comparison");
        title.title = "Antes e Depois";
        title.setAttribute("role", "img");
        title.setAttribute("aria-label", "Antes e Depois");
        return title;
      },
      render(row) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn comparison-open";
        button.innerHTML = iconMarkup("eye");
        button.disabled = !canCompare(row, step);
        button.title = button.disabled ? "Sem resultado atual para comparar neste passo"
          : `Comparar capítulo ${row.chapter} — Passo ${step}`;
        button.setAttribute("aria-label", button.title);
        button.addEventListener("click", () => open(row, button));
        return button;
      },
    },
    dispose() { close(false); },
  };
}
