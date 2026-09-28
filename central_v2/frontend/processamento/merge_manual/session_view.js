import { mergeManualImageUrl } from "/_app/api/merge_manual.js";
import { iconMarkup } from "/_shared/icons/icons.js";

export function renderMergeManualSession({ row, session, provider, manga, onToggle, onChange, onOpenCuts }) {
  const section = document.createElement("section");
  section.className = "manual-merge-config";
  section.dataset.chapter = row.chapter;
  if (!session.expanded) section.classList.add("is-collapsed");
  if (row.status !== "pending") {
    section.innerHTML = `<div class="manual-merge-config-heading"><div class="manual-merge-title"><h2>Capítulo ${escapeHtml(row.chapter)}</h2><p>${row.status === "resolved" ? "Não há páginas residuais para configurar." : escapeHtml(row.error || "Este capítulo precisa de revisão.")}</p></div><button type="button" class="manual-merge-collapse" aria-expanded="${session.expanded}" aria-label="${session.expanded ? "Minimizar" : "Expandir"} sessão">${iconMarkup(session.expanded ? "collapse" : "expand")}</button></div>`;
    section.querySelector("button").addEventListener("click", onToggle);
    return section;
  }

  const block = row.pending_blocks?.[session.blockIndex];
  if (!block) { section.textContent = "Não há bloco pendente disponível."; return section; }
  const pages = block.pages || [];
  const first = pages.findIndex((page) => page.file === session.start);
  const last = pages.findIndex((page) => page.file === session.end);
  const selected = first >= 0 && last >= first ? pages.slice(first, last + 1) : [];
  const options = (value) => pages.map((page) => `<option value="${escapeHtml(page.file)}" ${page.file === value ? "selected" : ""}>${escapeHtml(page.file)}</option>`).join("");

  section.innerHTML = `
    <div class="manual-merge-config-heading">
      <div class="manual-merge-title"><h2>Configurar intervalo · Cap. ${escapeHtml(row.chapter)}</h2></div>
      <div class="manual-merge-controls">
        ${row.pending_blocks.length > 1 ? `<label>Bloco<select data-block>${row.pending_blocks.map((item, index) => `<option value="${index}" ${index === session.blockIndex ? "selected" : ""}>${index + 1} de ${row.pending_blocks.length} · ${item.page_count} páginas</option>`).join("")}</select></label>` : ""}
        <label><span>Início</span><select data-start>${options(session.start)}</select></label><span class="manual-merge-arrow" aria-hidden="true">→</span>
        <label><span>Fim</span><select data-end>${options(session.end)}</select></label>
        <div class="manual-merge-zoom"><span>Zoom</span><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><output>${session.zoom}%</output><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button></div>
      </div>
      <button type="button" class="manual-merge-collapse" aria-expanded="${session.expanded}" aria-label="${session.expanded ? "Minimizar" : "Expandir"} sessão">${iconMarkup(session.expanded ? "collapse" : "expand")}</button>
    </div>
    <div class="manual-merge-session-body" ${session.expanded ? "" : "hidden"}>
      <div class="manual-merge-thumbnails">${selected.map((page) => `<figure><img loading="lazy" src="${mergeManualImageUrl(provider, manga, row.chapter, page.file)}" alt="Prévia de ${escapeHtml(page.file)}" style="height:${session.zoom}px"><figcaption>${escapeHtml(page.file)}</figcaption></figure>`).join("")}</div>
      <div class="manual-merge-footer"><p>Faixa selecionada · ${selected.length} imagem(ns)</p><div><button type="button" class="manual-merge-cancel" data-cancel>Cancelar</button><button type="button" class="manual-merge-next" data-next>Submeter a Novos Cortes →</button></div></div>
    </div>
  `;

  section.querySelector(".manual-merge-collapse").addEventListener("click", onToggle);
  if (!session.expanded) return section;
  section.querySelector("[data-cancel]").addEventListener("click", onToggle);
  section.querySelector("[data-start]").addEventListener("change", (event) => {
    const next = { ...session, start: event.target.value };
    if (pages.findIndex((item) => item.file === next.start) > pages.findIndex((item) => item.file === next.end)) next.end = next.start;
    onChange(next);
  });
  section.querySelector("[data-end]").addEventListener("change", (event) => {
    const next = { ...session, end: event.target.value };
    if (pages.findIndex((item) => item.file === next.end) < pages.findIndex((item) => item.file === next.start)) next.start = next.end;
    onChange(next);
  });
  section.querySelector("[data-block]")?.addEventListener("change", (event) => {
    const blockIndex = Number(event.target.value);
    const nextBlock = row.pending_blocks[blockIndex];
    onChange({ ...session, blockIndex, start: nextBlock.first_page, end: nextBlock.last_page });
  });
  section.querySelectorAll("[data-zoom]").forEach((button) => button.addEventListener("click", () => {
    const delta = button.dataset.zoom === "+" ? 16 : -16;
    onChange({ ...session, zoom: Math.max(64, Math.min(240, session.zoom + delta)) });
  }));
  section.querySelector("[data-next]").addEventListener("click", () => onOpenCuts({
    chapter: row.chapter, blockId: block.id, start: session.start, end: session.end, pendingBlock: block,
  }));
  return section;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
