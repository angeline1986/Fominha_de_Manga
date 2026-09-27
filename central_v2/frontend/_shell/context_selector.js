function options(items, selectedValue) {
  return items
    .map((item) => {
      const selected = item === selectedValue ? " selected" : "";
      return `<option value="${escapeAttribute(item)}"${selected}>${escapeHtml(item)}</option>`;
    })
    .join("");
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = value;
  return element.innerHTML;
}

function escapeAttribute(value) {
  return escapeHtml(value);
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

  const providers = Object.keys(context.catalog);
  const mangas = context.provider
    ? context.catalog[context.provider] ?? []
    : [];

  element.innerHTML = `
    <div class="context-selector-heading">CONTEXTO</div>

    <label>
      <span>Provider</span>
      <select data-context-provider>
        <option value="">Selecionar</option>
        ${options(providers, context.provider)}
      </select>
    </label>

    <label>
      <span>Obra</span>
      <select
        data-context-manga
        ${context.provider ? "" : "disabled"}
      >
        <option value="">Selecionar</option>
        ${options(mangas, context.manga)}
      </select>
    </label>
  `;

  const providerSelect = element.querySelector("[data-context-provider]");
  const mangaSelect = element.querySelector("[data-context-manga]");

  providerSelect.addEventListener("change", () => {
    onProviderChange(providerSelect.value);
  });

  mangaSelect.addEventListener("change", () => {
    onMangaChange(mangaSelect.value);
  });

  return element;
}
