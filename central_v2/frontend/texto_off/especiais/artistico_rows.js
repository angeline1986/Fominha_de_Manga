import { createTable } from "/_shared/table/table.js";
import { iconMarkup } from "/_shared/icons/icons.js";
import { artisticDone, artisticKey } from "/texto_off/especiais/artistico_model.js";
import { createSpecialActions } from "/texto_off/especiais/special_worklist_actions.js";

const label = (status) => ({ pending: "Pendente", failed: "Falhou", processed: "Concluído",
  no_change: "Sem alteração" })[status] || status;
const node = (tag, className, content) => {
  const element = document.createElement(tag);
  element.className = className;
  if (content != null) element.textContent = content;
  return element;
};
function iconButton(icon, title, action, disabled = false) {
  const button = node("button", "btn artistico-icon-button");
  button.type = "button"; button.innerHTML = iconMarkup(icon);
  button.title = title; button.setAttribute("aria-label", title);
  button.disabled = disabled;
  if (action) button.addEventListener("click", action);
  return button;
}
function entries(row) { return row.type === "occurrence" ? [row.item] : row.occurrences; }
function statusOf(row) {
  if (row.type === "occurrence") return row.item.status;
  const items = row.occurrences;
  if (items.every(artisticDone)) return "processed";
  if (items.some((item) => item.status === "failed")) return "failed";
  return "pending";
}

