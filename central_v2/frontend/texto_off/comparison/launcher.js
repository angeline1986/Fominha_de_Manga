import { getContext, subscribeContext } from "/_app/state/context.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { comparisonModeForStep } from "/texto_off/comparison/model.js";
import { createComparisonScreen } from "/texto_off/comparison/screen.js";
import { createMapearComparisonScreen } from "/texto_off/comparison/mapear_screen.js";

export function canCompare(row, step, mode = comparisonModeForStep(step)) {
  if (mode === "mapear") return row.cleaned === true && row.candidate_pages?.length > 0;
  if (mode === "level1" || mode === "level2" || mode === "before_after" || mode === "check") return row.cleaned === true;
  if (["degrade", "suave", "artistico"].includes(mode)) return row.review_available === true;
  return row.comparison_available === true;
}

export function createComparisonLauncher(origin, step, mode = comparisonModeForStep(step), scope = "") {
  let screen = null, unsubscribe = null, focus = null, scroll = 0;
  let availableChapters = [];
  function close(restore = true) {
    unsubscribe?.(); unsubscribe = null;
    screen?.dispose(); screen?.element.remove(); screen = null;
    origin.classList.remove("comparison-origin-hidden");
    if (restore && origin.parentElement) {
      origin.parentElement.scrollTop = scroll;
      if (focus?.isConnected) focus.focus({ preventScroll: true });
    }
  }
  function open(row, button, target = {}, viewState = null) {
    close(false);
    const { provider, manga } = getContext();
    focus = button;
    scroll = origin.parentElement.scrollTop;
    const createScreen = mode === "mapear" ? createMapearComparisonScreen : createComparisonScreen;
    screen = createScreen({ provider, manga, chapter: row.chapter, step,
      ...(mode === "mapear" ? { mapearPages: row.candidate_pages } : {}),
      availableChapters: availableChapters.filter((entry) => canCompare(entry, step, mode)),
      onChapterChange: (chapter) => {
        const targetRow = availableChapters.find((entry) => String(entry.chapter) === String(chapter));
        if (targetRow && canCompare(targetRow, step, mode)) open(targetRow, button, {}, screen?.getViewState?.());
      },
      ...(viewState ? { viewState } : {}),
      comparisonMode: mode, ...(scope ? { scope } : {}),
      ...(target.page ? { initialPage: target.page } : {}),
      ...(target.occurrence ? { initialOccurrence: target.occurrence } : {}) }, close);
    if (["degrade", "suave", "artistico", "mapear"].includes(mode)) {
      const back = document.createElement("button");
      back.type = "button"; back.className = "btn comparison-back";
      const label = { degrade: "Degradê", suave: "Suave", artistico: "Artístico", mapear: "Mapear" }[mode];
      back.innerHTML = `${iconMarkup("back")} Voltar ao ${label}`;
      back.addEventListener("click", () => close());
      screen.element.querySelector(".comparison-page-heading").prepend(back);
    }
    origin.classList.add("comparison-origin-hidden");
    origin.after(screen.element);
    screen.start();
    unsubscribe = subscribeContext(() => {
      const current = getContext();
      if (current.provider !== provider || current.manga !== manga) close(false);
    });
  }
  return {
    open,
    setChapters(chapters) { availableChapters = Array.isArray(chapters) ? chapters : []; },
    column: {
      id: "comparison",
      header() {
        const title = document.createElement("span");
        title.innerHTML = iconMarkup("comparison");
        title.title = mode === "mapear" ? "Ver balões mapeados" : "Antes e Depois";
        title.setAttribute("role", "img");
        title.setAttribute("aria-label", title.title);
        return title;
      },
      render(row) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn comparison-open";
        button.innerHTML = iconMarkup("eye");
        button.disabled = !canCompare(row, step, mode);
        button.title = button.disabled ? mode === "mapear" ? "Sem balões mapeados neste capítulo"
          : "Sem resultado atual para comparar neste passo"
          : mode === "mapear" ? `Ver balões mapeados no capítulo ${row.chapter}`
          : `Comparar capítulo ${row.chapter} — Passo ${step}`;
        button.setAttribute("aria-label", button.title);
        button.addEventListener("click", () => open(row, button));
        return button;
      },
    },
    dispose() { close(false); },
  };
}
