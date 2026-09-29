function checkbox(label, checked, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = checked;
  input.setAttribute("aria-label", label);
  input.addEventListener("change", () => onChange(input.checked));
  return input;
}

export function createMergedColumns({ rows, selected, pageChapters, onSelect, onSelectPage }) {
  const eligible = pageChapters.filter((chapter) => rows.find((row) => row.chapter === chapter)?.selectable);
  return [
    {
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
    { label: "Cap.", render: (row) => row.chapter },
    { label: "MERGES", render: (row) => row.merge_valid ? row.merge_count : "—" },
    {
      label: "TEXTO OFF",
      render: (row) => row.cleaned ? "Resultado registrado" : row.selectable ? "Sem resultado" : "MERGE inválido",
      className: (row) => row.cleaned ? "textoff-status is-done" : row.selectable ? "textoff-status is-pending" : "textoff-status is-invalid",
    },
  ];
}
