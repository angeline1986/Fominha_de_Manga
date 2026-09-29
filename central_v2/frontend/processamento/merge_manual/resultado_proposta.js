import { applyMergeManualProposal, mergeManualProposalImageUrl } from "/_app/api/merge_manual.js";
import { getMergeManualSelection } from "/_app/state/merge_manual.js";
import { escapeHtml } from "/_shared/dom/sanitize.js";
import { confirmMessage, showMessage } from "/_shared/messages/messages.js";
import { bindFocusMode } from "/_shared/focus_mode/focus_mode.js";
import { iconMarkup } from "/_shared/icons/icons.js";

export function render(container) {
  const selection = getMergeManualSelection();
  const proposal = selection?.proposal;
  const page = document.createElement("section");
  page.className = "manual-proposal-result";
  container.replaceChildren(page);
  if (!selection || !proposal) {
    page.innerHTML = `<p role="status">Não há proposta para visualizar. Gere uma proposta em Novos Merges.</p>`;
    return;
  }

  page.innerHTML = `
    <header class="manual-result-toolbar">
      <button type="button" class="manual-cut-back" data-back>← Voltar aos cortes</button>
      <div><h1>Resultado · Cap. ${escapeHtml(selection.chapter)}</h1><p>${proposal.outputs.length} merges</p></div>
      <div class="manual-result-tools">
        <div class="zoom-control"><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><output data-zoom-value>100%</output><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><button type="button" class="zoom-control-reset" data-reset aria-label="Visualizar em escala 1 para 1">1:1</button></div>
        <button type="button" class="manual-cut-toolbar-button" data-focus-toggle aria-label="Modo Foco" aria-pressed="false">${iconMarkup("focus-exit")} Foco</button>
        <button type="button" class="manual-result-apply" data-apply>Aplicar composição final</button>
      </div>
    </header>
    <aside class="focus-mode-dock focus-mode-compact" data-focus-dock aria-label="Controles do resultado em foco">
      <button type="button" data-focus-exit aria-label="Sair do Modo Foco" title="Sair do Modo Foco"><span>×</span></button>
      <span data-focus-divider></span><div class="focus-mode-zoom"><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><output data-zoom-value-dock>100%</output><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><button type="button" data-reset aria-label="Visualizar em escala 1 para 1">1:1</button></div>
      <span data-focus-divider></span><button type="button" class="focus-mode-primary" data-apply aria-label="Aplicar composição final" title="Aplicar composição final">✓</button>
    </aside>
    <p class="manual-result-status" data-status role="status" aria-live="polite"></p>
    ${compositionMarkup(selection, proposal)}
  `;

  const grid = page.querySelector("[data-grid]");
  const zoomValue = page.querySelector("[data-zoom-value]");
  const status = page.querySelector("[data-status]");
  let zoom = 100;
  grid.style.setProperty("--result-count", proposal.outputs.length);
  const disposeFocusMode = bindFocusMode(page, { button: page.querySelector("[data-focus-toggle]") });
  page.querySelector("[data-back]").addEventListener("click", () => navigate(container, "novos-merges"));
  page.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => {
    zoom = Math.max(30, Math.min(200, zoom + (button.dataset.zoom === "+" ? 10 : -10)));
    setZoom();
  }));
  page.querySelectorAll("[data-reset]").forEach((button) => button.addEventListener("click", () => { zoom = 100; setZoom(); }));
  page.querySelectorAll("[data-apply]").forEach((button) => button.addEventListener("click", async (event) => {
    const confirmed = await confirmMessage({
      title: "Aplicar composição final",
      message: "Os novos merges substituirão a composição oficial deste capítulo em 02_MERGE. Deseja continuar?",
      confirmText: "Aplicar",
    });
    if (!confirmed) return;
    page.querySelectorAll("[data-apply]").forEach((item) => { item.disabled = true; });
    status.textContent = "Validando e aplicando composição final…";
    try {
      const result = await applyMergeManualProposal({ provider: selection.provider, manga: selection.manga, chapter: selection.chapter, proposal_id: proposal.proposal_id });
      status.textContent = "";
      await showMessage({ title: "Composição aplicada", message: result.message || "A composição final foi aplicada e validada em 02_MERGE." });
    } catch (error) {
      status.textContent = "";
      page.querySelectorAll("[data-apply]").forEach((item) => { item.disabled = false; });
      await showMessage({ title: "Falha ao aplicar composição", message: error.message });
    }
  }));
  function setZoom() {
    zoomValue.textContent = `${zoom}%`;
    page.querySelector("[data-zoom-value-dock]").textContent = `${zoom}%`;
    grid.style.setProperty("--result-zoom-scale", zoom / 100);
  }
  return () => disposeFocusMode();
}

export function compositionMarkup(selection, proposal) {
  const segments = proposal.outputs.map((output) => `
    <figure class="manual-result-segment">
      <img loading="lazy" src="${mergeManualProposalImageUrl(selection.provider, selection.manga, selection.chapter, proposal.proposal_id, output.file)}" alt="Merge ${output.block} de ${proposal.outputs.length}">
      <figcaption>${escapeHtml(getOutputPageRange(proposal, output))}</figcaption>
    </figure>`).join("");
  return `<div class="manual-result-composition"><div class="manual-result-grid" data-grid>${segments}</div></div>`;
}

export function getOutputPages(proposal, output) {
  const start = Number(output.global_start);
  const end = Number(output.global_end);
  let cursor = Number(proposal.source_block.global_start);
  return proposal.source_files.flatMap((source) => {
    const sourceStart = cursor;
    const sourceEnd = sourceStart + Number(source.pending_height);
    cursor = sourceEnd;
    return Math.min(end, sourceEnd) > Math.max(start, sourceStart) ? [source.name] : [];
  });
}

export function getOutputPageRange(proposal, output) {
  const files = proposal.source_files || [];
  let cursor = Number(proposal.source_block.global_start);
  let startPage = "";
  let endPage = "";
  const start = Number(output.global_start);
  const end = Number(output.global_end);
  for (const source of files) {
    const sourceEnd = cursor + Number(source.pending_height);
    if (!startPage && start <= sourceEnd) startPage = source.name;
    if (end <= sourceEnd) { endPage = source.name; break; }
    cursor = sourceEnd;
  }
  endPage ||= files.at(-1)?.name || "";
  if (!startPage) startPage = files[0]?.name || "";
  return startPage === endPage ? startPage : `${startPage} → ${endPage}`;
}

function navigate(container, action) {
  container.dispatchEvent(new CustomEvent("menu:action", { bubbles: true, detail: { action } }));
}
