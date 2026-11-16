import { escapeHtml } from "/_shared/dom/sanitize.js";
import { iconMarkup } from "/_shared/icons/icons.js";

export function savedProposalTableMarkup(proposals) {
  const groups = Map.groupBy ? Map.groupBy(proposals, (item) => item.chapter)
    : proposals.reduce((map, item) => map.set(item.chapter, [...(map.get(item.chapter) || []), item]), new Map());
  const rows = [...groups].map(([chapter, items]) => {
    const pending = items.filter((item) => item.status === "PROPOSTA_GERADA").length;
    const selected = items.filter((item) => item.status === "FAIXA_SELECIONADA").length;
    const applied = items.filter((item) => item.status === "EFETIVADO").length;
    const latest = items[0]?.created_at ? new Date(items[0].created_at).toLocaleString("pt-BR") : "—";
    return `<tr><td>Cap. ${escapeHtml(chapter)}</td><td>${pending}</td><td>${selected || "—"}</td><td>${applied || "—"}</td><td>${escapeHtml(latest)}</td>
      <td><button type="button" class="btn saved-proposal-open" data-open-chapter="${escapeHtml(chapter)}" aria-label="Ver páginas pendentes do capítulo ${escapeHtml(chapter)}" ${pending ? "" : "disabled"}>${iconMarkup("eye")}</button></td></tr>`;
  }).join("");
  return `<h1>Propostas Salvas</h1><p class="saved-proposal-subtitle">Consulte as faixas pendentes e confirmadas por capítulo.</p>
    <div class="saved-proposal-table-wrap"><table class="data-table"><thead><tr><th>Capítulo</th><th>Pendentes</th><th>Faixas confirmadas</th><th>Publicadas</th><th>Última atualização</th><th>Ação</th></tr></thead>
    <tbody>${rows || "<tr><td colspan=\"6\">Nenhuma proposta salva para esta obra.</td></tr>"}</tbody></table></div>`;
}