export function createArtisticRows(groups, state) {
  const rows = [];
  const pageEligible = groups.flatMap((group) => group.occurrences
    .filter((item) => state.eligible(group.chapter, item) &&
      state.choices.get(artisticKey(group.chapter.chapter, item.page, item.id)) !== "none")
    .map((item) => ({ chapter: group.chapter.chapter, item })));
  for (const group of groups) {
    rows.push({ type: "chapter", chapter: group.chapter.chapter,
      source: group.chapter, occurrences: group.occurrences, pages: group.pages });
    if (!state.openCh.has(group.chapter.chapter)) continue;
    for (const page of group.pages) {
      const pageKey = artisticKey(group.chapter.chapter, page.name, "");
      rows.push({ type: "page", chapter: group.chapter.chapter, source: group.chapter,
        page: page.name, pageKey, occurrences: page.occurrences });
      if (state.openPages.has(pageKey)) {
        for (const item of page.occurrences) rows.push({ type: "occurrence",
          chapter: group.chapter.chapter, page: page.name, source: group.chapter, item,
          ordinal: group.chapter.occurrences.filter((entry) => entry.page === page.name)
            .findIndex((entry) => entry.id === item.id) + 1 });
      }
    }
  }
  function selection(row) {
    const selectable = entries(row).filter((item) => state.eligible(row.source, item) &&
      state.choices.get(artisticKey(row.chapter, item.page, item.id)) !== "none");
    const input = node("input", "artistico-check"); input.type = "checkbox";
    input.disabled = !selectable.length || state.busy();
    const count = selectable.filter((item) => state.selected.has(
      artisticKey(row.chapter, item.page, item.id))).length;
    input.checked = !!selectable.length && count === selectable.length;
    input.indeterminate = count > 0 && count < selectable.length;
    input.setAttribute("aria-label", row.type === "occurrence"
      ? `Selecionar ${row.item.id} em ${row.page}`
      : `Selecionar ocorrências elegíveis ${row.type === "page" ? `da página ${row.page}` : `do capítulo ${row.chapter}`}`);
    if (row.type === "occurrence" && row.item.execution_blocked)
      input.title = row.item.execution_block_reason;
    input.addEventListener("change", () => {
      selectable.forEach((item) => {
        const key = artisticKey(row.chapter, item.page, item.id);
        if (input.checked) state.selected.add(key); else state.selected.delete(key);
      });
      state.draw();
    });
    return input;
  }
  function selectAll() {
    const input = node("input", "artistico-check"); input.type = "checkbox";
    input.setAttribute("aria-label", "Selecionar ocorrências da página de capítulos");
    input.disabled = !pageEligible.length || state.busy();
    const count = pageEligible.filter(({ chapter, item }) => state.selected.has(
      artisticKey(chapter, item.page, item.id))).length;
    input.checked = !!pageEligible.length && count === pageEligible.length;
    input.indeterminate = count > 0 && count < pageEligible.length;
    input.addEventListener("change", () => {
      pageEligible.forEach(({ chapter, item }) => {
        const key = artisticKey(chapter, item.page, item.id);
        if (input.checked) state.selected.add(key); else state.selected.delete(key);
      });
      state.draw();
    });
    return input;
  }
  function name(row) {
    const wrap = node("div", `artistico-name artistico-name--${row.type}`);
    if (row.type !== "occurrence") {
      const opened = row.type === "chapter" ? state.openCh.has(row.chapter)
        : state.openPages.has(row.pageKey);
      const toggle = iconButton(opened ? "collapse" : "expand",
        `${opened ? "Recolher" : "Expandir"} ${row.type === "chapter" ? `capítulo ${row.chapter}` : `página ${row.page}`}`,
        () => { const set = row.type === "chapter" ? state.openCh : state.openPages;
          const key = row.type === "chapter" ? row.chapter : row.pageKey;
          if (set.has(key)) set.delete(key); else set.add(key); state.draw(); });
      toggle.classList.add("artistico-chevron"); toggle.setAttribute("aria-expanded", String(opened));
      wrap.append(toggle);
    } else wrap.insertAdjacentHTML("beforeend", iconMarkup("circle-dot"));
    if (row.type === "page") wrap.insertAdjacentHTML("beforeend", iconMarkup("crop-simple"));
    if (row.type === "occurrence") {
      const trigger = node("button", "artistico-balloon", `Balão ${String(row.ordinal).padStart(2, "0")}`);
      trigger.type = "button"; trigger.title = `${row.item.id} · Prévia do balão`;
      trigger.setAttribute("aria-label", `Prévia do balão ${row.ordinal}: ${row.item.id}`);
      trigger.addEventListener("pointerenter", () => state.preview.show(trigger, row.chapter, row.item, row.ordinal));
      trigger.addEventListener("pointerleave", state.preview.hide);
      trigger.addEventListener("focus", () => state.preview.show(trigger, row.chapter, row.item, row.ordinal));
      trigger.addEventListener("blur", state.preview.hide);
      wrap.append(trigger);
    } else {
      wrap.append(node("strong", "artistico-name-label", row.type === "chapter" ? row.chapter : row.page));
      wrap.append(node("small", "artistico-meta", row.type === "chapter"
        ? `${row.pages.length} pág. · ${row.occurrences.length} ocorrências`
        : `${row.occurrences.length} balões`));
    }
    return wrap;
  }
  function status(row) {
    const value = statusOf(row), badge = node("span", `artistico-status artistico-status--${value}`);
    badge.append(node("i", "artistico-dot"), document.createTextNode(label(value)));
    return badge;
  }
  function progress(row) {
    if (row.type === "occurrence") return node("small", "artistico-progress-text",
      artisticDone(row.item) ? "Processado" : "Aguardando");
    const all = row.occurrences.length, done = row.occurrences.filter(artisticDone).length;
    const wrap = node("span", "artistico-progress");
    const bar = node("span", "artistico-bar"), fill = node("i", "artistico-fill");
    fill.style.width = `${all ? 100 * done / all : 0}%`;
    bar.append(fill); wrap.append(bar, node("small", "artistico-progress-text", `${done}/${all}`));
    return wrap;
  }
  function treatment(row) {
    if (row.type !== "occurrence") return node("span", "artistico-muted", "—");
    const key = artisticKey(row.chapter, row.page, row.item.id);
    const select = node("select", "artistico-treatment");
    select.setAttribute("aria-label", `Tratamento de ${row.item.id} em ${row.page}`);
    select.append(new Option(state.label, state.treatment), new Option("Não selecionar", "none"));
    select.value = state.choices.get(key) || state.treatment;
    select.disabled = state.busy();
    select.addEventListener("change", () => {
      state.choices.set(key, select.value);
      if (select.value === "none") state.selected.delete(key);
      state.draw();
    });
    return select;
  }
  return createTable([
    { id: "select", header: selectAll, render: selection },
    { id: "chapter", label: "CAP.", render: name },
    { id: "status", label: "Situação", render: status },
    { id: "progress", label: "Progresso", render: progress },
    { id: "treatment", label: "Tratamento", render: treatment },
    { id: "actions", label: "Ações", render: (row) => createSpecialActions(row, state) },
  ], rows, `Ocorrências ${state.label} por capítulo e página`, {
    emptyMessage: "Nenhum resultado encontrado.",
    rowClass: (row) => `artistico-row artistico-row--${row.type}`,
  });
}
