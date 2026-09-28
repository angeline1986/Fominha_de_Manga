import { renderStatusBadge } from "/processamento/auto_merge/filtros_estado.js";

function chapterCheckbox(row, selected, onSelect) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = selected.has(row.chapter);
  input.disabled = row.eligible === false;
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

export function createLevel3Columns({ selected, onSelect, onSelectPage }) {
  return [
    { label: "Seleção", header: () => pageCheckbox(selected, onSelectPage),
      render: (row) => chapterCheckbox(row, selected.chapters, onSelect) },
    { label: "CAP.", render: (row) => row.chapter },
    { label: "IMAGENS", render: (row) => row.residual_images },
    { label: "RESÍDUOS", render: (row) => row.residual_segments },
    { label: "REGIÃO DO RESÍDUO", render: (row) => (row.residual_regions || []).join("; ") || "—",
      title: (row) => (row.residual_regions || []).join("; ") || "—" },
    { label: "ESTADO", render: renderStatusBadge },
  ];
}
