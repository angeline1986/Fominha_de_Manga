import { RESIDUE_TYPES, normalizedBox, normalizedPoint, renderedBoxSize } from "/texto_off/comparison/residue_model.js";
import { createResidueCatalogState } from "/texto_off/comparison/residue_catalog_state.js";
import { renderResidueOccurrences } from "/texto_off/comparison/residue_catalog_view.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { showMessage } from "/_shared/messages/messages.js";

export function createResidueCatalog({ workspace, slider, context, onOpenChange = () => {}, onPersistedCount = () => {} }) {
  const panel = document.createElement("aside");
  panel.className = "comparison-residue-panel";
  panel.setAttribute("aria-label", "Catalogação de resíduos");
  panel.setAttribute("aria-hidden", "true");
  panel.innerHTML = `<header class="comparison-residue-heading"><h2>Catalogação de resíduos</h2>
      <button class="btn comparison-residue-close" type="button" data-close aria-label="Fechar painel">${iconMarkup("close")}</button></header>
    <section class="comparison-residue-step"><h3>Passo 1: identificar resíduo</h3>
      <button class="btn comparison-residue-action" type="button" data-signal aria-pressed="false">Sinalizar Resíduo</button>
      <button class="btn comparison-residue-action" type="button" data-draw aria-pressed="false" disabled>Selecionar área manual</button>
      <p data-hint aria-live="polite">Ative a sinalização para selecionar áreas.</p></section>
    <section class="comparison-residue-layers"><header><h3>Camadas / áreas</h3><output data-count>0</output></header>
      <div data-layers></div></section>
    <footer class="comparison-residue-step"><h3>Passo 2</h3>
      <button class="btn comparison-residue-catalog" type="button" data-catalog disabled>Catalogar Resíduo</button>
      <div class="comparison-residue-feedback"><p data-feedback role="status" aria-live="polite"></p>
        <button class="btn comparison-residue-retry" type="button" data-retry hidden>Recarregar ocorrências</button></div></footer>`;
  const overlay = document.createElement("div");
  overlay.className = "comparison-residue-overlay";
  overlay.setAttribute("aria-hidden", "true");
  slider.mountAfterOverlay(overlay);
  panel.inert = true;

  const query = (selector) => panel.querySelector(selector);
  let currentPage = "", state = "idle", drag = null, hoveredId = null;
  const options = RESIDUE_TYPES.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
  const catalogState = createResidueCatalogState(context, render, onPersistedCount);

  function draft() { return catalogState.current(); }
  function setState(next) {
    if (next === "drawing" && draft().loadState !== "ready") return;
    state = next;
    const drawing = state === "drawing", armed = state !== "idle";
    query("[data-signal]").setAttribute("aria-pressed", String(armed));
    query("[data-draw]").disabled = !armed || draft().loadState !== "ready";
    query("[data-draw]").setAttribute("aria-pressed", String(drawing));
    query("[data-hint]").textContent = drawing ? "Clique e arraste sobre Auto Cleaner para demarcar o resíduo."
      : armed ? "Sinalização ativa. Selecione uma área para começar." : "Ative a sinalização para selecionar áreas.";
    overlay.classList.toggle("is-drawing", drawing);
    slider.setInteractionMode(drawing ? "residue-selection" : "normal");
  }
  function syncStatus() {
    const item = draft();
    query("[data-catalog]").disabled = !catalogState.canSave();
    query("[data-retry]").hidden = item.loadState !== "error";
    query("[data-draw]").disabled = state === "idle" || item.loadState !== "ready";
    const message = item.loadState === "loading" ? "Carregando ocorrências desta página…"
      : item.loadState === "error" ? `Falha ao carregar: ${item.error || "tente novamente."}`
        : item.saveState === "saving" ? "Salvando ocorrências…"
          : item.saveState === "error" ? `Falha ao catalogar: ${item.error || "tente novamente."}`
            : item.dirty ? "Há alterações ainda não catalogadas."
              : item.persisted ? "Ocorrências catalogadas."
                : "Nenhuma ocorrência catalogada nesta página.";
    query("[data-feedback]").textContent = message;
  }
  function setOpen(open) {
    workspace.classList.toggle("has-residue-panel", open);
    panel.setAttribute("aria-hidden", String(!open));
    panel.inert = !open;
    panel.classList.toggle("is-open", open);
    onOpenChange(open);
    return open;
  }
  function highlight(id) {
    hoveredId = id;
    overlay.querySelectorAll("[data-box-id]").forEach((box) => box.classList.toggle("is-highlighted", box.dataset.boxId === id));
    query("[data-layers]").querySelectorAll("[data-occurrence-id]").forEach((row) => row.classList.toggle("is-highlighted", row.dataset.occurrenceId === id));
  }
  function removeOccurrence(id) {
    if (hoveredId === id) highlight(null);
    catalogState.remove(id);
  }
  function render() {
    const occurrences = draft().occurrences;
    query("[data-count]").value = String(occurrences.length);
    renderResidueOccurrences(overlay, query("[data-layers]"), occurrences, options);
    if (hoveredId) highlight(hoveredId);
    syncStatus();
  }
  function point(event) { return normalizedPoint(event, overlay.getBoundingClientRect()); }
  function paintLive(box) {
    let live = overlay.querySelector("[data-live-box]");
    if (!live) { live = document.createElement("div"); live.dataset.liveBox = ""; live.className = "comparison-residue-box is-live"; overlay.append(live); }
    live.style.left = `${box.left * 100}%`; live.style.top = `${box.top * 100}%`;
    live.style.width = `${box.width * 100}%`; live.style.height = `${box.height * 100}%`;
  }
  function pointerDown(event) {
    if (state !== "drawing" || draft().loadState !== "ready" || event.button !== 0
        || event.target.closest("[data-remove]")) return;
    const rect = overlay.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    drag = { id: event.pointerId, start: point(event) };
    overlay.setPointerCapture(event.pointerId); event.preventDefault();
    paintLive(normalizedBox(drag.start, drag.start));
  }
  function pointerMove(event) {
    if (!drag || drag.id !== event.pointerId) return;
    paintLive(normalizedBox(drag.start, point(event)));
  }
  function pointerEnd(event) {
    if (!drag || drag.id !== event.pointerId) return;
    const start = drag.start; drag = null;
    if (overlay.hasPointerCapture(event.pointerId)) overlay.releasePointerCapture(event.pointerId);
    overlay.querySelector("[data-live-box]")?.remove();
    if (event.type !== "pointerup") return;
    const box = normalizedBox(start, point(event)), size = renderedBoxSize(box, overlay.getBoundingClientRect());
    if (size.width < 20 || size.height < 20) return;
    catalogState.add(box, crypto.randomUUID());
  }

  function onClick(event) {
    if (event.target.closest("[data-retry]")) { catalogState.setPage(currentPage); return; }
    if (event.target.closest("[data-close]")) setOpen(false);
    if (event.target.closest("[data-signal]")) setState(state === "idle" ? "armed" : "idle");
    if (event.target.closest("[data-draw]")) setState(state === "drawing" ? "armed" : "drawing");
    const remove = event.target.closest("[data-remove]");
    if (remove) removeOccurrence(remove.dataset.remove);
    if (event.target.closest("[data-catalog]")) void catalogOccurrences();
  }
  function onChange(event) {
    const select = event.target.closest("[data-type]");
    if (!select) return;
    catalogState.setType(select.dataset.type, select.value);
  }
  function onInput(event) {
    const input = event.target.closest("[data-note]");
    if (input && catalogState.setNote(input.dataset.note, input.value)) syncStatus();
  }
  function onPointerOver(event) {
    const box = event.target.closest("[data-box-id]");
    const row = event.target.closest("[data-occurrence-id]");
    if (box) highlight(box.dataset.boxId);
    else if (row) highlight(row.dataset.occurrenceId);
  }
  function onPointerOut(event) {
    const fromBox = event.target.closest("[data-box-id]");
    const fromRow = event.target.closest("[data-occurrence-id]");
    const toBox = event.relatedTarget?.closest?.("[data-box-id]");
    const toRow = event.relatedTarget?.closest?.("[data-occurrence-id]");
    if ((fromBox || fromRow) && !toBox && !toRow) highlight(null);
  }
  panel.addEventListener("click", onClick);
  panel.addEventListener("change", onChange);
  panel.addEventListener("input", onInput);
  panel.addEventListener("pointerover", onPointerOver);
  panel.addEventListener("pointerout", onPointerOut);
  overlay.addEventListener("pointerdown", pointerDown);
  overlay.addEventListener("click", onClick);
  overlay.addEventListener("pointermove", pointerMove);
  overlay.addEventListener("pointerup", pointerEnd);
  overlay.addEventListener("pointercancel", pointerEnd);
  overlay.addEventListener("lostpointercapture", pointerEnd);
  overlay.addEventListener("pointerover", onPointerOver);
  overlay.addEventListener("pointerout", onPointerOut);

  function setPage(pageKey) {
    currentPage = String(pageKey || ""); hoveredId = null; catalogState.setPage(currentPage);
  }
  async function catalogOccurrences() {
    const result = await catalogState.save(slider.getImageMetrics());
    if (result.ok) await showMessage({ title: "Ocorrências catalogadas", message: "As áreas desta página foram salvas no manifesto." });
    else if (result.error) await showMessage({ title: "Falha ao catalogar", message: result.error });
  }
  function dispose() {
    setState("idle"); catalogState.dispose();
    panel.removeEventListener("click", onClick); panel.removeEventListener("change", onChange);
    panel.removeEventListener("input", onInput); panel.removeEventListener("pointerover", onPointerOver);
    panel.removeEventListener("pointerout", onPointerOut);
    overlay.removeEventListener("pointerdown", pointerDown); overlay.removeEventListener("pointermove", pointerMove);
    overlay.removeEventListener("click", onClick);
    overlay.removeEventListener("pointerup", pointerEnd); overlay.removeEventListener("pointercancel", pointerEnd);
    overlay.removeEventListener("lostpointercapture", pointerEnd);
    overlay.removeEventListener("pointerover", onPointerOver); overlay.removeEventListener("pointerout", onPointerOut);
    overlay.remove(); panel.remove();
  }
  return { element: panel, setPage, setOpen, toggle: () => setOpen(!panel.classList.contains("is-open")), dispose };
}
