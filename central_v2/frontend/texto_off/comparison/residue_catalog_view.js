import { iconMarkup } from "/_shared/icons/icons.js";

export function renderResidueOccurrences(overlay, layers, occurrences, options, { readOnly = false } = {}) {
  overlay.querySelectorAll("[data-box-id], [data-live-box]").forEach((box) => box.remove());
  const rows = [];
  occurrences.forEach((item, index) => {
    const number = index + 1;
    const box = document.createElement("div");
    box.className = "comparison-residue-box"; box.dataset.boxId = item.id;
    box.style.left = `${item.box.left * 100}%`; box.style.top = `${item.box.top * 100}%`;
    box.style.width = `${item.box.width * 100}%`; box.style.height = `${item.box.height * 100}%`;
    box.innerHTML = `<span class="comparison-residue-number">${number}</span>${readOnly ? "" : `<button class="btn comparison-residue-delete" type="button" data-remove="${item.id}" aria-label="Remover área ${number}">${iconMarkup("close")}</button>`}`;
    overlay.append(box);
    const row = document.createElement("div");
    row.className = "comparison-residue-row"; row.dataset.occurrenceId = item.id;
    if (readOnly) {
      const numberLabel = document.createElement("span");
      numberLabel.className = "comparison-residue-number";
      numberLabel.textContent = String(number);
      const identity = document.createElement("span");
      identity.textContent = item.id;
      row.append(numberLabel, identity);
      rows.push(row);
      return;
    }
    row.innerHTML = `<span class="comparison-residue-number">${number}</span><span class="comparison-residue-origin" data-origin></span><select aria-label="Tipo da área ${number}" data-type="${item.id}">${options}</select><small class="comparison-residue-source-classification" data-source-classification></small><button class="btn comparison-residue-delete" type="button" data-remove="${item.id}" aria-label="Remover área ${number}">${iconMarkup("close")}</button>`;
    const origins = [...new Set(item.origins || [item.origin || "MANUAL"])];
    row.querySelector("[data-origin]").textContent = origins.map(originLabel).join(" + ");
    const sourceClasses = (item.source_classifications || [])
      .filter((source) => typeof source.value === "string")
      .map((source) => `${originLabel(source.origin)}: ${source.value}`);
    if (typeof item.source_classification === "string") {
      sourceClasses.push(`${originLabel(item.origin || "MANUAL")}: ${item.source_classification}`);
    }
    const sourceLabel = [...new Set(sourceClasses)].join(" · ");
    const sourceElement = row.querySelector("[data-source-classification]");
    sourceElement.textContent = sourceLabel || (item.candidate === true ? "Candidato identificado" : "");
    sourceElement.hidden = !sourceElement.textContent;
    if (!item.type) {
      const pending = document.createElement("option");
      pending.value = "";
      pending.textContent = "Classificação não mapeada";
      row.querySelector("select").append(pending);
    }
    row.querySelector("select").value = item.type;
    if (item.type === "outro") appendNote(row, item, number);
    rows.push(row);
  });
  layers.replaceChildren(...rows);
}

function originLabel(origin) {
  return ({ MAPEAR: "Mapear", SOMMELIER: "Sommelier", MANUAL: "Manual" })[origin] || "Manual";
}

function appendNote(row, item, number) {
  const input = document.createElement("input"); input.type = "text";
  input.placeholder = "Descreva o defeito...";
  input.setAttribute("aria-label", `Descrição da área ${number}`);
  input.dataset.note = item.id; input.value = item.note || "";
  row.append(input);
}
