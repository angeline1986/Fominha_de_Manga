export const STAGES = [
  ["all", "ALL"], ["ac1", "AC1"], ["ac2", "AC2"], ["ac3", "AC3"],
  ["ac4", "AC4"], ["map", "MAPEAR"], ["retouch", "RETOQUE"],
];
export const RETOUCH = [["degrade", "Degradê"], ["artistic", "Artístico"], ["soft", "Suave"]];

export function matchesStage(row, key, treatments = []) {
  if (key === "all") return true;
  if (key === "retouch") {
    const keys = treatments.length ? treatments : RETOUCH.map(([name]) => name);
    return keys.some((name) => row.retouch?.[name] === true);
  }
  return row.stages?.[key] === true;
}

export function createStageFilters(container, onChange) {
  let active = "all";
  const treatments = new Set();
  const main = document.createElement("div");
  main.className = "auto-merge-filters";
  main.setAttribute("role", "group");
  main.setAttribute("aria-label", "Filtrar por etapa realizada");
  const secondary = document.createElement("div");
  secondary.className = "auto-merge-filters cleaner-retouch-filters";
  secondary.setAttribute("role", "group");
  secondary.setAttribute("aria-label", "Tipos de retoque: seleção múltipla");
  container.replaceChildren(main, secondary);

  function button(label, pressed, action) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = "auto-merge-filter-button";
    element.textContent = label;
    element.classList.toggle("active", pressed);
    element.setAttribute("aria-pressed", String(pressed));
    element.addEventListener("click", action);
    return element;
  }
  return {
    matches: (row) => matchesStage(row, active, [...treatments]),
    reset() { active = "all"; treatments.clear(); },
    draw(rows) {
      main.replaceChildren();
      secondary.replaceChildren();
      for (const [key, label] of STAGES) {
        const count = rows.filter((row) => matchesStage(row, key)).length;
        main.append(button(`${label} (${count})`, active === key, () => {
          active = key; onChange();
        }));
      }
      secondary.hidden = active !== "retouch";
      for (const [key, label] of RETOUCH) {
        secondary.append(button(label, treatments.has(key), () => {
          treatments.has(key) ? treatments.delete(key) : treatments.add(key);
          onChange();
        }));
      }
    },
  };
}
