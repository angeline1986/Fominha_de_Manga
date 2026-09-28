function chapterCheckbox(row, selected, onSelect) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = selected.has(row.chapter);
  input.setAttribute("aria-label", `Selecionar capítulo ${row.chapter}`);
  input.addEventListener("change", () => onSelect(row.chapter, input.checked));
  return input;
}

function pageCheckbox(selected, onSelectPage) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = selected.pageSelected;
  input.setAttribute("aria-label", "Selecionar capítulos desta página");
  input.addEventListener("change", () => onSelectPage(input.checked));
  return input;
}

export function createLevel2Columns({ selected, onSelect, onSelectPage }) {
  return [
    { label: "Seleção", header: () => pageCheckbox(selected, onSelectPage),
      render: (row) => chapterCheckbox(row, selected.chapters, onSelect) },
    { label: "CAP.", render: (row) => row.chapter },
    { label: "RESIDUAL RECEBIDO", render: (row) => row.residual_segments },
    { label: "REGIÃO DO RESIDUAL", render: (row) => (row.residual_regions || []).join("; ") || "—" },
  ];
}
