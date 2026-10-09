const completed = (value) => ["processed", "no_change"].includes(value);

export function styledSelection(row, selected) {
  const eligible = (row.occurrences || []).filter((item) => completed(item.status)
    && !item.reexecution_blocked && item.expected_sha256);
  return eligible.find((item) => item.id === selected.get(row.chapter)) || eligible[0];
}

export function styledOccurrenceColumn(selected) {
  return { id: "styled_occurrence", label: "OCORRÊNCIA", render: (row) => {
    const wrapper = document.createElement("div");
    wrapper.className = "sommelier-occurrence-picker";
    const select = document.createElement("select");
    select.className = "sommelier-occurrence-select";
    select.setAttribute("aria-label", `Ocorrência Artística do capítulo ${row.chapter}`);
    for (const item of row.occurrences || []) {
      const option = document.createElement("option");
      option.value = item.id;
      const box = item.roi || {};
      option.textContent = `${item.page} · ${item.id}`;
      option.disabled = !completed(item.status) || item.reexecution_blocked || !item.expected_sha256;
      option.title = item.reexecution_block_reason ||
        `Filtro atual: ${item.current_filter}; solicitado: ${item.requested_filter}`;
      select.append(option);
    }
    const current = styledSelection(row, selected);
    select.disabled = !current;
    if (current) select.value = current.id;
    select.title = current ? `Filtro atual: ${current.current_filter}; solicitado: ${current.requested_filter}. Use Revisar para ver antes/depois.`
      : row.reexecution_block_reason || "Nenhuma ocorrência com autoria verificável.";
    const detail = document.createElement("small");
    detail.className = "sommelier-occurrence-detail";
    function describe(item) {
      const box = item?.roi || {};
      detail.textContent = item ? `ROI ${box.x},${box.y} · ${box.width}×${box.height} · ${item.current_filter} → ${item.requested_filter}`
        : row.reexecution_block_reason || "Sem autoria verificável";
    }
    describe(current);
    select.addEventListener("change", () => {
      selected.set(row.chapter, select.value);
      describe(styledSelection(row, selected));
    });
    wrapper.append(select, detail);
    return wrapper;
  } };
}

export function reexecutionColumn({ treatment, title, busy, selected, run }) {
  return { id: "reexecute", label: "AÇÃO", render: (row) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn sommelier-reexecute";
    const eligible = completed(row.status) || (row.statuses || []).some(completed);
    const choice = treatment === "estilizado" ? styledSelection(row, selected) : null;
    const blocked = treatment === "estilizado" && !choice;
    button.disabled = busy() || !eligible || blocked;
    button.textContent = blocked ? "Histórico indisponível" : "Reexecutar";
    button.title = blocked ? row.reexecution_block_reason || "Selecione uma ocorrência verificável." : "";
    button.setAttribute("aria-label", blocked
      ? `Reexecução bloqueada em ${row.chapter}: ${button.title}`
      : `Reexecutar ${title} no capítulo ${row.chapter}`);
    if (eligible) button.addEventListener("click", () => {
      const selectedOccurrence = treatment === "estilizado" ? styledSelection(row, selected) : null;
      if (treatment === "estilizado" && !selectedOccurrence) return;
      run?.([row.chapter], false, true,
        selectedOccurrence ? [{ chapter: row.chapter, page: selectedOccurrence.page,
          id: selectedOccurrence.id, expected_sha256: selectedOccurrence.expected_sha256,
          roi: selectedOccurrence.roi, current_filter: selectedOccurrence.current_filter,
          requested_filter: selectedOccurrence.requested_filter }] : undefined);
    });
    return button;
  } };
}
