/** Laboratório L3: Degradê experimental, sem promoção de artefatos. */
export function connectDegrade({ root, button, getRequest }) {
  const panel = root.querySelector('.lab-cards > .lab-image:nth-child(2)');
  const placeholder = panel.querySelector('.lab-placeholder');
  const image = document.createElement('img');
  image.className = 'lab-original-image';
  image.alt = 'Prévia experimental Degradê';
  image.hidden = true;
  panel.append(image);
  const note = root.querySelector('[data-lab-degrade-status]');
  const progress = document.createElement('progress');
  progress.className = 'lab-degrade-progress';
  progress.setAttribute('aria-label', 'Tratamento Degradê em execução');
  progress.hidden = true;
  note.after(progress);
  let controller = null;
  let serial = 0;
  let sourceKey = '';
  function reset(key) {
    if (sourceKey === key) return;
    sourceKey = key;
    serial++;
    controller?.abort();
    controller = null;
    image.hidden = true;
    image.removeAttribute('src');
    placeholder.hidden = false;
    placeholder.textContent = 'Aguardando execução';
    note.textContent = 'Selecione uma página e pelo menos uma área.';
    progress.hidden = true;
    button.disabled = false;
  }
  async function run() {
    const payload = getRequest();
    if (!payload) {
      note.textContent = 'Selecione uma imagem carregada e pelo menos uma área.';
      return;
    }
    const id = ++serial;
    controller = new AbortController();
    button.disabled = true;
    image.hidden = true;
    image.removeAttribute('src');
    placeholder.hidden = false;
    placeholder.textContent = 'Processando Degradê...';
    note.textContent = 'Processamento em andamento (progresso indeterminado).';
    progress.hidden = false;
    try {
      const response = await fetch('/api/textoff/laboratorio/degrade/execute', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload), signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      if (id !== serial) return;
      image.onload = () => {
        if (id !== serial) return;
        image.hidden = false;
        placeholder.hidden = true;
        note.textContent = 'Prévia experimental pronta. Nenhum arquivo oficial foi alterado.';
      };
      image.onerror = () => {
        if (id !== serial) return;
        image.hidden = true;
        placeholder.hidden = false;
        placeholder.textContent = 'Falha ao abrir a prévia experimental.';
      };
      image.src = result.image_url;
    } catch (error) {
      if (id === serial && error.name !== 'AbortError') {
        placeholder.textContent = `Degradê não concluído: ${error.message}`;
        note.textContent = 'Consulte os registros do experimento.';
      }
    } finally {
      if (id === serial) { button.disabled = false; progress.hidden = true; }
    }
  }
  button.addEventListener('click', run);
  return {reset, dispose() {serial++; controller?.abort(); button.removeEventListener('click', run); image.remove(); progress.remove();}};
}
