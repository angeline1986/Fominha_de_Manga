/** Degradê experimental: o clique autoriza componentes elegíveis nas ROIs. */
import { executeDegradeLaboratoryJob } from "/_app/api/laboratorio.js";

export function connectDegrade({ root, button, getRequest, progress }) {
  const panel = root.querySelector('.lab-cards > .lab-image:nth-child(2)');
  const placeholder = panel.querySelector('.lab-placeholder');
  const image = document.createElement('img');
  Object.assign(image, { className: 'lab-original-image',
    alt: 'Prévia experimental Degradê', hidden: true });
  panel.append(image);
  const controllers = new Set();
  let serial = 0;
  let sourceKey = '';

  function setState(state, message, busy = false) {
    placeholder.dataset.state = state;
    placeholder.setAttribute('aria-busy', String(busy));
    placeholder.textContent = message;
    placeholder.hidden = state === 'running';
  }
  function clearResult(message = 'Aguardando execução', state = 'waiting') {
    image.hidden = true;
    image.removeAttribute('src');
    setState(state, message);
  }
  function invalidate() {
    serial++;
    clearResult();
    button.disabled = false;
  }
  function reset(key) {
    if (sourceKey === key) return;
    sourceKey = key;
    invalidate();
  }
  function current(id, snapshot) {
    return id === serial && JSON.stringify(getRequest()) === snapshot;
  }
  function showResult(result, id, snapshot) {
    image.onload = () => {
      if (!current(id, snapshot)) return;
      image.hidden = false;
      setState('completed', 'Concluído');
    };
    image.onerror = () => {
      if (current(id, snapshot)) clearResult('Falha ao abrir a prévia experimental.', 'failed');
    };
    image.src = result.image_url;
  }
  async function run() {
    const payload = getRequest();
    if (!payload) {
      setState('waiting', 'Selecione uma imagem carregada e pelo menos uma área.');
      return;
    }
    const id = ++serial;
    const snapshot = JSON.stringify(payload);
    const active = new AbortController();
    controllers.add(active);
    clearResult('Executando Degradê…', 'running');
    const progressRun = progress?.start('Executando Degradê');
    button.disabled = true;
    try {
      const result = await executeDegradeLaboratoryJob(payload, active.signal, (state) => {
        if (progressRun != null) progress?.update?.(progressRun, state);
      });
      if (current(id, snapshot)) showResult(result, id, snapshot);
    } catch (error) {
      if (current(id, snapshot) && error.name !== 'AbortError') {
        setState('failed', `Degradê não concluído: ${error.message}`);
      }
    } finally {
      progress?.finish(progressRun);
      controllers.delete(active);
      if (id === serial) button.disabled = false;
    }
  }
  button.addEventListener('click', run);
  return { reset, invalidate, dispose() {
    serial++;
    controllers.forEach((controller) => controller.abort());
    button.removeEventListener('click', run);
    image.remove();
  }};
}
