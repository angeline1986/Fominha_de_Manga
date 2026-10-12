/** Laboratório L3: Degradê experimental com autorização individual e temporária. */
import { confirmMessage } from "/_shared/messages/messages.js";
import { confirmDegradeLaboratory, executeDegradeLaboratory,
  getDegradeAuthorizationCandidates } from "/_app/api/laboratorio.js";
import { drawDegradeCandidates } from "/texto_off/laboratorio/degrade_candidates.js";
export function connectDegrade({ root, button, getRequest }) {
  const panel = root.querySelector('.lab-cards > .lab-image:nth-child(2)');
  const placeholder = panel.querySelector('.lab-placeholder');
  const image = document.createElement('img');
  Object.assign(image, {className: 'lab-original-image', alt: 'Prévia experimental Degradê', hidden: true});
  panel.append(image);
  const note = root.querySelector('[data-lab-degrade-status]');
  const progress = document.createElement('progress');
  progress.className = 'lab-degrade-progress';
  progress.setAttribute('aria-label', 'Tratamento Degradê em execução');
  progress.hidden = true;
  note.after(progress);
  const review = document.createElement('section');
  Object.assign(review, {className: 'lab-degrade-review', hidden: true});
  review.setAttribute('aria-label', 'Autorização assistida de componentes Degradê');
  note.after(review);
  const frame = root.querySelector('.lab-roi-frame');
  const highlights = document.createElement('div');
  highlights.className = 'lab-degrade-highlights';
  frame?.append(highlights);
  let controller = null;
  let serial = 0;
  let sourceKey = '';
  let proposal = null;
  function clearReview() {
    proposal = null;
    review.replaceChildren();
    review.hidden = true;
    highlights.replaceChildren();
  }
  function clearResult(message = 'Aguardando execução') {
    image.hidden = true; image.removeAttribute('src'); placeholder.hidden = false;
    placeholder.textContent = message;
  }
  function reset(key) {
    if (sourceKey === key) return;
    sourceKey = key;
    invalidate();
    note.textContent = 'Selecione uma página e pelo menos uma área.';
    progress.hidden = true;
    button.disabled = false;
  }
  function invalidate() {
    serial++;
    controller?.abort();
    controller = null;
    clearReview();
    clearResult();
    progress.hidden = true;
  }
  function current(id, snapshot) {
    return id === serial && JSON.stringify(getRequest()) === snapshot;
  }
  function showResult(result, id) {
    image.onload = () => {
      if (id !== serial) return;
      image.hidden = false; placeholder.hidden = true;
      note.textContent = 'Prévia experimental pronta. Nenhum arquivo oficial foi alterado.';
    };
    image.onerror = () => {
      if (id !== serial) return;
      clearResult('Falha ao abrir a prévia experimental.');
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
      note.textContent = 'Proposta invalidada: a imagem ou as ROIs mudaram.';
      return;
    }
    const rows = proposal.candidates.filter((item) => selected.includes(item.id));
    const confirmed = await confirmMessage({title: 'Autorizar componentes adiados',
      message: `Você confirmou ${rows.map((item) => `componente ${item.component}`).join(', ')} para esta imagem e estas ROIs. A autorização vale somente para esta execução experimental.`,
      confirmText: 'Autorizar e executar'});
    if (!confirmed) {
      note.textContent = 'Autorização cancelada; o Degradê não foi executado.';
      confirmButton.disabled = false;
      return;
    }
    if (!current(id, snapshot)) {
      invalidate();
      note.textContent = 'Confirmação invalidada: a imagem ou as ROIs mudaram.';
      return;
    }
    confirmButton.disabled = true;
    button.disabled = true;
    progress.hidden = false;
    note.textContent = 'Executando os componentes confirmados...';
    const active = new AbortController(); controller = active;
    try {
      const result = await confirmDegradeLaboratory({
        ...getRequest(), proposal_run_id: proposal.runId,
        proposal_token: proposal.token, component_ids: selected,
      }, active.signal);
      if (!current(id, snapshot)) return;
      clearReview();
      showResult(result, id);
    } catch (error) {
      if (id === serial && error.name !== 'AbortError') {
        clearReview();
        note.textContent = `Autorização não concluída: ${error.message}`;
      }
    } finally {
      if (id === serial) { button.disabled = false; progress.hidden = true; controller = null; }
    }
  }
  async function run() {
    const payload = getRequest();
    if (!payload) {
      note.textContent = 'Selecione uma imagem carregada e pelo menos uma área.';
      return;
    }
    const id = ++serial;
    const snapshot = JSON.stringify(payload);
    controller?.abort();
    const active = new AbortController(); controller = active;
    clearReview();
    clearResult('Processando Degradê...');
    button.disabled = true;
    note.textContent = 'Classificação automática em andamento.';
    progress.hidden = false;
    try {
      const result = await executeDegradeLaboratory(payload, active.signal);
      if (current(id, snapshot)) showResult(result, id);
    } catch (error) {
      if (id !== serial || error.name === 'AbortError') return;
      const runId = error.body?.run_id;
      if (runId) {
        try {
          const candidates = await getDegradeAuthorizationCandidates(runId, active.signal);
          if (!current(id, snapshot)) return;
          proposal = {runId: candidates.proposal_run_id, token: candidates.proposal_token,
            requestSnapshot: snapshot, candidates: candidates.candidates};
          drawCandidates(candidates.candidates);
          note.textContent = `A classificação automática adiou ${candidates.candidates.length} componente(s). Revise e confirme individualmente.`;
          return;
        } catch (candidateError) {
          if (candidateError.name === 'AbortError' || id !== serial) return;
          note.textContent = `Degradê não concluído: ${candidateError.message}`;
        }
      } else {
        note.textContent = `Degradê não concluído: ${error.message}`;
      }
      placeholder.textContent = 'Consulte os registros do experimento.';
    } finally {
      if (id === serial) { button.disabled = false; progress.hidden = true; controller = null; }
    }
  }
  button.addEventListener('click', run);
  return {reset, invalidate, dispose() {
    serial++;
    controller?.abort();
    button.removeEventListener('click', run);
    image.remove(); progress.remove(); review.remove(); highlights.remove();
  }};
}
