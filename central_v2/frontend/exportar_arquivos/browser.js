import { api } from "/exportar_arquivos/state.js";

export function createDirectoryBrowser(root, onSelect) {
  const dialog = document.createElement("dialog");
  dialog.className = "export-browser";
  dialog.setAttribute("aria-label", "Explorador de pastas");
  dialog.innerHTML = `
    <header class="export-browser-head"><h2>Escolher pasta de destino</h2>
      <button type="button" data-close class="export-browser-close" aria-label="Fechar">✕</button></header>
    <div class="export-browser-body">
      <div class="export-browser-breadcrumb" data-path></div>
      <div class="export-browser-list" data-list role="list"></div>
      <div class="export-browser-info" data-info role="status" aria-live="polite"></div>
    </div>
    <footer class="export-browser-foot"><button type="button" class="export-browser-up" data-up>↑ Voltar</button>
      <button type="button" class="export-browser-close" data-cancel>Cancelar</button>
      <button type="button" class="export-browser-confirm" data-select>Selecionar esta pasta</button></footer>`;
  root.append(dialog);
  const $ = q => dialog.querySelector(q);
  let current = "", request = 0;
  async function navigate(path) {
    const id = ++request;
    $("[data-info]").textContent = "Carregando pastas…";
    $("[data-list]").replaceChildren();
    $("[data-select]").disabled = true;
    try {
      const params = new URLSearchParams(path ? { path } : {});
      const data = await api(`/api/export/browse?${params}`);
      if (id !== request || !dialog.open) return;
      current = data.path;
      $("[data-path]").textContent = data.display;
      $("[data-up]").disabled = !data.parent;
      $("[data-up]").dataset.path = data.parent || "";
      $("[data-select]").disabled = !data.writable;
      $("[data-info]").textContent = data.writable ? "Pasta acessível para exportação" : "Pasta sem permissão de gravação";
      for (const folder of data.directories) {
        const row = document.createElement("button");
        row.type = "button";
        row.textContent = `📁  ${folder.name}`;
        row.addEventListener("click", () => navigate(folder.path));
        $("[data-list]").append(row);
      }
      if (!data.directories.length) $("[data-list]").textContent = "Nenhuma subpasta disponível.";
    } catch (e) { if (id === request) $("[data-info]").textContent = `Não foi possível listar a pasta: ${e.message}`; }
  }
  const close = () => { request++; dialog.close(); };
  $("[data-close]").addEventListener("click", close);
  $("[data-cancel]").addEventListener("click", close);
  $("[data-up]").addEventListener("click", () => navigate($("[data-up]").dataset.path));
  $("[data-select]").addEventListener("click", () => { if (current) { onSelect(current); close(); } });
  dialog.addEventListener("close", () => { request++; });
  return { open(initial) { dialog.showModal(); navigate(initial); }, dispose() { request++; if (dialog.open) dialog.close(); dialog.remove(); } };
}
