export const OUTCOME_FILTERS = [
  ["all", "ALL"], ["pending", "Pendente"], ["processed", "Concluído"],
  ["unchanged", "Inalterado"], ["residue", "Resíduo"],
];

export function matchesOutcome(row, filter) {
  if (filter === "all") return true;
  if (filter === "residue") return row.cleaned === true && Number(row.deferred_components) > 0;
  const status = row.cleaner_status ?? row.level2_status;
  return status === ({ pending: "pending", processed: "processed", unchanged: "no_change" })[filter];
}

export function drawOutcomeFilters(container, rows, active, onSelect) {
  container.replaceChildren();
  for (const [key, label] of OUTCOME_FILTERS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "auto-merge-filter-button";
    const count = rows.filter((row) => matchesOutcome(row, key)).length;
    button.textContent = key === "residue" ? label : `${label} (${count})`;
    if (key === "residue") button.title = "Capítulos com resíduos adiados registrados no Passo 1";
    button.classList.toggle("active", active === key);
    button.setAttribute("aria-pressed", String(active === key));
    button.addEventListener("click", () => onSelect(key));
    container.append(button);
  }
}
