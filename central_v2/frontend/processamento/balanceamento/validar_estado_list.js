import { balanceamentoImageUrl } from "/_app/api/balanceamento.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";

export function createBalanceMergeList({ onEvent }) {
  const element = document.createElement("aside");
  element.className = "balance-validation-sidebar";
  element.innerHTML = `<div class="balance-sidebar-heading"><div class="balance-sidebar-title"><h2>Merges do capítulo</h2><label class="balance-chapter-picker"><span class="visually-hidden">Capítulo</span><select data-chapter aria-label="Selecionar capítulo"></select></label></div><button class="btn" type="button" data-refresh>Atualizar</button></div>
    <div class="balance-list-controls"><div data-filters></div><div data-view-mode aria-label="Modo de distribuição"><button type="button" data-mode="bars" aria-label="Exibir barras" aria-pressed="true"><img src="/_shared/icons/chart-simple-solid-full.svg" alt="" aria-hidden="true"></button><button type="button" data-mode="pixels" aria-label="Exibir pixels" aria-pressed="false">px</button></div></div>
    <div class="balance-list-heading"><strong>Distribuição proporcional</strong><button type="button" data-select-all>Marcar todos</button></div>
    <div class="balance-merge-list" data-list></div><div data-pagination></div>
    <footer class="balance-list-footer"><span data-count></span><button class="btn primary" type="button" data-submit disabled>Submeter a Novos Cortes →</button></footer>
    <div class="balance-hover-preview" role="tooltip" hidden><img alt=""></div>`;
  const list = element.querySelector("[data-list]");
  const preview = element.querySelector(".balance-hover-preview");
  document.body.append(preview);
  const pagination = createPagination();
  let state = {};
  let selected = new Set();
  let mode = "bars";
  let filter = "all";
  element.addEventListener("click", onClick);
  element.addEventListener("change", onChange);
  list.addEventListener("pointerover", onPointerOver);
  list.addEventListener("pointerout", onPointerOut);

  function draw() {
    const merges = state.chapter?.merges || [];
    const deviations = new Set((state.chapter?.issues || []).map((item) => item.file));
    const visible = merges.filter((item) => filter === "all" || deviations.has(item.file));
    const page = pagination.select(visible);
    const maxHeight = Math.max(1, ...merges.map((item) => Number(item.height) || 0));
    element.querySelector("[data-chapter]").value = state.chapter ? String(state.chapter.chapter) : "";
    element.querySelector("[data-filters]").innerHTML = `<button type="button" data-filter="all" aria-pressed="${filter === "all"}">Todos (${merges.length})</button><button type="button" data-filter="deviations" aria-pressed="${filter === "deviations"}">Desvios (${deviations.size})</button>`;
    element.querySelectorAll("[data-mode]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.mode === mode)));
    list.replaceChildren();
    for (const item of page.rows) {
      const isDeviation = deviations.has(item.file);
      const isError = item.status === "ERRO";
      const height = Number(item.height);
      const hasHeight = Number.isFinite(height) && height > 0;
      const row = document.createElement("label");
      row.className = `balance-merge-item ${isError ? "is-error" : isDeviation ? "is-short" : "is-ideal"} ${selected.has(item.file) ? "is-selected" : ""}`;
      row.dataset.file = item.file;
      row.dataset.height = hasHeight ? String(height) : "";
      row.dataset.status = isDeviation ? "Desvio de altura" : isError ? "Erro de leitura" : "Dentro da regra";
      row.dataset.src = balanceamentoImageUrl(state.provider, state.manga, state.chapter?.chapter || "", item.file, "merge");
      row.innerHTML = `<span class="balance-check-wrap"><input type="checkbox" data-merge="${escapeHtml(item.file)}" ${selected.has(item.file) ? "checked" : ""} aria-label="Selecionar ${escapeHtml(item.file)}"></span><span class="balance-merge-data"><span class="balance-merge-name" title="${escapeHtml(item.file)}">${escapeHtml(item.file)}</span><span class="balance-merge-values"><span class="balance-bar-track"><span style="width:${hasHeight ? Math.min(100, 100 * height / maxHeight) : 0}%"></span></span><span class="balance-pixel-value">${hasHeight ? `${height.toLocaleString("pt-BR")} px` : "—"}</span></span></span><span class="balance-merge-status">${isDeviation ? "Desvio" : isError ? "Erro" : "OK"}</span>`;
      list.append(row);
    }
    const pager = element.querySelector("[data-pagination]");
    pager.replaceChildren(createPaginationControls(page, (delta) => { pagination.move(delta); draw(); }));
    const contiguous = isContiguous(merges, selected);
    element.querySelector("[data-count]").textContent = `${selected.size} merge${selected.size === 1 ? "" : "s"} selecionado${selected.size === 1 ? "" : "s"}`;
    const submit = element.querySelector("[data-submit]");
    submit.disabled = selected.size < 2 || !contiguous;
    submit.title = selected.size < 2 ? "Selecione pelo menos dois merges" : contiguous ? "Abrir Novos Cortes" : "Selecione merges contíguos";
    element.classList.toggle("is-pixel-mode", mode === "pixels");
    element.querySelector("[data-select-all]").disabled = !merges.length;
  }

  function onClick(event) {
    const filterButton = event.target.closest("[data-filter]");
    if (filterButton) { filter = filterButton.dataset.filter; pagination.reset(); draw(); return; }
    const modeButton = event.target.closest("[data-mode]");
    if (modeButton) { mode = modeButton.dataset.mode; draw(); return; }
    if (event.target.closest("[data-select-all]")) { selected = new Set((state.chapter?.merges || []).map((item) => item.file)); draw(); onEvent("selection", selected); return; }
    if (event.target.closest("[data-refresh]")) onEvent("refresh");
    if (event.target.closest("[data-submit]")) onEvent("submit", [...selected]);
  }

  function onChange(event) {
    const checkbox = event.target.closest("[data-merge]");
    if (!checkbox) return;
    if (checkbox.checked) selected.add(checkbox.dataset.merge); else selected.delete(checkbox.dataset.merge);
    draw(); onEvent("selection", selected);
  }

  function onPointerOver(event) {
    const row = event.target.closest(".balance-merge-item");
    if (!row || row.contains(event.relatedTarget)) return;
    const rect = row.getBoundingClientRect();
    const image = preview.querySelector("img");
    image.src = row.dataset.src; image.alt = row.dataset.file;
    preview.hidden = false;
    const width = preview.getBoundingClientRect().width || 220;
    const height = preview.getBoundingClientRect().height || 280;
    preview.style.left = `${rect.right + width + 12 < innerWidth ? rect.right + 12 : Math.max(8, rect.left - width - 12)}px`;
    preview.style.top = `${Math.max(8, Math.min(rect.top, innerHeight - height - 8))}px`;
  }

  function onPointerOut(event) {
    const row = event.target.closest(".balance-merge-item");
    if (row && !row.contains(event.relatedTarget)) preview.hidden = true;
  }

  return {
    element,
    update(next, nextSelected) { state = next; selected = new Set(nextSelected || []); draw(); },
    dispose() { element.removeEventListener("click", onClick); element.removeEventListener("change", onChange); list.removeEventListener("pointerover", onPointerOver); list.removeEventListener("pointerout", onPointerOut); preview.remove(); },
  };
}

function isContiguous(rows, selected) {
  const indexes = rows.map((row, index) => selected.has(row.file) ? index : -1).filter((index) => index >= 0);
  return indexes.length < 2 || indexes[indexes.length - 1] - indexes[0] + 1 === indexes.length;
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
