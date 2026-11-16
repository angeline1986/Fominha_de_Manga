import { mergeManualImageUrl, mergeManualProposalImageUrl } from "/_app/api/merge_manual.js";
import { escapeHtml } from "/_shared/dom/sanitize.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { savedProposalToolbar, savedProposalFooter } from "/processamento/merge_manual/propostas_salvas_visualizador.js";

export function pageLabel(name) {
  return String(name).replace(/^page-/i, "Pág. ").replace(/\.png$/i, "");
}

export function savedProposalImagesMarkup({ provider, manga, chapter, currentPage, selected, previewed }) {
  if (!currentPage) return '<p class="saved-proposal-placeholder" role="status">Nenhuma página pendente neste capítulo.</p>';
  const original = `<figure><figcaption>ORIGINAL · ${escapeHtml(currentPage)}</figcaption><img src="${mergeManualImageUrl(provider, manga, chapter, currentPage)}" alt="Página original ${escapeHtml(currentPage)}"></figure>`;
  if (!previewed || !selected) return original;
  const outputs = (selected.proposal?.outputs || []).map((output) => `<figure><figcaption>SAÍDA · ${escapeHtml(output.file)}</figcaption><img src="${mergeManualProposalImageUrl(provider, manga, chapter, selected.proposal_id, output.file)}" alt="Merge ${escapeHtml(output.file)}"></figure>`).join("");
  return original + (outputs || '<p class="saved-proposal-placeholder" role="status">Esta proposta não contém saídas para visualizar.</p>');
}

function proposalOptions(items, currentPage, selectedId) {
  return items.filter((item) => (item.proposal?.source_files || []).some((source) => source.name === currentPage)).map((item) => {
    const date = item.created_at ? new Date(item.created_at).toLocaleString("pt-BR") : "—";
    return `<label class="saved-proposal-option ${item.proposal_id === selectedId ? "is-selected" : ""}"><input type="radio" name="saved-proposal" value="${escapeHtml(item.proposal_id)}" ${item.proposal_id === selectedId ? "checked" : ""}>
      <span><strong>${item.outputs} merge(s) · ${escapeHtml(date)}</strong><small>Faixa ${escapeHtml(item.start || "—")} → ${escapeHtml(item.end || "—")}</small></span><b>Pendente</b></label>`;
  }).join("") || '<p class="saved-proposal-empty">Nenhuma proposta pendente para esta página.</p>';
}

export function savedProposalReviewMarkup({ provider, manga, chapter, chapters, currentPage, pages, items, selectedId, previewed, zoom, panelOpen }) {
  const selected = items.find((item) => item.proposal_id === selectedId);
  const index = pages.indexOf(currentPage);
  const chapterOptions = chapters.map((id) => `<option value="${escapeHtml(id)}" ${id === chapter ? "selected" : ""}>Cap. ${escapeHtml(id)}</option>`).join("");
  const pageOptions = pages.map((name) => `<option value="${escapeHtml(name)}" ${name === currentPage ? "selected" : ""}>${escapeHtml(pageLabel(name))}</option>`).join("");
  return `<header class="saved-review-heading"><button type="button" class="btn saved-review-back" data-back-table>${iconMarkup("back")} Voltar à tabela</button>
      <strong>MERGE MANUAL · PROPOSTAS SALVAS</strong><span>Cap. ${escapeHtml(chapter)} · ${items.length} proposta(s) pendente(s)</span></header>
    <div class="saved-review-workspace ${panelOpen ? "has-proposal-panel" : ""}">
      <aside class="saved-review-pages"><div class="saved-review-pages-heading"><h2>Páginas</h2></div><div class="saved-review-selects">
        <select data-chapter aria-label="Capítulo">${chapterOptions}</select><select data-page aria-label="Página">${pageOptions}</select></div>
        <nav class="saved-review-page-list" aria-label="Páginas com propostas pendentes"></nav>
        <div class="saved-review-page-pagination" data-page-pagination></div>
      </aside>
      <main class="saved-review-viewer">${savedProposalToolbar(escapeHtml(chapter), escapeHtml(currentPage), index, pages.length, zoom, panelOpen)}
        <div class="saved-review-viewport"><div class="saved-review-stage"><div class="saved-review-images">${savedProposalImagesMarkup({ provider, manga, chapter, currentPage, selected, previewed })}</div></div></div>
        ${savedProposalFooter(index, pages.length)}</main>
      <aside id="saved-proposal-panel" class="saved-review-panel" ${panelOpen ? "" : "hidden"}>
        <header><div><h2>Propostas para ${escapeHtml(currentPage)}</h2><p>Alternativas salvas que incluem esta página.</p></div><button type="button" class="btn saved-panel-close" data-close-panel aria-label="Fechar painel">${iconMarkup("close")}</button></header>
        <div class="saved-proposal-options">${proposalOptions(items, currentPage, selectedId)}</div>
        <footer><button type="button" class="btn" data-preview ${selected ? "" : "disabled"}>Visualizar</button><button type="button" class="btn primary" data-apply ${selected ? "" : "disabled"}>Efetivar</button></footer>
      </aside>
    </div><aside class="saved-page-preview" data-page-preview role="tooltip" hidden><img alt="Prévia da página original"><span data-preview-name></span></aside>`;
}
