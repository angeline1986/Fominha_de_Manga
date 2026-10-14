const providers = [['comix', 'Comix'], ['mangago', 'Mangago'], ['ridi', 'Ridi'], ['lezhinus', 'Lezhinus']];

async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);
  return data;
}

export function render(container) {
  const root = document.createElement('section');
  root.className = 'saved-works-page';
  root.innerHTML = `<header><h1>Obras para Download</h1><p>Gerencie os nomes e links utilizados pelo downloader.</p></header>
    <div class="sw-panel"><div class="sw-toolbar"><label><span>Provider</span><select data-provider></select></label>
    <label class="sw-search"><span class="sw-sr">Buscar obra</span><input data-search type="search" placeholder="Buscar obra ou link"></label>
    <button class="sw-primary" type="button" data-new>+ Nova obra</button></div>
    <div class="sw-table-wrap"><table><thead><tr><th>Obra</th><th>Link</th><th>Ações</th></tr></thead><tbody data-rows></tbody></table></div>
    <p class="sw-empty" data-empty hidden>Nenhuma obra encontrada.</p><div class="sw-summary" data-summary></div></div>
    <dialog class="sw-dialog" data-dialog><form method="dialog" data-form><h2 data-form-title>Adicionar obra</h2>
      <label>Nome da obra<input name="name" maxlength="240" required placeholder="Ex.: Minha nova obra"></label>
      <label>URL da obra<input name="url" type="url" maxlength="2048" required placeholder="https://..."></label>
      <p class="sw-error" data-error role="alert"></p><div class="sw-actions"><button value="cancel" data-cancel>Cancelar</button><button class="sw-primary" type="submit" value="save" data-save>Salvar</button></div></form></dialog>
    <p class="sw-toast" data-status role="status" aria-live="polite"></p>`;
  container.replaceChildren(root);
  const css = document.createElement('link'); css.rel = 'stylesheet';
  css.href = '/exportar_arquivos/saved_works/style.css'; document.head.append(css);
  const provider = root.querySelector('[data-provider]');
  providers.forEach(([value, label]) => provider.add(new Option(label, value)));
  const search = root.querySelector('[data-search]');
  const rows = root.querySelector('[data-rows]');
  const dialog = root.querySelector('[data-dialog]');
  const form = root.querySelector('[data-form]');
  const status = root.querySelector('[data-status]');
  const error = root.querySelector('[data-error]');
  let works = [], editing = null, disposed = false, revision = 0;
  const show = (message) => { status.textContent = message; };
  function renderRows() {
    rows.replaceChildren();
    const term = search.value.trim().toLocaleLowerCase('pt-BR');
    const filtered = works.filter((w) => `${w.name} ${w.url}`.toLocaleLowerCase('pt-BR').includes(term));
    root.querySelector('[data-summary]').textContent = `${works.length} obra(s) cadastrada(s) · ${filtered.length} exibida(s)`;
    root.querySelector('[data-empty]').hidden = filtered.length > 0;
    for (const work of filtered) {
      const tr = document.createElement('tr');
      const title = document.createElement('td'); title.textContent = work.name;
      const linkCell = document.createElement('td'); const link = document.createElement('a');
      link.href = work.url; link.textContent = work.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      linkCell.append(link);
      const actions = document.createElement('td'); actions.className = 'sw-row-actions';
      const iconButton = (label, paths, className) => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = `sw-icon-action ${className}`;
        button.setAttribute('aria-label', `${label} ${work.name}`);
        button.title = `${label} ${work.name}`;
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '1.8');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        for (const d of paths) {
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('d', d); svg.append(path);
        }
        button.append(svg); return button;
      };
      const edit = iconButton('Editar', ['M12 20h9', 'M16.5 3.5a2.12 2.12 0 0 1 3 3L9 17l-4 1 1-4Z'], 'sw-edit');
      edit.addEventListener('click', () => openForm(work));
      const remove = iconButton('Excluir', ['M3 6h18', 'M8 6V4h8v2', 'M19 6l-1 14H6L5 6', 'M10 10v7', 'M14 10v7'], 'sw-delete');
      remove.addEventListener('click', () => removeWork(work));
      actions.append(edit, remove); tr.append(title, linkCell, actions); rows.append(tr);
    }
  }
  async function load() {
    const id = ++revision; show('Carregando catálogo…');
    try {
      const result = await request(`/api/export/saved-works?provider=${encodeURIComponent(provider.value)}`);
      if (disposed || id !== revision) return;
      works = result.works; renderRows(); show('');
    } catch (cause) { if (!disposed && id === revision) show(cause.message); }
  }
  function openForm(work = null) {
    editing = work; form.reset(); error.textContent = '';
    root.querySelector('[data-form-title]').textContent = work ? 'Editar obra' : 'Adicionar obra';
    if (work) { form.elements.name.value = work.name; form.elements.url.value = work.url; }
    dialog.showModal();
  }
  async function change(payload) {
    const result = await request('/api/export/saved-works', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
    });
    if (disposed) return;
    works = result.works; renderRows(); show('Catálogo atualizado.');
  }
  async function removeWork(work) {
    if (!confirm(`Excluir "${work.name}" da lista de ${provider.value}?`)) return;
    try { await change({provider: provider.value, action: 'delete', original_url: work.url}); }
    catch (cause) { show(cause.message); }
  }
  const onSubmit = async (event) => {
    if (event.submitter?.value === 'cancel') return;
    event.preventDefault(); error.textContent = '';
    const save = root.querySelector('[data-save]'); save.disabled = true;
    try {
      await change({provider: provider.value, action: editing ? 'edit' : 'add',
        original_url: editing?.url, name: form.elements.name.value, url: form.elements.url.value});
      dialog.close();
    } catch (cause) { error.textContent = cause.message; }
    finally { save.disabled = false; }
  };
  form.addEventListener('submit', onSubmit);
  root.querySelector('[data-new]').addEventListener('click', () => openForm());
  provider.addEventListener('change', load);
  search.addEventListener('input', renderRows);
  load();
  return () => { disposed = true; revision++; css.remove(); root.remove(); };
}
