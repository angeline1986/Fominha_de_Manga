import { zoomDimensions } from "/texto_off/laboratorio/zoom.js";

/** Painel lateral, modo Foco e zoom do espaço de visualização. */
export function connectWorkspaceControls(root, originalImage) {
  const toolbar = root.querySelector(".lab-tool-group");
  const panel = root.querySelector(".lab-actions");
  const panelToggle = document.createElement("button");
  panelToggle.type = "button";
  panelToggle.textContent = "Painel";
  panelToggle.className = "lab-panel-toggle";
  panelToggle.setAttribute("aria-expanded", "false");
  panelToggle.setAttribute("aria-pressed", "false");
  toolbar.append(panelToggle);
  root.classList.remove("lab-panel-open");
  panel.hidden = true;

  const closePanel = document.createElement("button");
  closePanel.type = "button";
  closePanel.className = "lab-close-panel";
  closePanel.textContent = "×";
  closePanel.title = "Fechar painel";
  closePanel.setAttribute("aria-label", "Fechar painel");
  panel.querySelector(".lab-panel-head").append(closePanel);
  function setPanel(open) {
    root.classList.toggle("lab-panel-open", open);
    panel.hidden = !open;
    panelToggle.setAttribute("aria-expanded", String(open));
    panelToggle.setAttribute("aria-pressed", String(open));
  }
  panelToggle.addEventListener("click", () => setPanel(!root.classList.contains("lab-panel-open")));
  closePanel.addEventListener("click", () => setPanel(false));

  const focusButton = toolbar.querySelector("button[title='Foco'], button[aria-label='Foco']")
    || [...toolbar.querySelectorAll("button")].find((button) => button.textContent.trim() === "Foco");
  const focusFooter = document.createElement("footer");
  focusFooter.className = "lab-focus-footer";
  focusFooter.innerHTML = `
    <span>Comparação horizontal · quatro tratamentos</span>
    <div class="lab-focus-nav">
      <button type="button" data-focus-prev aria-label="Página anterior">‹</button>
      <span data-focus-counter>1 / 1</span>
      <button type="button" data-focus-next aria-label="Próxima página">›</button>
    </div>
    <span>F ou Esc para sair</span>`;
  root.querySelector(".lab-workspace").append(focusFooter);
  const setFocus = (active) => {
    root.classList.toggle("lab-focus-mode", active);
    focusButton?.setAttribute("aria-pressed", String(active));
    document.body.classList.toggle("lab-focus-lock", active);
  };
  if (focusButton) {
    focusButton.disabled = false;
    focusButton.setAttribute("aria-label", "Modo Foco");
    focusButton.setAttribute("aria-pressed", "false");
    focusButton.title = "Modo Foco";
    focusButton.addEventListener("click", () => setFocus(!root.classList.contains("lab-focus-mode")));
  }
  const focusPrev = focusFooter.querySelector("[data-focus-prev]");
  const focusNext = focusFooter.querySelector("[data-focus-next]");
  const focusCounter = focusFooter.querySelector("[data-focus-counter]");
  focusPrev.addEventListener("click", () => root.querySelector("[data-lab-prev]").click());
  focusNext.addEventListener("click", () => root.querySelector("[data-lab-next]").click());

  let active = true;
  const onFocusKey = (event) => {
    if (!active || !root.isConnected) return;
    if (document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return;
    if (event.key === "Escape") {
      if (root.classList.contains("lab-focus-mode")) {
        event.preventDefault();
        setFocus(false);
      }
      return;
    }
    const element = event.target;
    if (element instanceof HTMLElement && (
      element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)
    )) return;
    if (event.key.toLowerCase() === "f" && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      setFocus(!root.classList.contains("lab-focus-mode"));
    }
  };
  document.addEventListener("keydown", onFocusKey);

  const zoomButtons = [...toolbar.querySelectorAll("button")].filter((button) =>
    ["−", "+", "1:1"].includes(button.textContent.trim()));
  const zoomOutput = toolbar.querySelector("span");
  let zoom = 40;
  const setZoomEnabled = (enabled) => zoomButtons.forEach((button) => { button.disabled = !enabled; });
  const resetZoomDimensions = () => {
    root.style.removeProperty("--lab-image-width");
    root.style.removeProperty("--lab-image-height");
    root.style.removeProperty("--lab-panel-width");
  };
  const updateZoom = () => {
    if (zoomOutput) zoomOutput.textContent = `${zoom}%`;
    if (!originalImage?.naturalWidth || !originalImage.naturalHeight) return;
    const size = zoomDimensions(originalImage.naturalWidth, originalImage.naturalHeight, zoom);
    root.style.setProperty("--lab-image-width", `${size.width}px`);
    root.style.setProperty("--lab-image-height", `${size.height}px`);
    root.style.setProperty("--lab-panel-width", `${size.width + 2}px`);
  };
  for (const button of zoomButtons) {
    button.addEventListener("click", () => {
      const action = button.textContent.trim();
      zoom = action === "1:1" ? 100 : Math.max(30, Math.min(200, zoom + (action === "+" ? 10 : -10)));
      updateZoom();
    });
  }
  updateZoom();

  return {
    openPanel: () => setPanel(true),
    setZoomEnabled,
    resetZoomDimensions,
    updateZoom,
    syncFocusNavigation() {
      focusPrev.disabled = root.querySelector("[data-lab-prev]").disabled;
      focusNext.disabled = root.querySelector("[data-lab-next]").disabled;
      focusCounter.textContent = root.querySelector("[data-lab-counter]").textContent;
    },
    dispose() {
      active = false;
      if (root.classList.contains("lab-focus-mode")) setFocus(false);
      document.removeEventListener("keydown", onFocusKey);
    },
  };
}
