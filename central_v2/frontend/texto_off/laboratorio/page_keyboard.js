/** Scoped arrow-key pagination outside interactive controls. */
export function connectPageKeyboard(root, prev, next) {
  function onKey(event) {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || event.defaultPrevented
        || event.repeat || event.altKey || event.ctrlKey || event.metaKey
        || event.shiftKey || !root.isConnected) return;
    if (event.target instanceof Element && event.target.closest(
      'input, textarea, select, button, [contenteditable], [role="slider"], [role="dialog"], [role="listbox"]'
    )) return;
    if (document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return;
    const button = event.key === 'ArrowLeft' ? prev : next;
    if (button.disabled) return;
    event.preventDefault();
    button.click();
  }
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}
