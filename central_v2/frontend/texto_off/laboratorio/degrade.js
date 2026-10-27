/** Degradê experimental: o clique autoriza componentes elegíveis nas ROIs. */
import { executeDegradeLaboratoryJob } from "/_app/api/laboratorio.js";

export function connectDegrade({ root, button, getRequest, progress, review, order }) {
  const panel = root.querySelector('[data-lab-card="degrade"]')
    || root.querySelector('.lab-cards > .lab-image:nth-child(2)');
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
    review?.clear('degrade');
    order?.clear('degrade');
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
      review?.ready('degrade', getRequest(), result.run_id);
      order?.complete('degrade');
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
    review?.clear('degrade');
    order?.clear('degrade');
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
  function restore(result, identity, expectedSerial) {
    if (serial !== expectedSerial || !result?.run_id || !result.image_url
        || result.treatment !== 'degrade') return false;
    const id = ++serial;
    image.onload = () => {
      if (id !== serial) return;
      image.hidden = false;
      setState('completed', 'Resultado recuperado');
      review?.ready('degrade', identity, result.run_id);
      order?.complete('degrade', result.completed_at);
    };
    image.onerror = () => {
      if (id === serial) clearResult('Não foi possível reabrir o resultado salvo.', 'failed');
    };
    image.src = result.image_url;
    return true;
  }
  return { reset, invalidate, restore, revision: () => serial, dispose() {
    serial++;
    controllers.forEach((controller) => controller.abort());
    button.removeEventListener('click', run);
    image.remove();
  }};
}
