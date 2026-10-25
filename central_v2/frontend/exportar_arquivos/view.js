import { getContext, subscribeContext } from "/_app/state/context.js";
import { KINDS, mb, invalidate, api, post } from "/exportar_arquivos/state.js";
import { confirmMessage, showMessage } from "/_shared/messages/messages.js";
import { createDirectoryBrowser } from "/exportar_arquivos/browser.js";
import { createFilePicker } from "/exportar_arquivos/file_picker.js";
import { chapterCatalog, createChapterSelection } from "/exportar_arquivos/chapter_selection.js";

export function createExportView(container) {
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = "/exportar_arquivos/style.css";
  document.head.append(style);
  const root = document.createElement("section");
  root.className = "export-v2";
  root.innerHTML = `
    <div class="export-heading"><h1>Simular e Exportar</h1><span tabindex="0" role="note" title="Simule e revise os arquivos antes de exportar. Conflitos impedem a cópia.">ⓘ</span></div>
    <div class="export-split">
      <section class="export-config" aria-label="Configuração de exportação">
        <header class="export-title-row"><strong>Configuração</strong><span data-manga class="export-manga">Selecione uma obra</span></header>
        <div class="export-field"><label for="export-dest">Diretório pai de destino</label>
          <div class="export-path-row"><input id="export-dest" data-dest readonly placeholder="Escolha uma pasta de destino" title="Caminho do destino" />
          <button type="button" data-browse class="export-secondary export-icon-button" aria-label="Explorar pastas" title="Explorar pastas"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg></button></div>
          <small>A pasta da obra será criada automaticamente dentro do destino escolhido.</small>
        </div>
        <fieldset class="export-contents"><legend>Conteúdo para exportar</legend>
          ${KINDS.map(k => `<label class="export-content"><input type="checkbox" data-kind="${k.key}" checked />
            <span class="export-content-body"><strong>${k.label}</strong><small>Destino: <code>${k.dest}/</code></small>
              <span class="export-item-count" data-count="${k.key}">Todos</span></span>
            <button type="button" class="export-secondary export-icon-button" data-pick="${k.key}" title="Escolher arquivos" aria-label="Escolher arquivos de ${k.label}"><svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg></button></label>`).join("")}
        </fieldset>
        <div class="export-exclusions"><strong>Exclusões automáticas</strong><div><code>*_mask.png</code><code>*.json</code><code>.DS_Store</code></div></div>
        <footer class="export-actions"><span data-available>2 origens disponíveis para seleção</span>
          <button type="button" class="export-primary" data-simulate>Simular exportação</button></footer>
      </section>
      <aside class="export-inspector" aria-label="Inspeção da exportação">
        <header><strong>Inspeção da exportação</strong><span data-total>Sem simulação</span></header>
        <div class="export-tree" data-tree></div>
        <section class="export-chapters" data-chapters></section>
        <div class="export-summary" data-summary></div>
        <div class="export-state" data-state role="status" aria-live="polite">Escolha um destino e simule para conferir arquivos e conflitos.</div>
        <button type="button" class="export-primary export-execute" data-execute disabled>Exportar arquivos</button>
      </aside>
    </div>
  `;
  container.replaceChildren(root);
  const browser = createDirectoryBrowser(root, path => { state.destination = path; changed(); });
  const $ = q => root.querySelector(q);
  const state = { destination: "", plan: null, result: null, busy: false, disposed: false,
    fileSelection: {}, sourceFiles: null, requestId: 0 };
  const chapters = createChapterSelection($("[data-chapters]"), () => simulate(false));
  const picker = createFilePicker(root, (kind, selection) => {
    state.fileSelection[kind] = selection; changed();
  });
  const kinds = () => [...root.querySelectorAll("[data-kind]:checked")].map(el => el.dataset.kind);
  const status = message => { $("[data-state]").textContent = message; };
  function displayDestination(path) {
    if (!path) return { name: "", description: "Escolha uma pasta de destino" };
    const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
    const name = parts.at(-1) || "";
    const isDefault = parts.slice(-3).join("/") === "03_Novel/01_MANGA/Staff_Berry" &&
      parts.some(part => part === "Meu Drive" || part === "My Drive" || part.startsWith("GoogleDrive-"));
    const description = isDefault ? "Meu Drive/03_Novel/01_MANGA/Staff_Berry" : parts.slice(-3).join("/");
    return { name, description };
  }
  function render() {
    const ctx = getContext();
    $("[data-manga]").textContent = ctx.manga || "Selecione uma obra";
    const destination = displayDestination(state.destination);
    $("[data-dest]").value = destination.name ? `📁  ${destination.name}` : "";
    $("[data-dest]").title = destination.description;
    $("[data-dest]").setAttribute("aria-label", `Destino: ${destination.description}`);
    const selected = kinds();
    const plan = state.plan;
    const summary = plan?.summary || {};
    for (const kind of KINDS) {
      const s = summary[kind.key];
      const chosen = state.fileSelection[kind.key];
      $(`[data-count="${kind.key}"]`).textContent = s ? `${s.files} arq · ${mb(s.bytes)}` :
        chosen ? `${chosen.length} selecionado(s)` : "Todos";
    }
    const tree = $("[data-tree]"); tree.replaceChildren();
    const rootNode = document.createElement("strong"); rootNode.textContent = `${ctx.manga || "Obra"}/`; tree.append(rootNode);
    for (const k of KINDS.filter(k => selected.includes(k.key))) {
      const row = document.createElement("div"); row.className = "export-tree-row";
      const name = document.createElement("span"); name.textContent = `└── ${k.dest}/`;
      const count = document.createElement("span"); count.textContent = summary[k.key] ? `${summary[k.key].files} arquivos` : "Aguardando simulação";
      row.append(name, count); tree.append(row);
    }
    if (!selected.length) { const blank = document.createElement("small"); blank.textContent = "Nenhum conteúdo selecionado."; tree.append(blank); }
    $("[data-total]").textContent = plan ? `${plan.total_files} arq · ${mb(plan.total_bytes)}` : "Sem simulação";
    const metrics = $("[data-summary]"); metrics.replaceChildren();
    for (const [title, count] of [["Novos", plan?.new_files], ["Idênticos", plan?.identical_files], ["Conflitos", plan?.conflicts]]) {
      const cell = document.createElement("div"); const value = document.createElement("strong");
      value.textContent = count == null ? "—" : String(count);
      const label = document.createElement("span"); label.textContent = title;
      cell.append(value, label); metrics.append(cell);
    }
    $("[data-simulate]").disabled = state.busy || !ctx.manga || !state.destination || !selected.length;
    $("[data-browse]").disabled = state.busy;
    root.querySelectorAll("[data-kind]").forEach(box => { box.disabled = state.busy; });
    root.querySelectorAll("[data-pick]").forEach(button => { button.disabled = state.busy || !ctx.manga; });
    chapters.setBusy(state.busy);
    $("[data-execute]").disabled = state.busy || !plan?.can_export || !plan.plan_id;
    $("[data-available]").textContent = `${selected.length} conteúdo(s) selecionado(s)`;
  }
  function changed() {
    state.requestId++; state.busy = false; state.sourceFiles = null; chapters.clear(); invalidate(state);
    status("Configuração alterada. Simule novamente antes de exportar."); render();
  }
  function lockControls() {
    root.querySelectorAll("[data-kind], [data-pick], [data-simulate], [data-browse], [data-execute]")
      .forEach(control => { control.disabled = true; });
    chapters.setBusy(true);
  }
  root.querySelectorAll("[data-kind]").forEach(box => box.addEventListener("change", changed));
  const unsubscribe = subscribeContext(() => { state.fileSelection = {}; picker.close(); changed(); });
  root.querySelectorAll("[data-pick]").forEach(button => button.addEventListener("click", () => {
    const {provider,manga} = getContext();
    picker.open(provider,manga,button.dataset.pick,state.fileSelection[button.dataset.pick]);
  }));
  $("[data-browse]").addEventListener("click", () => browser.open(state.destination));
  async function simulate(refreshSources = true) {
    const { provider, manga } = getContext(); const selected = kinds();
    const requestId = ++state.requestId;
    const hasPreview = !!state.plan;
    state.busy = true; invalidate(state); status("Simulando exportação e conferindo os arquivos…");
    if (hasPreview) lockControls(); else render();
    try {
      if (refreshSources || !state.sourceFiles) {
        const rows = await Promise.all(selected.map(kind =>
          post("/api/export/files", { provider, manga, kind })));
        if (requestId !== state.requestId || state.disposed) return;
        const preserve = !!state.sourceFiles;
        state.sourceFiles = Object.fromEntries(rows.map((row, index) => [selected[index], row.files]));
        chapters.show(chapterCatalog(state.sourceFiles, state.fileSelection), preserve);
        chapters.setBusy(true);
      }
      if (!chapters.hasSelection()) {
        status(!chapters.hasChapters() ? "Nenhum arquivo elegível encontrado." :
          "Selecione pelo menos um capítulo para exportar.");
        return;
      }
      const plan = await post("/api/export/simulate", { provider, manga, destination: state.destination,
        contents: selected, file_selection: chapters.fileSelection() });
      if (requestId !== state.requestId || state.disposed) return;
      state.plan = plan;
      status(state.plan.conflicts ? `${state.plan.conflicts} conflito(s). A exportação está bloqueada.` :
        state.plan.can_export ? `${state.plan.new_files} arquivo(s) novo(s). Pronto para exportar.` : "Arquivos já exportados. Nenhuma cópia necessária.");
    } catch (e) { if (requestId === state.requestId) status(`Falha na simulação: ${e.message}`); }
    finally { if (requestId === state.requestId && !state.disposed) { state.busy = false; render(); } }
  }
  $("[data-simulate]").addEventListener("click", () => simulate());
  async function confirmExport() {
    return confirmMessage({ title: "Confirmar exportação",
      message: `Copiar ${state.plan?.new_files || 0} arquivo(s) para a pasta da obra? Arquivos existentes serão preservados.`,
      confirmText: "Exportar arquivos" });
  }
  $("[data-execute]").addEventListener("click", async () => {
    if (!state.plan?.can_export || state.busy || !await confirmExport()) return;
    const { provider, manga } = getContext(); const plan_id = state.plan.plan_id;
    state.busy = true; status("Exportando arquivos…"); render();
    try { const r = await post("/api/export/execute", { provider, manga, plan_id });
      invalidate(state); status(`Exportação concluída: ${r.copied} arquivo(s) copiado(s), ${r.unchanged} preservado(s).`);
      await showMessage({ title: "Exportação concluída", message: `${r.copied} arquivo(s) copiado(s), ${r.unchanged} preservado(s).` });
    } catch (e) { invalidate(state); status(`Falha na exportação: ${e.message}. Simule novamente.`); }
    finally { state.busy = false; render(); }
  });
  // Resolves the mounted Google Drive path; never submit the display alias to the exporter.
  const defaultRequest = new AbortController();
  async function loadDefaultDestination() {
    try {
      const result = await api("/api/export/default-destination", { signal: defaultRequest.signal });
      if (state.disposed || state.destination) return;
      if (result.available && result.path) {
        state.destination = result.path;
        status("Destino padrão selecionado. Simule antes de exportar.");
      } else {
        status(result.warning || "Destino padrão indisponível. Escolha outra pasta.");
      }
      render();
    } catch (error) {
      if (!state.disposed && error.name !== "AbortError") {
        status(`Destino padrão indisponível: ${error.message}. Escolha uma pasta.`);
      }
    }
  }
  loadDefaultDestination();
  render();
  return () => { defaultRequest.abort(); state.disposed = true; state.requestId++;
    unsubscribe(); browser.dispose(); picker.dispose(); style.remove(); root.remove(); };
}
