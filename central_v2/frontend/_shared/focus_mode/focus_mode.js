let activeController = null;
let lastController = null;

export function bindFocusMode(root, { button, active = false, onChange = () => {} }) {
  root.classList.add("focus-mode-root");
  const controller = { root, setFocus };
  const exitButtons = root.querySelectorAll("[data-focus-exit]");
  function setFocus(next, notify = true) {
    root.classList.toggle("is-focus-mode", next);
    document.body.classList.toggle("has-image-focus", next);
    button?.setAttribute("aria-pressed", String(next));
    if (next) activeController = lastController = controller;
    else if (activeController === controller) activeController = null;
    if (notify) onChange(next);
  }
  function onToggle() { setFocus(!root.classList.contains("is-focus-mode")); }
  function onKeyDown(event) {
    if (document.querySelector("dialog[open]")) return;
    const editing = event.target.closest?.("input, textarea, select, [contenteditable='true']");
    if (event.key === "Escape" && activeController === controller) {
      event.preventDefault(); setFocus(false);
    } else if ((event.key === "f" || event.key === "F") && !editing && !event.altKey && !event.ctrlKey && !event.metaKey && !activeController && lastController === controller) {
      event.preventDefault(); setFocus(true);
    }
  }
  function remember() { lastController = controller; }
  button?.addEventListener("click", onToggle);
  exitButtons.forEach((item) => item.addEventListener("click", () => setFocus(false)));
  root.addEventListener("focusin", remember);
  document.addEventListener("keydown", onKeyDown);
  if (!lastController) lastController = controller;
  if (active) setFocus(true, false);
  return () => {
    button?.removeEventListener("click", onToggle);
    root.removeEventListener("focusin", remember);
    document.removeEventListener("keydown", onKeyDown);
    if (activeController === controller) activeController = null;
    if (lastController === controller) lastController = null;
    root.classList.remove("is-focus-mode");
    document.body.classList.remove("has-image-focus");
  };
}
