import { iconMarkup } from "/_shared/icons/icons.js";

export function sommelierColumns({ page, selected, executionBusy, draw, openReview }) {
  return [
    { id: "select", header: () => {
      const eligible = page.rows.filter((row) => row.merge_valid !== false);
      const count = eligible.filter((row) => selected.has(row.chapter)).length;
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = eligible.length > 0 && count === eligible.length;
      input.indeterminate = count > 0 && count < eligible.length;
      input.disabled = executionBusy || eligible.length === 0;
      input.setAttribute("aria-label", "Selecionar todos os capítulos desta página");
      input.addEventListener("change", () => {
        for (const row of eligible) {
          if (input.checked) selected.add(row.chapter);
          else selected.delete(row.chapter);
        }
        draw();
      });
      return input;
    }, render: (row) => {
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = selected.has(row.chapter);
      input.disabled = executionBusy || row.merge_valid === false;
      input.setAttribute("aria-label", `Selecionar capítulo ${row.chapter}`);
      input.addEventListener("change", () => {
        if (input.checked) selected.add(row.chapter);
        else selected.delete(row.chapter);
        draw();
      });
      return input;
    }},
    { id: "chapter", label: "Capítulo", render: (row) => row.chapter },
    { id: "merges", label: "MERGES", render: (row) => row.merge_valid ? row.merge_count : "—" },
    { id: "balloons", label: "BALÕES", render: (row) => row.sommelier?.balloons ?? "—" },
    { id: "candidates", label: "CANDIDATOS", render: (row) => row.sommelier?.candidates ?? "—" },
    { id: "profile", label: "PERFIL", render: (row) => row.sommelier?.analyzed ? row.sommelier.profile_id : "—" },
    { id: "review", label: "REVISAR", render: (row) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn sommelier-review";
      button.innerHTML = iconMarkup("eye");
      button.setAttribute("aria-label", "Visualizar capítulo");
      button.disabled = !row.sommelier?.analyzed;
      button.title = row.sommelier?.analyzed
        ? "Visualizar resultado do Bubble Sommelier" : "Disponível após a análise do Bubble Sommelier";
      button.addEventListener("click", () => openReview(row.chapter));
      return button;
    }},
  ];
}
