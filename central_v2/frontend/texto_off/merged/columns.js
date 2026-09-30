import { createMappingColumns } from "/texto_off/merged/mapping.js";
import { createStageColumns } from "/texto_off/merged/stage_columns.js";
import { createStatusMark } from "/texto_off/merged/status_mark.js";

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
    { id: "chapter", label: "Capítulo", render: (row) => row.chapter },
    ...(mode === "level3" ? createMappingColumns(onInspect) : [
      { id: "merges", label: "MERGES", render: (row) => row.merge_valid ? row.merge_count : "—" },
    ]),
    ...(mode === "overview" ? createStageColumns() : mode === "level3" ? [] : [{
      id: "textoff-status",
      label: "TEXTO OFF",
      render: (row) => {
        const label = row.cleaned ? mode === "level3" ? "Analisado" : "Concluído" : row.selectable ? "Pendente" : "MERGE inválido";
        const state = row.cleaned ? "complete" : row.selectable ? "pending" : "review";
        return createStatusMark(label, state);
      },
      className: (row) => row.cleaned ? "textoff-status is-done" : row.selectable ? "textoff-status is-pending" : "textoff-status is-invalid",
    }]),
  ];
}
