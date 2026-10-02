import { iconMarkup } from "/_shared/icons/icons.js";

export function renderResidueOccurrences(overlay, layers, occurrences, options) {
  overlay.querySelectorAll("[data-box-id], [data-live-box]").forEach((box) => box.remove());
  const rows = [];
  occurrences.forEach((item, index) => {
    const number = index + 1;
    const box = document.createElement("div");
    box.className = "comparison-residue-box"; box.dataset.boxId = item.id;
    box.style.left = `${item.box.left * 100}%`; box.style.top = `${item.box.top * 100}%`;
    box.style.width = `${item.box.width * 100}%`; box.style.height = `${item.box.height * 100}%`;
    box.innerHTML = `<span class="comparison-residue-number">${number}</span><button class="btn comparison-residue-delete" type="button" data-remove="${item.id}" aria-label="Remover área ${number}">${iconMarkup("close")}</button>`;
    overlay.append(box);
    const row = document.createElement("div");
    row.className = "comparison-residue-row"; row.dataset.occurrenceId = item.id;
    row.innerHTML = `<span class="comparison-residue-number">${number}</span><select aria-label="Tipo da área ${number}" data-type="${item.id}">${options}</select><button class="btn comparison-residue-delete" type="button" data-remove="${item.id}" aria-label="Remover área ${number}">${iconMarkup("close")}</button>`;
    row.querySelector("select").value = item.type;
    if (item.type === "outro") appendNote(row, item, number);
    rows.push(row);
  });
  layers.replaceChildren(...rows);
}

function appendNote(row, item, number) {
  const input = document.createElement("input"); input.type = "text";
  input.placeholder = "Descreva o defeito...";
  input.setAttribute("aria-label", `Descrição da área ${number}`);
  input.dataset.note = item.id; input.value = item.note || "";
  row.append(input);
}
