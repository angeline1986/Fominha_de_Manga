const FILTERS = [
  ["all", "All"],
  ["pending", "Do"],
  ["analyzed", "Done"],
  ["candidates", "Candidato"],
];

export function matchesSommelierRow(row, key) {
  if (key === "all") return true;
  if (key === "pending") return !row.sommelier?.analyzed;
  if (key === "analyzed") return Boolean(row.sommelier?.analyzed);
  if (key === "candidates") {
    return Boolean(row.sommelier?.analyzed && row.sommelier.candidates > 0);
  }
  return false;
}

export function drawSommelierFilters(filters, rows, activeFilter, onSelect) {
  filters.replaceChildren();
  for (const [key, label] of FILTERS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "auto-merge-filter-button";
    button.classList.toggle("active", activeFilter === key);
    button.textContent = `${label} (${rows.filter((row) => matchesSommelierRow(row, key)).length})`;
    button.setAttribute("aria-pressed", String(activeFilter === key));
    button.addEventListener("click", () => onSelect(key));
    filters.append(button);
  }
}
