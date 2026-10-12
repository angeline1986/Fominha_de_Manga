/** Posicionamento compartilhado das prévias flutuantes do navegador. */
export function positionPreview(element, clientX, clientY) {
  const gap = 16, edge = 8;
  const width = element.offsetWidth || 234;
  const height = element.offsetHeight || 334;
  let left = clientX + gap;
  let top = clientY + gap;
  if (left + width + edge > window.innerWidth) left = clientX - width - gap;
  if (top + height + edge > window.innerHeight) top = clientY - height - gap;
  element.style.left = `${Math.max(edge, Math.min(left, Math.max(edge, window.innerWidth - width - edge)))}px`;
  element.style.top = `${Math.max(edge, Math.min(top, Math.max(edge, window.innerHeight - height - edge)))}px`;
}

export function previewNearElement(element, target) {
  const rect = target.getBoundingClientRect();
  positionPreview(element, rect.right, rect.top + Math.min(rect.height / 2, 20));
}
