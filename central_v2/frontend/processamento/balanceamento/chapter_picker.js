export function createChapterPicker(onChange) {
  const element = document.createElement("div");
  element.className = "balance-chapter-picker";
  const trigger = document.createElement("button");
  trigger.className = "balance-chapter-trigger";
  trigger.type = "button";
  trigger.setAttribute("aria-label", "Selecionar capítulo");
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-controls", "balance-chapter-options");
  const value = document.createElement("span");
  const options = document.createElement("div");
  options.id = "balance-chapter-options";
  options.className = "balance-chapter-options";
  options.setAttribute("role", "listbox");
  options.setAttribute("aria-label", "Capítulo");
  options.hidden = true;
  trigger.append(value);
  element.append(trigger, options);

  let items = [];
  let selected = "";
  function close(restoreFocus = false) {
    options.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) trigger.focus();
  }
  function open() {
    if (!items.length) return;
    options.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    (items.find((item) => item.value === selected) || items[0]).element.focus();
  }
  function update(chapters, chapter) {
    selected = chapter == null ? "" : String(chapter);
    items = chapters.map((row) => {
      const option = document.createElement("button");
      option.className = "balance-chapter-option";
      option.type = "button";
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(String(row.chapter) === selected));
      const label = document.createElement("span");
      label.textContent = `Cap. ${row.chapter}`;
      option.append(label);
      if (row.issues?.length) {
        option.classList.add("has-deviations");
        option.setAttribute("aria-label", `Capítulo ${row.chapter}, com desvios mapeados`);
        const indicator = document.createElement("span");
        indicator.className = "balance-chapter-option-dot";
        indicator.setAttribute("aria-hidden", "true");
        option.append(indicator);
      }
      const item = { value: String(row.chapter), element: option };
      option.addEventListener("click", () => { close(); onChange(item.value); });
      return item;
    });
    options.replaceChildren(...items.map((item) => item.element));
    value.textContent = selected ? `Cap. ${selected}` : "Capítulo";
    trigger.disabled = !items.length;
    trigger.setAttribute("aria-label", selected ? `Capítulo ${selected}` : "Selecionar capítulo");
  }
  trigger.addEventListener("click", () => options.hidden ? open() : close());
  trigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); open(); }
  });
  options.addEventListener("keydown", (event) => {
    const index = items.findIndex((item) => item.element === document.activeElement);
    let next = index;
    if (event.key === "ArrowDown") next = Math.min(index + 1, items.length - 1);
    else if (event.key === "ArrowUp") next = Math.max(index - 1, 0);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else if (event.key === "Escape") { event.preventDefault(); close(true); return; }
    else return;
    event.preventDefault();
    items[next]?.element.focus();
  });
  function onOutsidePointer(event) {
    if (!element.contains(event.target)) close();
  }
  document.addEventListener("pointerdown", onOutsidePointer);
  return { element, update, dispose() { close(); document.removeEventListener("pointerdown", onOutsidePointer); } };
}
