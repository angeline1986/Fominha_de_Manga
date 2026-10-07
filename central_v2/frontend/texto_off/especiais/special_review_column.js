import { iconMarkup } from "/_shared/icons/icons.js";

export function specialReviewColumn(treatment, launcher) {
  if (treatment !== "degrade") return {
    id: "review", label: "REVISAR", render: (row) => launcher.column.render(row),
  };
  return { id: "review", label: "REVISAR", render: (row) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn sommelier-review";
    button.innerHTML = iconMarkup("eye");
    button.disabled = row.review_available !== true || !["processed", "no_change"].includes(row.status);
    button.title = button.disabled ? "Resultado Degradê indisponível para revisão"
      : `Revisar Degradê do capítulo ${row.chapter}`;
    button.setAttribute("aria-label", button.title);
    if (!button.disabled) button.addEventListener("click", () => launcher.open(row, button));
    return button;
  } };
}
