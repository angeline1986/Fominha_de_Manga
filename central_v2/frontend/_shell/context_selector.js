function createField({ id, label, items, value, disabled, onChange }) {
  const field = document.createElement("label");
  field.className = "context-field";
  const caption = document.createElement("span");
  caption.textContent = label;
  const control = document.createElement("div");
  control.className = "context-combobox";
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "context-combobox-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-controls", `${id}-options`);
  trigger.disabled = disabled;
  const current = items.find((item) => item.value === value);
  trigger.textContent = current?.label ?? "Selecionar";

  const list = document.createElement("div");
  list.id = `${id}-options`;
  list.className = "context-combobox-options";
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", label);
  list.hidden = true;
  const options = items.map((item) => {
    const option = document.createElement("div");
    option.className = "context-combobox-option";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", String(item.value === value));
    option.tabIndex = -1;
    option.textContent = item.label;
    option.addEventListener("click", () => {
      onChange(item.value);
      close();
    });
    list.append(option);
    return option;
  });

  function close(restoreFocus = false) {
    list.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) trigger.focus();
  }
  function open() {
    if (trigger.disabled) return;
    list.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    (options.find((option) => option.getAttribute("aria-selected") === "true")
      ?? options[0])?.focus();
  }
  trigger.addEventListener("click", () => list.hidden ? open() : close());
  trigger.addEventListener("keydown", (event) => {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      open();
    }
  });
  list.addEventListener("keydown", (event) => {
    const index = options.indexOf(document.activeElement);
    let next = index;
    if (event.key === "ArrowDown") next = Math.min(index + 1, options.length - 1);
    else if (event.key === "ArrowUp") next = Math.max(index - 1, 0);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = options.length - 1;
    else if (event.key === "Escape") { event.preventDefault(); close(true); return; }
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      options[index]?.click();
      return;
    } else return;
    event.preventDefault();
    options[next]?.focus();
  });

  control.append(trigger, list);
  field.append(caption, control);
  return field;
}

export function createContextSelector(
  context,
  {
    onProviderChange = () => {},
    onMangaChange = () => {},
  } = {},
) {
  const element = document.createElement("div");
  element.className = "context-selector";
  const heading = document.createElement("div");
  heading.className = "context-selector-heading";
  heading.textContent = "CONTEXTO";

  const providers = Object.keys(context.catalog).map((item) => ({ value: item, label: item }));
  const mangas = (context.provider ? context.catalog[context.provider] ?? [] : [])
    .map((item) => ({ value: item, label: item }));
  element.append(
    heading,
    createField({ id: "context-provider", label: "Provider", items: [{ value: "", label: "Selecionar" }, ...providers], value: context.provider, onChange: onProviderChange }),
    createField({ id: "context-manga", label: "Obra", items: [{ value: "", label: "Selecionar" }, ...mangas], value: context.manga, disabled: !context.provider, onChange: onMangaChange }),
  );
  return element;
}
