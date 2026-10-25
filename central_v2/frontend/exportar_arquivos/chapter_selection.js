const LOOSE_FILES = "__avulsos__";

function chapterOf(path) {
  const parts = path.split("/");
  return parts.length > 1 ? parts[0] : LOOSE_FILES;
}

export function chapterCatalog(sources, manualSelection) {
  const filesByKind = {};
  const counts = new Map();
  for (const [kind, files] of Object.entries(sources)) {
    const allowed = Array.isArray(manualSelection[kind])
      ? new Set(manualSelection[kind]) : null;
    filesByKind[kind] = files.map(item => item.path).filter(path => !allowed || allowed.has(path));
    for (const path of filesByKind[kind]) {
      const chapter = chapterOf(path);
      counts.set(chapter, (counts.get(chapter) || 0) + 1);
    }
  }
  const chapters = [...counts].sort(([a], [b]) =>
    a.localeCompare(b, "pt-BR", { numeric: true }));
  return { filesByKind, chapters };
}

export function filesForChapters(catalog, selected) {
  const result = {};
  for (const [kind, files] of Object.entries(catalog.filesByKind)) {
    result[kind] = files.filter(path => selected.has(chapterOf(path)));
  }
  return result;
}

export function createChapterSelection(container, onChange) {
  const heading = document.createElement("strong");
  heading.textContent = "Capítulos para exportar";
  const hint = document.createElement("small");
  hint.textContent = "Marque os capítulos que serão incluídos na exportação.";
  const list = document.createElement("div");
  list.className = "export-chapter-list";
  const actions = document.createElement("div");
  actions.className = "export-chapter-actions";
  const selectAll = document.createElement("button");
  selectAll.type = "button";
  selectAll.className = "export-chapter-action";
  selectAll.textContent = "Selecionar todos";
  const clearAll = document.createElement("button");
  clearAll.type = "button";
  clearAll.className = "export-chapter-action";
  clearAll.textContent = "Desmarcar todos";
  actions.append(selectAll, clearAll);
  const count = document.createElement("small");
  container.append(heading, hint, actions, list, count);
  let catalog = null;
  let selected = new Set();

  function updateCount() {
    count.textContent = catalog
      ? `${selected.size} de ${catalog.chapters.length} capítulos selecionados`
      : "Aguardando simulação";
  }

  function setBusy(busy) {
    list.querySelectorAll("input").forEach(box => { box.disabled = busy; });
    selectAll.disabled = busy || !catalog;
    clearAll.disabled = busy || !catalog;
  }

  function selectAllChapters(checked) {
    selected = new Set(checked ? catalog.chapters.map(([chapter]) => chapter) : []);
    list.querySelectorAll("input").forEach(box => { box.checked = checked; });
    updateCount();
    onChange();
  }
  selectAll.addEventListener("click", () => selectAllChapters(true));
  clearAll.addEventListener("click", () => selectAllChapters(false));

  function show(next, preserve = false) {
    const previous = selected;
    catalog = next;
    selected = new Set(next.chapters.map(([chapter]) => chapter)
      .filter(chapter => !preserve || previous.has(chapter)));
    list.replaceChildren();
    for (const [chapter, total] of next.chapters) {
      const label = document.createElement("label");
      label.className = "export-chapter-row";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = selected.has(chapter);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) selected.add(chapter);
        else selected.delete(chapter);
        updateCount();
        onChange();
      });
      const name = document.createElement("span");
      name.textContent = chapter === LOOSE_FILES ? "Arquivos avulsos" : `Cap. ${chapter}`;
      const amount = document.createElement("small");
      amount.textContent = `${total} arq.`;
      label.append(checkbox, name, amount);
      list.append(label);
    }
    updateCount();
    setBusy(false);
  }

  function clear() {
    catalog = null;
    selected.clear();
    const placeholder = document.createElement("span");
    placeholder.className = "export-chapter-placeholder";
    placeholder.textContent = "Simule a exportação para escolher capítulos.";
    list.replaceChildren(placeholder);
    updateCount();
    setBusy(false);
  }

  clear();

  return {
    show, clear,
    hasChapters: () => !!catalog?.chapters.length,
    hasSelection: () => selected.size > 0,
    fileSelection: () => filesForChapters(catalog, selected),
    setBusy,
  };
}
