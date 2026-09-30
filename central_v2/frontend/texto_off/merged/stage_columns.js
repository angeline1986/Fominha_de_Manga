import { iconMarkup } from "/_shared/icons/icons.js";
import { STAGES, RETOUCH } from "/texto_off/merged/stage_filters.js";

function booleanMark(value, label) {
  const mark = document.createElement("span");
  mark.className = `cleaner-stage-mark${value ? " is-complete" : ""}`;
  mark.title = label;
  mark.setAttribute("aria-label", label);
  if (value) mark.innerHTML = iconMarkup("check");
  else mark.textContent = "—";
  return mark;
}

export function createStageColumns() {
  return STAGES.filter(([key]) => key !== "all").map(([key, label]) => ({
    id: key,
    label,
    render(row) {
      if (key === "retouch") {
        const names = RETOUCH.filter(([name]) => row.retouch?.[name]).map(([, name]) => name);
        const value = document.createElement("span");
        value.className = "cleaner-retouch-types";
        value.textContent = names.join(" · ") || "—";
        value.title = names.length ? "Retoques com prévia disponível" : "Sem retoque registrado";
        return value;
      }
      const done = row.stages?.[key] === true;
      const detail = ["ac3", "ac4"].includes(key) ? "Prévia disponível" : "Realizado";
      return booleanMark(done, `${label}: ${done ? detail : "Sem registro atual"}`);
    },
  }));
}
