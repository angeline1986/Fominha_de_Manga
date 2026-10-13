/** Laboratório L3: Degradê experimental com autorização individual e temporária. */
import { confirmDegradeLaboratory, executeDegradeLaboratory,
  getDegradeAuthorizationCandidates } from "/_app/api/laboratorio.js";
import { drawDegradeCandidates } from "/texto_off/laboratorio/degrade_candidates.js";
export function connectDegrade({ root, button, getRequest }) {
  const panel = root.querySelector('.lab-cards > .lab-image:nth-child(2)');
  const placeholder = panel.querySelector('.lab-placeholder');
  const image = document.createElement('img');
  Object.assign(image, {className: 'lab-original-image', alt: 'Prévia experimental Degradê', hidden: true});
  panel.append(image);
  const review = document.createElement('section');
  Object.assign(review, {className: 'lab-degrade-review', hidden: true});
  review.setAttribute('aria-label', 'Autorização assistida de componentes Degradê');
  button.after(review);
  const frame = root.querySelector('.lab-roi-frame');
  const highlights = document.createElement('div');
  highlights.className = 'lab-degrade-highlights';
  frame?.append(highlights);
  const controllers = new Set();
  let serial = 0;
  let sourceKey = '';
  let proposal = null;
  function clearReview() {
    proposal = null;
    review.replaceChildren();
    review.hidden = true;
    highlights.replaceChildren();
  }
  function setState(state, message, busy = false) {
    placeholder.dataset.state = state;
    placeholder.setAttribute('aria-busy', String(busy));
    placeholder.textContent = message;
    placeholder.hidden = false;
  }
  function clearResult(message = 'Aguardando execução', state = 'waiting') {
    image.hidden = true; image.removeAttribute('src');
    setState(state, message);
  }
  function reset(key) {
    if (sourceKey === key) return;
    sourceKey = key;
    invalidate();
    button.disabled = false;
  }
  function invalidate() {
    serial++;
    clearReview();
    clearResult();
    button.disabled = false;
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
      if (!current(id, snapshot)) return;
      clearResult('Falha ao abrir a prévia experimental.', 'failed');
    };
    image.src = result.image_url;
  }
  function drawCandidates(candidates) {
    drawDegradeCandidates({review, highlights, frame, candidates, onConfirm: confirmRun});
  }
  async function confirmRun(event) {
    const confirmButton = event.currentTarget;
    const selected = [...review.querySelectorAll('input:checked')].map((item) => item.value);
    if (!proposal || !selected.length) return;
    const id = serial;
    const snapshot = proposal.requestSnapshot;
    if (!current(id, snapshot)) {
      invalidate();
      return;
    }
    const rows = proposal.candidates.filter((item) => selected.includes(item.id));
    if (!current(id, snapshot) || rows.length !== selected.length) {
      invalidate();
      return;
    }
    confirmButton.disabled = true;
    button.disabled = true;
    setState('running', 'Executando os componentes confirmados…', true);
    const active = new AbortController(); controllers.add(active);
    try {
      const result = await confirmDegradeLaboratory({
        ...getRequest(), proposal_run_id: proposal.runId,
        proposal_token: proposal.token, component_ids: selected,
      }, active.signal);
      if (!current(id, snapshot)) return;
      clearReview();
      showResult(result, id, snapshot);
    } catch (error) {
      if (current(id, snapshot) && error.name !== 'AbortError') {
        clearReview();
        setState('failed', `Autorização não concluída: ${error.message}`);
      }
    } finally {
      controllers.delete(active);
      if (id === serial) button.disabled = false;
    }
  }
  async function run() {
    const payload = getRequest();
    if (!payload) {
      setState('waiting', 'Selecione uma imagem carregada e pelo menos uma área.');
      return;
    }
    const id = ++serial;
    const snapshot = JSON.stringify(payload);
    const active = new AbortController(); controllers.add(active);
    clearReview();
    clearResult('Executando classificação Degradê…', 'running');
    button.disabled = true;
    try {
      const result = await executeDegradeLaboratory(payload, active.signal);
      if (current(id, snapshot)) showResult(result, id, snapshot);
    } catch (error) {
      if (!current(id, snapshot) || error.name === 'AbortError') return;
      const runId = error.body?.run_id;
      if (error.status === 422 && runId) {
        try {
          const candidates = await getDegradeAuthorizationCandidates(runId, active.signal);
          if (!current(id, snapshot)) return;
          proposal = {runId: candidates.proposal_run_id, token: candidates.proposal_token,
            requestSnapshot: snapshot, candidates: candidates.candidates};
          drawCandidates(candidates.candidates);
          setState('waiting', 'Aguardando revisão e autorização dos componentes adiados.');
          return;
        } catch (candidateError) {
          if (candidateError.name === 'AbortError' || !current(id, snapshot)) return;
          if (candidateError.status === 422) {
            setState('waiting', 'Nenhum componente adiado elegível para autorização nesta seleção.');
          } else {
            setState('failed', `Degradê não concluído: ${candidateError.message}`);
          }
        }
      } else {
        setState('failed', `Degradê não concluído: ${error.message}`);
      }
    } finally {
      controllers.delete(active);
      if (id === serial) button.disabled = false;
    }
  }
  button.addEventListener('click', run);
  return {reset, invalidate, dispose() {
    serial++;
    controllers.forEach((controller) => controller.abort());
    button.removeEventListener('click', run);
    image.remove(); review.remove(); highlights.remove();
  }};
}
