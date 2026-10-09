import { renderSpecialWorklist } from "/texto_off/especiais/artistico_table.js";

export function matchesSpecialRow(row, term, filter) {
  const search = term.trim().toLocaleLowerCase("pt-BR");
  const matchesText = !search || row.chapter.toLocaleLowerCase("pt-BR").includes(search)
    || row.pages.some((page) => page.toLocaleLowerCase("pt-BR").includes(search));
  const matchesStatus = filter === "all" || (filter === "completed"
    ? ["processed", "no_change"].includes(row.status) : row.status === "pending");
  return matchesText && matchesStatus;
}

export function renderSpecialTable(container, treatment) {
  if (!["degrade", "gradiente_suave"].includes(treatment))
    throw new Error("Tratamento especial inválido.");
  return renderSpecialWorklist(container, treatment);
}
