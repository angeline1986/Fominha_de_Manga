import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { createBalanceMergeList } from "/processamento/balanceamento/validar_estado_list.js";
import { createBalanceCanvas } from "/processamento/balanceamento/validar_estado_canvas.js";

export function createBalanceValidationView({ onOpenEditor, onRevalidate, onZoom = () => {} }) {
  const element = document.createElement("section");
  element.className = "balance-validation-page focus-mode-root";
  element.innerHTML = `<header class="balance-validation-header"><span>VALIDAR BALANCEAMENTO</span></header>
    <div class="balance-validation-workspace"><div data-list></div><div data-canvas></div></div>
    <p class="balance-validation-status" role="status" aria-live="polite" data-status></p>`;
  const list = createBalanceMergeList({ onEvent });
  const canvas = createBalanceCanvas({ onZoom });
  element.querySelector("[data-list]").replaceWith(list.element);
  element.querySelector("[data-canvas]").replaceWith(canvas.element);
  element.append(canvas.focusDock);
  const disposeFocus = bindFocusMode(element, { button: canvas.focusButton });
  let state = { chapters: [] };
  let selectedChapter = null;
  let selectedMerges = new Set();
  let zoom = 60;
  function chapter() { return (state.chapters || []).find((row) => String(row.chapter) === String(selectedChapter)) || null; }

  function draw() {
    const rows = state.chapters || [];
    if (rows.length && !rows.some((row) => String(row.chapter) === String(selectedChapter))) {
      selectedChapter = rows.length ? String(rows[0].chapter) : null;
      selectedMerges = defaultSelection(rows[0]);
    }
    const current = chapter();
    element.querySelector("[data-status]").textContent = state.status === "loading" ? `Lendo merges de ${state.manga}…` : state.status === "error" ? state.error : state.status === "idle" ? "Selecione provider e obra para consultar o Balanceamento." : "";
    list.update({ ...state, chapter: current }, selectedMerges);
    canvas.update({ ...state, chapter: current, selectedMerges: [...selectedMerges], zoom });
  }

  function selectChapter(value) {
    selectedChapter = value || null;
    selectedMerges = defaultSelection(chapter());
    draw();
  }

  function onEvent(action, value) {
    if (action === "refresh") onRevalidate();
    if (action === "chapter") selectChapter(value);
    if (action === "selection") { selectedMerges = new Set(value); draw(); }
    if (action === "submit") onOpenEditor({ chapter: selectedChapter, merges: value });
  }

  function update(next) {
    const contextChanged = state.provider !== next.provider || state.manga !== next.manga;
    state = { ...state, ...next };
    if (contextChanged) { selectedChapter = null; selectedMerges.clear(); }
    draw();
  }

  draw();
  return {
    element, update,
    dispose() { list.dispose(); canvas.dispose(); disposeFocus(); },
  };
}

export function defaultSelection(chapter) {
  const merges = chapter?.merges || [];
  if (!merges.length) return new Set();
  const issue = chapter.issues?.[0];
  const index = issue ? merges.findIndex((item) => item.file === issue.file) : 0;
  const start = Math.max(0, index - (issue ? 1 : 0));
  const end = Math.min(merges.length, index + (issue ? 2 : 2));
  return new Set(merges.slice(start, end).map((item) => item.file));
}
