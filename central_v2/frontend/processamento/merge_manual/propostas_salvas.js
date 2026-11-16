import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchSavedMergeManualProposals } from "/_app/api/merge_manual.js";
import { setMergeManualSelection } from "/_app/state/merge_manual.js";
import { escapeHtml } from "/_shared/dom/sanitize.js";

export function render(container) {
  const page = document.createElement("section");
  page.className = "saved-manual-proposals";
  container.replaceChildren(page);
  let requestId = 0;
  let proposals = [];
  const onClick = (event) => {
    const button = event.target.closest("[data-proposal]");
    if (!button) return;
    const item = proposals[Number(button.dataset.proposal)];
    const { provider, manga } = getContext();
    if (!item || item.status !== "PROPOSTA_GERADA" || !provider || !manga) return;
    setMergeManualSelection({ provider, manga, chapter: item.chapter,
      proposal: item.proposal, returnTo: "merge-manual-saved" });
    container.dispatchEvent(new CustomEvent("menu:action", {
      bubbles: true, detail: { action: "merge-manual-result" },
    }));
  };
  page.addEventListener("click", onClick);
  const unsubscribe = subscribeContext(load);
  load();

  async function load() {
    const id = ++requestId;
    const { provider, manga } = getContext();
    if (!provider || !manga) {
      proposals = [];
      page.innerHTML = "<p role=\"status\">Selecione uma obra para consultar as propostas salvas.</p>";
      return;
    }
    page.innerHTML = "<p role=\"status\">Carregando propostas salvas…</p>";
    try {
      proposals = await fetchSavedMergeManualProposals(provider, manga);
      if (id !== requestId) return;
      page.innerHTML = proposals.length ? tableMarkup(proposals) :
        "<p role=\"status\">Nenhuma proposta salva para esta obra.</p>";
    } catch (error) {
      if (id === requestId) page.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p>`;
    }
  }

  return () => { requestId += 1; unsubscribe(); page.removeEventListener("click", onClick); };
}

function tableMarkup(items) {
  const rows = items.map((item, index) => {
    const applied = item.status === "EFETIVADO";
    const range = item.start && item.end ? `${item.start} → ${item.end}` : "Faixa registrada";
    const date = item.created_at ? new Date(item.created_at).toLocaleString("pt-BR") : "—";
    return `<tr><td>Cap. ${escapeHtml(item.chapter)}</td><td>${escapeHtml(range)}</td>
      <td>${item.outputs} merge(s)</td><td>${escapeHtml(date)}</td>
      <td><span class="saved-proposal-status ${applied ? "applied" : "pending"}">${applied ? "Efetivada" : "Pendente"}</span></td>
      <td>${applied ? "—" : `<button type="button" class="btn saved-proposal-review" data-proposal="${index}">Revisar e efetivar</button>`}</td></tr>`;
  }).join("");
  return `<div class="saved-proposal-table-wrap"><table class="data-table"><thead><tr>
    <th>Capítulo</th><th>Faixa</th><th>Saídas</th><th>Criada em</th><th>Status</th><th>Ação</th>
    </tr></thead><tbody>${rows}</tbody></table></div>`;
}
