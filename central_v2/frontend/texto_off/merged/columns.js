function checkbox(label, checked, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = checked;
  input.setAttribute("aria-label", label);
  input.addEventListener("change", () => onChange(input.checked));
  return input;
}

export function createMergedColumns({ rows, selected, pageChapters, onSelect, onSelectPage, onInspect, mode }) {
  const eligible = pageChapters.filter((chapter) => rows.find((row) => row.chapter === chapter)?.selectable);
  return [
    {
      id: "select",
      header: () => {
        const input = checkbox("Selecionar todos os capítulos desta página", eligible.length > 0 && eligible.every((name) => selected.has(name)), onSelectPage);
        input.disabled = eligible.length === 0;
        return input;
      },
      render: (row) => {
        const input = checkbox(`Selecionar capítulo ${row.chapter}`, selected.has(row.chapter), (checked) => onSelect(row.chapter, checked));
        input.disabled = !row.selectable;
        return input;
      },
    },
    { id: "chapter", label: "Cap.", render: (row) => row.chapter },
    { id: "merges", label: "MERGES", render: (row) => row.merge_valid ? row.merge_count : "—" },
    ...(mode === "level3" ? [{ id: "candidates", label: "Balões candidatos", render: (row) => row.cleaned ? row.candidate_count : "—" }] : []),
    ...(mode === "level3" ? [{ id: "review", label: "Resultado", render: (row) => {
      if (!row.cleaned || !row.candidate_count) return "—";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn textoff-candidate-view-button";
      button.textContent = "Ver candidatos";
      button.addEventListener("click", () => onInspect?.(row));
      return button;
    } }] : []),
    {
      id: "textoff-status",
      label: "TEXTO OFF",
      render: (row) => row.cleaned ? mode === "level3" ? "Nível III analisado" : "Resultado registrado" : row.selectable ? "Sem resultado" : "MERGE inválido",
      className: (row) => row.cleaned ? "textoff-status is-done" : row.selectable ? "textoff-status is-pending" : "textoff-status is-invalid",
    },
  ];
}
