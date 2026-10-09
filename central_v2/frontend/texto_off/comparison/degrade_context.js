"use strict";

import { iconMarkup } from "/_shared/icons/icons.js";
import { renderResidueOccurrences } from "/texto_off/comparison/residue_catalog_view.js";

export function createDegradeContext({ workspace, slider, context, onOpenChange = () => {} }) {
  const panel = document.createElement("aside");
  panel.className = "comparison-residue-panel";
  panel.setAttribute("aria-label", "Áreas tratadas em Degradê");
  panel.setAttribute("aria-hidden", "true");
  panel.innerHTML = `<header class="comparison-residue-heading"><h2>Áreas tratadas</h2>
    <button class="btn comparison-residue-close" type="button" data-close aria-label="Fechar painel">${iconMarkup("close")}</button></header>
    <section class="comparison-residue-layers"><header><h3>ROIs aprovadas</h3><output data-count>0</output></header>
      <div data-layers></div></section>`;
  panel.inert = true;
  const overlay = document.createElement("div");
  overlay.className = "comparison-residue-overlay";
  overlay.setAttribute("aria-hidden", "true");
  slider.mountAfterOverlay(overlay);
  let pages = [], current = "";

  function render() {
    const page = pages.find((item) => item.name === current);
    const { naturalWidth: width, naturalHeight: height } = slider.getImageMetrics();
    if (!page || !width || !height) return;
    const occurrences = page.rois.map((roi, index) => ({
      id: page.occurrence_ids[index],
      box: { left: roi.x / width, top: roi.y / height,
        width: roi.width / width, height: roi.height / height },
    })).filter((item) => !context?.initialOccurrence || page.name !== context.initialPage ||
      item.id === context.initialOccurrence);
    renderResidueOccurrences(overlay, panel.querySelector("[data-layers]"),
      occurrences, [], { readOnly: true });
    panel.querySelector("[data-count]").value = String(occurrences.length);
  }
  function setOpen(open) {
    workspace.classList.toggle("has-residue-panel", open);
    panel.setAttribute("aria-hidden", String(!open));
    panel.inert = !open;
    panel.classList.toggle("is-open", open);
    onOpenChange(open);
  }
  function onClick(event) {
    if (event.target.closest("[data-close]")) setOpen(false);
  }
  panel.addEventListener("click", onClick);
  return { element: panel, render,
    setPages(value) { pages = value; },
    setPage(name) { current = name; overlay.replaceChildren(); render(); },
    draftOccurrenceCount() { return null; },
    toggle() { setOpen(!panel.classList.contains("is-open")); },
    dispose() { panel.removeEventListener("click", onClick); overlay.remove(); panel.remove(); },
  };
}
