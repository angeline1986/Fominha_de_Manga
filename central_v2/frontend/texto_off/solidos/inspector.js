import { createComparisonScreen } from "/texto_off/comparison/screen.js";
import { iconMarkup } from "/_shared/icons/icons.js";

export function createSolidInspector(root) {
  let screen = null, sourceButton = null, scrollTop = 0;
  const close = (restore = true) => {
    screen?.dispose(); screen?.element.remove(); screen = null;
    root.classList.remove("comparison-origin-hidden");
    if (restore) {
      if (root.parentElement) root.parentElement.scrollTop = scrollTop;
      sourceButton?.focus({ preventScroll: true });
    }
  };
  return {
    open(row, context) {
      close(false);
      sourceButton = document.activeElement;
      scrollTop = root.parentElement?.scrollTop || 0;
      screen = createComparisonScreen({
        provider: context.provider, manga: context.manga, chapter: row.chapter,
        step: "solid", comparisonMode: "solid", scope: "solid",
        ...(row.rowType === "page" ? { initialPage: row.name } : {}),
      }, close);
      const back = document.createElement("button");
      back.className = "btn comparison-back";
      back.type = "button";
      back.innerHTML = `${iconMarkup("back")} Voltar ao Auto-Cleaner: Sólidos`;
      back.addEventListener("click", () => close());
      screen.element.querySelector(".comparison-page-heading").prepend(back);
      root.classList.add("comparison-origin-hidden");
      root.after(screen.element);
      screen.start();
    },
    dispose() { close(false); },
  };
}
