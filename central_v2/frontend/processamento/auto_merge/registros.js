function selectionHeader(selected, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = selected;
  input.setAttribute("aria-label", "Selecionar capítulos desta página");
  input.addEventListener("change", () => onChange(input.checked));
  return input;
}

function chapterSelector(row, selected, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = selected;
  input.value = row.chapter;
  input.setAttribute("aria-label", `Selecionar capítulo ${row.chapter}`);
  input.addEventListener("change", () => onChange(row.chapter, input.checked));
  return input;
}

function mergeStatus(row) {
  if (row.official.status === "recorded") {
    return `✓ ${row.official.outputs_count}`;
  }
  if (row.official.status === "invalid") return "Revisar";
  return "—";
}

export function occurrence(row) {
  const messages = [row.level1.error, row.attempt.error, row.official.error,
    row.attempt.message].filter(Boolean);
  return messages.length ? messages.join(" · ") : "—";
}

export function matchesLevel1Filter(row, filter) {
  if (filter === "all") return true;
  if (filter === "clean") return Boolean(row.clean);
  if (filter === "pdf_merge") return Boolean(row.pdf_merge);
  if (filter === "occurrences") return occurrence(row) !== "—";
  if (filter === "merge") return ["recorded", "invalid"].includes(row.official.status);
  return false;
}

export function level1Label(record) {
  if (record.status === "absent") return "Sem registro";
  if (record.status === "invalid") return "Registro ilegível ou inválido";
  if (record.status !== "recorded") return "Formato não suportado";
  if (record.artifacts.some((file) => !file.exists)) return "Arquivos ausentes";
  return record.kind === "complete" ? "Completo no Nível I" : "Residual registrado";
}

export function needsAttention(row) {
  return [row.level1, row.attempt, row.official].some((item) => item.error)
    || (row.level1.artifacts || []).some((file) => !file.exists);
}

export function createColumns({ selected, onSelect, onSelectPage }) {
  return [
    {
      label: "Seleção",
      header: () => selectionHeader(selected.pageSelected, onSelectPage),
      render: (row) => chapterSelector(row, selected.chapters.has(row.chapter), onSelect),
    },
    { label: "CAP.", render: (row) => row.chapter },
    { label: "IMAGENS", render: (row) => row.pages },
    { label: "MERGE", render: mergeStatus, className: (row) => row.official.status === "recorded" ? "auto-merge-ok" : "" },
    { label: "CLEAN", render: (row) => row.clean ? "✓" : "—", className: (row) => row.clean ? "auto-merge-ok" : "" },
    { label: "PDF MERGE", render: (row) => row.pdf_merge ? "✓" : "—", className: (row) => row.pdf_merge ? "auto-merge-ok" : "" },
    { label: "OCORRÊNCIAS", render: occurrence, title: occurrence },
  ];
}
