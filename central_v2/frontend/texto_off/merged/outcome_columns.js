import { iconMarkup } from "/_shared/icons/icons.js";
import { OUTCOME_FILTERS, matchesOutcome } from "/texto_off/merged/outcome_filters.js";

export function createOutcomeColumns() {
  return OUTCOME_FILTERS.filter(([key]) => key !== "all").map(([key, label]) => ({
    id: key,
    label,
    render(row) {
      const active = matchesOutcome(row, key);
      const mark = document.createElement("span");
      mark.className = `cleaner-outcome-mark${active ? " is-active" : ""}`;
      const detail = key === "residue" ? "Resíduo adiado no Passo 1" : label;
      mark.title = `${detail}: ${active ? "Sim" : "Não"}`;
      mark.setAttribute("aria-label", mark.title);
      if (active) mark.innerHTML = iconMarkup("check");
      else mark.textContent = "—";
      return mark;
    },
  }));
}
