import { iconMarkup } from "/_shared/icons/icons.js";

export const MAPPING_FILTERS = [
  ["all", "ALL"], ["map", "Mapear"], ["degrade", "Degradê"],
  ["artistic", "Artístico"], ["soft", "Suave"],
];

export function matchesMapping(row, key) {
  if (key === "all") return true;
  return key === "map" ? row.cleaned === true : row.retouch?.[key] === true;
}

export function createMappingColumns(onInspect) {
  return MAPPING_FILTERS.filter(([key]) => key !== "all").map(([key, label]) => ({
    id: key,
    label,
    render(row) {
      const active = matchesMapping(row, key);
      const inspect = key === "map" && active && row.candidate_pages?.length && onInspect;
      const mark = document.createElement(inspect ? "button" : "span");
      mark.className = inspect ? "btn mapping-review" : "cleaner-outcome-mark";
      mark.classList.toggle("is-active", active);
      mark.title = inspect ? "Ver balões mapeados" : `${label}: ${active ? "Sim" : "Não"}`;
      mark.setAttribute("aria-label", mark.title);
      if (active) mark.innerHTML = iconMarkup("check");
      else mark.textContent = "—";
      if (inspect) {
        mark.type = "button";
        mark.addEventListener("click", () => onInspect(row));
      }
      return mark;
    },
  }));
}
