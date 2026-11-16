import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchSavedMergeManualProposals, mergeManualImageUrl, applyMergeManualProposal } from "/_app/api/merge_manual.js";
import { escapeHtml } from "/_shared/dom/sanitize.js";
import { confirmMessage, showMessage } from "/_shared/messages/messages.js";
import { createSavedPagePagination } from "/processamento/merge_manual/propostas_salvas_paginacao.js";
import { bindSavedProposalViewer } from "/processamento/merge_manual/propostas_salvas_visualizador.js";
import { savedProposalImagesMarkup, savedProposalReviewMarkup } from "/processamento/merge_manual/propostas_salvas_revisao.js";
import { savedProposalTableMarkup } from "/processamento/merge_manual/propostas_salvas_tabela.js";
import { isPending, pagesFor, pendingForChapter as pendingProposalsForChapter } from "/processamento/merge_manual/propostas_salvas_model.js";

export function render(container) {
  const page = document.createElement("section");
  page.className = "saved-manual-proposals focus-mode-root";
  container.replaceChildren(page);
  let requestId = 0, proposals = [], chapter = "", currentPage = "", selectedId = "", activeWork = "";
  let mode = "table", panelOpen = false, previewed = false, applying = false;
  let zoom = 40, focusActive = false, disposeViewer = () => {}, refreshViewer = () => {};
  const pagePagination = createSavedPagePagination(() => renderReview());
  const onClick = (event) => handleClick(event);
  const onChange = (event) => handleChange(event);
  const onPointerOver = (event) => showPagePreview(event);
  const onPointerOut = (event) => hidePagePreview(event);
  page.addEventListener("click", onClick);
  page.addEventListener("change", onChange);
  page.addEventListener("pointerover", onPointerOver);
  page.addEventListener("pointerout", onPointerOut);
  const unsubscribe = subscribeContext(load);
  load();

  async function load() {
    const id = ++requestId;
    const { provider, manga } = getContext();
    const work = provider && manga ? `${provider}\u0000${manga}` : "";
    if (work !== activeWork) {
      disposeViewer(); focusActive = false; zoom = 40;
      activeWork = work; mode = "table"; chapter = ""; currentPage = ""; selectedId = ""; panelOpen = false; previewed = false;
      pagePagination.reset();
    }
    if (!provider || !manga) {
      proposals = []; page.innerHTML = "<p role=\"status\">Selecione uma obra para consultar as propostas salvas.</p>"; return;
    }
    page.innerHTML = "<p role=\"status\">Carregando propostas salvas…</p>";
    try {
      proposals = await fetchSavedMergeManualProposals(provider, manga);
      if (id !== requestId) return;
      renderCurrent();
    } catch (error) {
      if (id === requestId) page.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p>`;
    }
  }

  function renderCurrent() { mode === "table" ? renderTable() : renderReview(); }
  function renderTable() {
    disposeViewer(); focusActive = false;
    page.innerHTML = savedProposalTableMarkup(proposals);
  }

  function renderReview() {
    disposeViewer();
    const items = pendingForChapter(chapter), pages = pagesFor(items);
    if (!pages.includes(currentPage)) currentPage = pages[0] || "";
    if (!items.some((item) => item.proposal_id === selectedId)) selectedId = "";
    const { provider, manga } = getContext();
    const chapters = [...new Set(proposals.filter(isPending).map((item) => item.chapter))].sort((a, b) => Number(a) - Number(b));
    page.innerHTML = savedProposalReviewMarkup({ provider, manga, chapter, chapters, currentPage, pages,
      items, selectedId, previewed, zoom, panelOpen });
    pagePagination.render(page.querySelector(".saved-review-page-list"), page.querySelector("[data-page-pagination]"), pages, currentPage);
    const viewer = bindSavedProposalViewer(page, { zoom, activeFocus: focusActive,
      onZoom: (value) => { zoom = value; }, onFocusChange: (value) => { focusActive = value; } });
    disposeViewer = viewer.dispose; refreshViewer = viewer.refresh;
  }

  function handleClick(event) {
    const open = event.target.closest("[data-open-chapter]");
    if (open) { chapter = open.dataset.openChapter; currentPage = ""; selectedId = ""; mode = "review"; panelOpen = false; previewed = false; pagePagination.reset(); renderReview(); return; }
    if (event.target.closest("[data-back-table]")) { mode = "table"; renderTable(); return; }
    const pageButton = event.target.closest("[data-page-name]");
    if (pageButton) { selectPage(pageButton.dataset.pageName); return; }
    if (event.target.closest("[data-focus-prev]")) { movePage(-1); return; }
    if (event.target.closest("[data-focus-next]")) { movePage(1); return; }
    if (event.target.closest("[data-panel-toggle]")) { setPanelOpen(!panelOpen); return; }
    if (event.target.closest("[data-close-panel]")) { setPanelOpen(false); return; }
    if (event.target.closest("[data-preview]")) { previewed = true; updatePreview(); return; }
    if (event.target.closest("[data-apply]")) applySelected();
  }

  function handleChange(event) {
    if (event.target.matches("[data-chapter]")) { chapter = event.target.value; currentPage = ""; selectedId = ""; previewed = false; pagePagination.reset(); renderReview(); }
    if (event.target.matches("[data-page]")) selectPage(event.target.value);
    if (event.target.matches('input[name="saved-proposal"]')) { selectedId = event.target.value; updateSelection(); }
  }

  function selectPage(name) {
    currentPage = name; selectedId = ""; previewed = false;
    pagePagination.show(name, pagesFor(pendingForChapter(chapter)));
    renderReview();
  }

  function movePage(delta) {
    const pages = pagesFor(pendingForChapter(chapter));
    const next = pages[pages.indexOf(currentPage) + delta];
    if (next) selectPage(next);
  }

  function setPanelOpen(open) {
    panelOpen = open;
    const panel = page.querySelector("#saved-proposal-panel"), workspace = page.querySelector(".saved-review-workspace");
    const toggle = page.querySelector("[data-panel-toggle]");
    if (!panel || !workspace || !toggle) return;
    panel.hidden = !open; workspace.classList.toggle("has-proposal-panel", open);
    toggle.setAttribute("aria-expanded", String(open)); toggle.setAttribute("aria-pressed", String(open));
  }

  function updateSelection() {
    const selected = pendingForChapter(chapter).find((item) => item.proposal_id === selectedId);
    page.querySelectorAll(".saved-proposal-option").forEach((option) => {
      const checked = option.querySelector("input").value === selectedId;
      option.classList.toggle("is-selected", checked);
    });
    page.querySelectorAll("[data-preview], [data-apply]").forEach((button) => { button.disabled = !selected; });
    if (previewed) updatePreview();
  }

  function updatePreview() {
    const selected = pendingForChapter(chapter).find((item) => item.proposal_id === selectedId);
    const images = page.querySelector(".saved-review-images");
    if (images) {
      const { provider, manga } = getContext();
      images.innerHTML = savedProposalImagesMarkup({ provider, manga, chapter, currentPage, selected, previewed });
      refreshViewer();
    }
  }

  async function applySelected() {
    if (applying) return;
    const item = pendingForChapter(chapter).find((proposal) => proposal.proposal_id === selectedId);
    if (!item) return;
    const target = { chapter, proposalId: item.proposal_id, ...getContext() };
    applying = true;
    page.querySelector("[data-apply]").disabled = true;
    try {
      const confirmed = await confirmMessage({ title: "Efetivar faixa", message: `A faixa ${item.start} → ${item.end} será confirmada e sairá das pendências. Quando todas as faixas estiverem confirmadas, a composição será validada e publicada em 02_MERGE. Deseja continuar?`, confirmText: "Efetivar" });
      if (!confirmed) return;
      const context = getContext();
      if (context.provider !== target.provider || context.manga !== target.manga || chapter !== target.chapter || selectedId !== target.proposalId) return;
      const result = await applyMergeManualProposal({ provider: target.provider, manga: target.manga, chapter: target.chapter, proposal_id: target.proposalId });
      await showMessage({ title: result.status === "FAIXA_SELECIONADA" ? "Faixa confirmada" : "Composição efetivada", message: result.message });
      if (result.status === "FAIXA_SELECIONADA") { selectedId = ""; currentPage = ""; previewed = false; pagePagination.reset(); }
      else { mode = "table"; panelOpen = false; }
      await load();
    } catch (error) { await showMessage({ title: "Falha ao efetivar faixa", message: error.message }); }
    finally { applying = false; const button = page.querySelector("[data-apply]"); if (button) button.disabled = !selectedId; }
  }

  function showPagePreview(event) {
    const button = event.target.closest("[data-page-name]");
    if (!button || button.contains(event.relatedTarget)) return;
    const preview = page.querySelector("[data-page-preview]"), image = preview.querySelector("img");
    const { provider, manga } = getContext(), rect = button.getBoundingClientRect();
    image.src = mergeManualImageUrl(provider, manga, chapter, button.dataset.pageName);
    preview.querySelector("[data-preview-name]").textContent = button.dataset.pageName;
    preview.hidden = false;
    const sidebar = page.querySelector(".saved-review-pages").getBoundingClientRect();
    const width = preview.offsetWidth || 300, height = preview.offsetHeight || 420;
    const left = sidebar.right + 12 + width <= innerWidth - 8 ? sidebar.right + 12 : sidebar.left - width - 12;
    preview.style.left = `${Math.max(8, Math.min(left, innerWidth - width - 8))}px`;
    preview.style.top = `${Math.max(8, Math.min(rect.top - 24, innerHeight - height - 8))}px`;
  }

  function hidePagePreview(event) {
    const button = event.target.closest("[data-page-name]");
    if (button && !button.contains(event.relatedTarget)) page.querySelector("[data-page-preview]")?.setAttribute("hidden", "");
  }

  return () => {
    requestId += 1; unsubscribe(); page.removeEventListener("click", onClick); page.removeEventListener("change", onChange);
    page.removeEventListener("pointerover", onPointerOver); page.removeEventListener("pointerout", onPointerOut);
    disposeViewer();
  };

  function pendingForChapter(id) { return pendingProposalsForChapter(proposals, id); }
}
