/** Candidate list and natural-coordinate highlights for assisted Degradê. */
export function drawDegradeCandidates({review, highlights, frame, candidates, onConfirm}) {
  const heading = document.createElement('strong');
  heading.textContent = 'Componentes adiados detectados';
  const explanation = document.createElement('p');
  explanation.className = 'lab-muted';
  explanation.textContent = 'Marque apenas as regiões que deseja autorizar. A confirmação é separada da classificação automática.';
  review.replaceChildren(heading, explanation);
  const original = frame.querySelector('img');
  for (const candidate of candidates) {
    const label = document.createElement('label');
    label.className = 'lab-degrade-candidate';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox'; checkbox.value = candidate.id;
    const detail = document.createElement('span');
    const [x, y, width, height] = candidate.bbox;
    detail.textContent = `Componente ${candidate.component} · ${width} × ${height} px · área ${candidate.area} · ROI ${candidate.roi_hits.join(', ')}`;
    label.append(checkbox, detail); review.append(label);
    const mark = document.createElement('div'); mark.className = 'lab-degrade-candidate-box';
    mark.style.left = `${100 * x / original.naturalWidth}%`;
    mark.style.top = `${100 * y / original.naturalHeight}%`;
    mark.style.width = `${100 * width / original.naturalWidth}%`;
    mark.style.height = `${100 * height / original.naturalHeight}%`;
    const tag = document.createElement('span');
    tag.textContent = `Componente ${candidate.component}`;
    mark.append(tag); highlights.append(mark);
  }
  const confirm = document.createElement('button');
  confirm.type = 'button'; confirm.className = 'lab-wide';
  confirm.textContent = 'Confirmar seleção e executar Degradê';
  confirm.disabled = true; review.append(confirm);
  review.querySelectorAll('input[type=checkbox]').forEach((input) => {
    input.addEventListener('change', () => {
      confirm.disabled = !review.querySelector('input:checked');
    });
  });
  confirm.addEventListener('click', onConfirm);
  review.hidden = false;
}
