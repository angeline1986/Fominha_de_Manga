import { RESIDUE_TYPES, addOccurrence, createPageDraftStore, normalizedBox,
  normalizedPoint, removeFromDraft, renderedBoxSize, updateOccurrenceType } from "/texto_off/comparison/residue_model.js";
import { iconMarkup } from "/_shared/icons/icons.js";

export function createResidueCatalog({ workspace, slider, onOpenChange = () => {} }) {
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
      <button class="btn comparison-residue-catalog" type="button" disabled>Catalogar Resíduo</button></footer>`;
  const overlay = document.createElement("div");
  overlay.className = "comparison-residue-overlay";
  overlay.setAttribute("aria-hidden", "true");
  slider.mountAfterOverlay(overlay);
  panel.inert = true;

  const drafts = createPageDraftStore(), query = (selector) => panel.querySelector(selector);
  let currentPage = "", state = "idle", drag = null, hoveredId = null;
  const options = RESIDUE_TYPES.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");

  function draft() {
    return drafts.get(currentPage);
  }
  function setState(next) {
    state = next;
    const drawing = state === "drawing", armed = state !== "idle";
    query("[data-signal]").setAttribute("aria-pressed", String(armed));
    query("[data-draw]").disabled = !armed;
    query("[data-draw]").setAttribute("aria-pressed", String(drawing));
    query("[data-hint]").textContent = drawing ? "Clique e arraste sobre Auto Cleaner para demarcar o resíduo."
      : armed ? "Sinalização ativa. Selecione uma área para começar." : "Ative a sinalização para selecionar áreas.";
    overlay.classList.toggle("is-drawing", drawing);
    slider.setInteractionMode(drawing ? "residue-selection" : "normal");
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
    if (removeFromDraft(draft(), id)) { if (hoveredId === id) highlight(null); render(); }
  }
  function render() {
    const occurrences = draft().occurrences;
    query("[data-count]").value = String(occurrences.length);
    overlay.querySelectorAll("[data-box-id], [data-live-box]").forEach((box) => box.remove());
    const rows = [];
    for (const item of occurrences) {
      const box = document.createElement("div");
      box.className = "comparison-residue-box"; box.dataset.boxId = item.id;
      box.style.left = `${item.box.left * 100}%`; box.style.top = `${item.box.top * 100}%`;
      box.style.width = `${item.box.width * 100}%`; box.style.height = `${item.box.height * 100}%`;
      box.innerHTML = `<span class="comparison-residue-number">${item.number}</span><button class="btn comparison-residue-delete" type="button" data-remove="${item.id}" aria-label="Remover área ${item.number}">${iconMarkup("close")}</button>`;
      overlay.append(box);
      const row = document.createElement("div");
      row.className = "comparison-residue-row"; row.dataset.occurrenceId = item.id;
      row.innerHTML = `<span class="comparison-residue-number">${item.number}</span><select aria-label="Tipo da área ${item.number}" data-type="${item.id}">${options}</select><button class="btn comparison-residue-delete" type="button" data-remove="${item.id}" aria-label="Remover área ${item.number}">${iconMarkup("close")}</button>`;
      row.querySelector("select").value = item.type;
      if (item.type === "outro") {
        const note = document.createElement("input"); note.type = "text"; note.placeholder = "Descreva o defeito...";
        note.setAttribute("aria-label", `Descrição da área ${item.number}`); note.dataset.note = item.id; note.value = item.note || "";
        row.append(note);
      }
      rows.push(row);
    }
    query("[data-layers]").replaceChildren(...rows);
    if (hoveredId) highlight(hoveredId);
  }
  function point(event) { return normalizedPoint(event, overlay.getBoundingClientRect()); }
  function paintLive(box) {
    let live = overlay.querySelector("[data-live-box]");
    if (!live) { live = document.createElement("div"); live.dataset.liveBox = ""; live.className = "comparison-residue-box is-live"; overlay.append(live); }
    live.style.left = `${box.left * 100}%`; live.style.top = `${box.top * 100}%`;
    live.style.width = `${box.width * 100}%`; live.style.height = `${box.height * 100}%`;
  }
  function pointerDown(event) {
    if (state !== "drawing" || event.button !== 0 || event.target.closest("[data-remove]")) return;
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
    addOccurrence(draft(), box, crypto.randomUUID()); render();
  }

  function onClick(event) {
    if (event.target.closest("[data-close]")) setOpen(false);
    if (event.target.closest("[data-signal]")) setState(state === "idle" ? "armed" : "idle");
    if (event.target.closest("[data-draw]")) setState(state === "drawing" ? "armed" : "drawing");
    const remove = event.target.closest("[data-remove]");
    if (remove) removeOccurrence(remove.dataset.remove);
  }
  function onChange(event) {
    const select = event.target.closest("[data-type]");
    if (!select) return;
    const item = draft().occurrences.find((occurrence) => occurrence.id === select.dataset.type);
    if (item) { updateOccurrenceType(item, select.value); render(); }
  }
  function onInput(event) {
    const input = event.target.closest("[data-note]");
    const item = input && draft().occurrences.find((occurrence) => occurrence.id === input.dataset.note);
    if (item) item.note = input.value || null;
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
    currentPage = String(pageKey || ""); hoveredId = null; render();
  }
  function dispose() {
    setState("idle");
    panel.removeEventListener("click", onClick); panel.removeEventListener("change", onChange);
    panel.removeEventListener("input", onInput); panel.removeEventListener("pointerover", onPointerOver);
    panel.removeEventListener("pointerout", onPointerOut);
    overlay.removeEventListener("pointerdown", pointerDown); overlay.removeEventListener("pointermove", pointerMove);
    overlay.removeEventListener("click", onClick);
    overlay.removeEventListener("pointerup", pointerEnd); overlay.removeEventListener("pointercancel", pointerEnd);
    overlay.removeEventListener("lostpointercapture", pointerEnd);
    overlay.removeEventListener("pointerover", onPointerOver); overlay.removeEventListener("pointerout", onPointerOut);
    overlay.remove(); panel.remove(); drafts.clear();
  }
  return { element: panel, setPage, setOpen, toggle: () => setOpen(!panel.classList.contains("is-open")), dispose };
}
