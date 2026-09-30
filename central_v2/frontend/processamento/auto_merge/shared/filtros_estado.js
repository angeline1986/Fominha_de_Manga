const FILTERS = [
  ["all", "Todos"],
  ["pending", "Pendente"],
  ["partial", "Parcial"],
  ["resolved", "Resolvido"],
  ["invalid", "Revisar"],
];

export function createStatusFilters(container, { chapters, value, onChange }) {
  container.replaceChildren();
  for (const [key, label] of FILTERS) {
    const count = chapters.filter((row) => matchesStatus(row, key)).length;
    const button = document.createElement("button");
    button.className = "auto-merge-filter-button";
    button.type = "button";
    button.textContent = `${label} (${count})`;
    button.classList.toggle("active", key === value);
    button.setAttribute("aria-pressed", String(key === value));
    button.addEventListener("click", () => onChange(key));
    container.append(button);
  }
}

export function matchesStatus(row, filter) {
  if (filter === "all") return true;
  if (filter === "pending") return row.eligible !== false && !["Parcial", "Resolvido", "Registro inválido"].includes(row.status);
  if (filter === "partial") return row.status === "Parcial";
  if (filter === "resolved") return row.status === "Resolvido";
  return row.status === "Registro inválido";
}

export function renderStatusBadge(row) {
  const status = row.status || "Disponível";
  const badge = document.createElement("span");
  badge.className = `auto-merge-badge ${status === "Parcial" ? "partial" : status === "Resolvido" ? "resolved" : status === "Registro inválido" ? "invalid" : "pending"}`;
  badge.textContent = status === "Disponível" ? "Pendente" : status === "Resolvido" ? "Resolvido" : status === "Registro inválido" ? "Revisar" : status;
  return badge;
}
