import { KINDS, post } from "/exportar_arquivos/state.js";

// Navegador virtual: a API devolve somente arquivos elegíveis sob a origem da obra.
// Pastas são derivadas desses caminhos e nunca acessam diretórios arbitrários.
export function createFilePicker(root, onSelect) {
  const dialog = document.createElement("dialog");
  dialog.className = "export-browser export-file-picker";
  dialog.setAttribute("aria-label", "Arquivos da obra");
  dialog.innerHTML = `
    <header class="export-browser-head">
      <h2>Arquivos da obra</h2>
      <button type="button" class="export-browser-close" data-close aria-label="Fechar">×</button>
    </header>
    <div class="export-browser-body">
      <div class="export-browser-breadcrumb" data-path></div>
      <div class="export-browser-list export-explorer-list" data-list></div>
      <div class="export-picker-tools">
        <button type="button" data-all>Selecionar todos</button>
        <button type="button" data-none>Desmarcar todos</button>
        <span data-count></span>
      </div>
      <div class="export-browser-info" data-info role="status" aria-live="polite"></div>
    </div>
    <footer class="export-browser-foot">
      <button type="button" class="export-browser-close" data-cancel>Cancelar</button>
      <button type="button" class="export-browser-confirm" data-save>Aplicar seleção</button>
    </footer>`;
  root.append(dialog);
  const $ = q => dialog.querySelector(q);
  let serial = 0, kind = "", source = "", work = "", current = "", files = [];
  let selected = new Set(), allMode = true, loaded = false;

  const isWithin = (path, dir) => !dir || path.startsWith(`${dir}/`);
  const immediateName = (path, dir) => dir ? path.slice(dir.length + 1).split("/")[0] : path.split("/")[0];
  const isDirectFile = (path, dir) => isWithin(path, dir) && !path.slice(dir ? dir.length + 1 : 0).includes("/");
  function update() {
    $("[data-count]").textContent = `${selected.size} de ${files.length} selecionado(s)`;
    $("[data-save]").disabled = !loaded || selected.size === 0;
    $("[data-all]").disabled = !loaded || !files.length;
    $("[data-none]").disabled = !loaded || !files.length;
  }
  function row(text, type, action, checked = false) {
    const element = document.createElement(type === "file" ? "label" : "button");
    element.className = "export-explorer-entry";
    if (type !== "file") element.type = "button";
    if (type === "file") {
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = checked;
      cb.addEventListener("change", () => action(cb.checked));
      const name = document.createElement("span");
      name.textContent = text;
      element.append(cb, name);
    } else {
      element.textContent = text;
      element.addEventListener("click", action);
    }
    return element;
  }
  function browse(path = "") {
    current = path;
    $("[data-path]").textContent = `${work}/${source}${path ? `/${path}` : ""}`;
    const list = $("[data-list]");
    list.replaceChildren();
    if (path) list.append(row("← Pasta anterior", "dir", () => browse(path.split("/").slice(0, -1).join("/"))));
    const directories = new Set();
    const immediateFiles = [];
    for (const item of files) {
      if (!isWithin(item.path, path)) continue;
      const remainder = path ? item.path.slice(path.length + 1) : item.path;
      if (remainder.includes("/")) directories.add(immediateName(item.path, path));
      else immediateFiles.push(item.path);
    }
    for (const name of [...directories].sort((a,b) => a.localeCompare(b, "pt-BR", {numeric:true}))) {
      const next = path ? `${path}/${name}` : name;
      list.append(row(`📁  ${name}`, "dir", () => browse(next)));
    }
    for (const pathName of immediateFiles) {
      list.append(row(pathName.split("/").at(-1), "file", checked => {
        if (checked) selected.add(pathName); else selected.delete(pathName);
        allMode = selected.size === files.length;
        update();
      }, selected.has(pathName)));
    }
    if (!directories.size && !immediateFiles.length) {
      const empty = document.createElement("span");
      empty.className = "export-explorer-empty";
      empty.textContent = "Nenhum arquivo elegível nesta pasta.";
      list.append(empty);
    }
    update();
  }
  function close() { serial++; if (dialog.open) dialog.close(); }
  async function open(provider, manga, nextKind, previous) {
    close();
    kind = nextKind;
    source = KINDS.find(item => item.key === kind)?.label || kind;
    work = `${provider}/${manga}`;
    current = "";
    files = []; loaded = false; selected = new Set();
    allMode = previous == null;
    const id = ++serial;
    $("[data-list]").textContent = "Carregando arquivos…";
    $("[data-path]").textContent = `${work}/${source}`;
    $("[data-info]").textContent = "";
    update();
    dialog.showModal();
    try {
      const data = await post("/api/export/files", {provider, manga, kind});
      if (id !== serial || !dialog.open) return;
      if (typeof data.source === "string" && data.source) source = data.source;
      files = Array.isArray(data.files) ? data.files : [];
      if (files.length > 10000) throw new Error("Quantidade excessiva de arquivos.");
      if (!files.every(f => typeof f.path === "string" && f.path && !f.path.startsWith("/") &&
        !f.path.includes("\\") && f.path.split("/").every(p => p && p !== "." && p !== ".."))) {
        throw new Error("A listagem retornou caminhos inválidos.");
      }
      const available = new Set(files.map(f => f.path));
      selected = allMode ? new Set(available) : new Set((previous || []).filter(p => available.has(p)));
      loaded = true;
      $("[data-info]").textContent = files.length
        ? "Navegue pelas pastas e marque os arquivos desejados."
        : "Nenhum arquivo elegível encontrado.";
      browse("");
    } catch (error) {
      if (id === serial) {
        $("[data-list]").replaceChildren();
        $("[data-info]").textContent = `Não foi possível carregar: ${error.message}`;
      }
    }
  }
  $("[data-close]").addEventListener("click", close);
  $("[data-cancel]").addEventListener("click", close);
  $("[data-all]").addEventListener("click", () => {
    selected = new Set(files.map(f => f.path)); allMode = true; browse(current);
  });
  $("[data-none]").addEventListener("click", () => {
    selected.clear(); allMode = false; browse(current);
  });
  $("[data-save]").addEventListener("click", () => {
    if (!loaded || !selected.size) return;
    onSelect(kind, selected.size === files.length ? null : [...selected].sort());
    close();
  });
  return {open, close, dispose() {close(); dialog.remove();}};
}
