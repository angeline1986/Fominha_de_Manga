import { iconMarkup } from "/_shared/icons/icons.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls, createPageSizeControl } from "/_shared/pagination/pagination.js";

function check(label, checked, disabled, onChange) {
  const element = document.createElement("input");
  element.type = "checkbox"; element.checked = checked; element.disabled = disabled;
  element.setAttribute("aria-label", label);
  element.addEventListener("change", () => onChange(element.checked));
  return element;
}

function chapterName(row, expanded, toggle) {
  const wrap = document.createElement("div");
  wrap.className = "artistico-name artistico-name--chapter solid-chapter-name";
  if (row.pages.length) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn solid-expand";
    button.innerHTML = iconMarkup(expanded ? "collapse" : "expand");
    button.setAttribute("aria-expanded", String(expanded));
    button.setAttribute("aria-label", `${expanded ? "Recolher" : "Expandir"} capítulo ${row.chapter}`);
    button.addEventListener("click", toggle); wrap.append(button);
  }
  const label = document.createElement("strong"); label.className = "artistico-name-label"; label.textContent = row.chapter;
  const detail = document.createElement("span"); detail.className = "artistico-meta solid-row-detail";
  detail.textContent = `${row.pages.length} pág. · ${row.regions} ocorrências`;
  const text = document.createElement("span"); text.className = "solid-row-label";
  text.append(label, detail); wrap.append(text); return wrap;
}

function pageName(row, expanded, toggle) {
  const wrap = document.createElement("div");
  wrap.className = "artistico-name artistico-name--page solid-page-name";
  if (row.regions > 0) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn solid-expand";
    button.innerHTML = iconMarkup(expanded ? "collapse" : "expand");
    button.setAttribute("aria-expanded", String(expanded));
    button.setAttribute("aria-label", `${expanded ? "Recolher" : "Expandir"} ${row.name}`);
    button.addEventListener("click", toggle); wrap.append(button);
  }
  wrap.insertAdjacentHTML("beforeend", iconMarkup("crop-simple"));
  const name = document.createElement("strong"); name.className = "artistico-name-label"; name.textContent = row.name;
  const detail = document.createElement("span"); detail.className = "artistico-meta solid-row-detail";
  detail.textContent = `${row.regions} ${row.regions === 1 ? "balão sólido" : "balões sólidos"}`;
  wrap.append(name, detail); return wrap;
}

function areaName(row) {
  const wrap = document.createElement("div");
  wrap.className = "artistico-name artistico-name--occurrence solid-area-name";
  wrap.insertAdjacentHTML("beforeend", iconMarkup("circle-dot"));
  const number = Number.isInteger(row.number) && row.number > 0 ? row.number : row.ordinal;
  const name = document.createElement("button");
  name.type = "button"; name.className = "artistico-balloon solid-area-preview-trigger";
  name.textContent = `Balão ${String(number).padStart(2, "0")}`;
  name.title = `Prévia do Balão ${String(number).padStart(2, "0")}`;
  name.setAttribute("aria-label", `Prévia do Balão ${number}`);
  name.addEventListener("pointerenter", () => row.preview?.show(name, row));
  name.addEventListener("pointerleave", () => row.preview?.hide());
  name.addEventListener("focus", () => row.preview?.show(name, row));
  name.addEventListener("blur", () => row.preview?.hide());
  const label = document.createElement("span"); label.className = "solid-row-detail";
  label.textContent = "Branco sólido";
  wrap.append(name, label); return wrap;
}

function rowStatus(row) {
  if (row.rowType === "area" || row.rowType === "area-state") return "—";
  if (row.rowType === "page") {
    if (!row.processed) return ["Pendente", "pending"];
    return row.outdated === true ? ["Pendente", "pending"] : ["Prévia disponível", "ready"];
  }
  const done = row.pages.filter((item) => item.processed).length;
  if (done && row.pages.some((item) => item.outdated === true)) return ["Pendente", "pending"];
  if (done === row.pages.length) return ["Prévia disponível", "ready"];
  return done ? ["Parcial", "partial"] : ["Pendente", "pending"];
}

function statusMark(row) {
  const value = rowStatus(row);
  if (typeof value === "string") return value;
  const [label, state] = value;
  const mark = document.createElement("span"); mark.className = `solid-status is-${state}`;
  const dot = document.createElement("i"); dot.setAttribute("aria-hidden", "true");
  const text = document.createElement("span"); text.textContent = label;
  mark.append(dot, text); return mark;
}

function progressMark(row) {
  if (row.rowType === "area" || row.rowType === "area-state") return "—";
  const total = row.rowType === "page" ? 1 : row.pages.length;
  const done = row.rowType === "page" ? Number(row.processed)
    : row.pages.filter((item) => item.processed).length;
  const wrap = document.createElement("div"); wrap.className = "solid-progress";
  const track = document.createElement("progress"); track.className = "solid-progress-track";
  track.max = total || 1; track.value = done;
  track.setAttribute("aria-label", `${done} de ${total} páginas com prévia`);
  const label = document.createElement("span"); label.textContent = `${done}/${total}`;
  wrap.append(track, label); return wrap;
}

function pageActions(row, busy, inspect, run) {
  const wrap = document.createElement("div"); wrap.className = "solid-row-actions";
  wrap.append(viewButton(row, inspect));
  if (!row.processed) return wrap;
  const button = document.createElement("button");
  button.type = "button"; button.className = "btn artistico-icon-button solid-page-rerun";
  button.innerHTML = iconMarkup("sync"); button.disabled = busy || !row.result_sha256;
  button.title = "Reexecutar somente esta página; a prévia anterior será arquivada.";
  button.setAttribute("aria-label", `Reexecutar Sólidos somente na página ${row.name}`);
  button.addEventListener("click", () => run(row)); wrap.append(button); return wrap;
}

export function createSolidTable(container, actions) {
  let pagination = createPagination(13);
  const sizeControl = createPageSizeControl((size) => {
    pagination = createPagination(size); actions.changePage(0);
  });
  const expandedChapters = new Set(), expandedPages = new Set();
  const pageKey = (chapter, name) => `${chapter}\u0000${name}`;
  return { draw(rows, selected, page, busy) {
    container.replaceChildren(); pagination.reset();
    for (let i = 0; i < page; i++) pagination.move(1);
    const view = pagination.select(rows);
    const waiting = [];
    const visible = view.rows.flatMap((chapter) => {
      const pages = chapter.displayPages || chapter.pages;
      const children = expandedChapters.has(chapter.chapter) ? pages.flatMap((item) => {
        const page = { ...item, chapter: chapter.chapter, rowType: "page" };
        if (!expandedPages.has(pageKey(chapter.chapter, item.name))) return [page];
        if (!item.areasState || item.areasState === "idle") waiting.push(page);
        if (item.areasState === "loading") return [page, areaMessage(page, "Carregando áreas sólidas…")];
        if (item.areasState === "error") return [page, areaMessage(page,
          "Não foi possível carregar as áreas. Recolha e reabra a página para tentar novamente.")];
        if (!item.areas?.length) return [page, areaMessage(page, "Nenhum balão sólido aprovado no Check.")];
        return [page, ...item.areas.map((area, index) => ({ ...area, ordinal: index + 1,
          chapter: chapter.chapter, page: item.name, rowType: "area", preview: actions.preview }))];
      }) : [];
      return [{ ...chapter, rowType: "chapter" }, ...children];
    });
    const columns = [
      { id: "select", header: () => check("Selecionar todos desta página",
          view.rows.some((row) => !row.processed)
            && view.rows.filter((row) => !row.processed).every((row) => selected.has(row.chapter)),
          busy || !view.rows.some((row) => !row.processed), (value) =>
            actions.onSelectPage(view.rows.filter((row) => !row.processed)
              .map((row) => row.chapter), value)),
        render: (row) => row.rowType !== "chapter" ? "" : check(
          `Selecionar capítulo ${row.chapter}`, selected.has(row.chapter), busy || row.processed,
          (value) => actions.onSelect(row.chapter, value)) },
      { id: "chapter", label: "CAP.", render: (row) => {
        if (row.rowType === "area") return areaName(row);
        if (row.rowType === "area-state") return row.message;
        if (row.rowType === "page") return pageName(row,
          expandedPages.has(pageKey(row.chapter, row.name)), () => {
            const key = pageKey(row.chapter, row.name);
            expandedPages.has(key) ? expandedPages.delete(key) : expandedPages.add(key);
            if (expandedPages.has(key)) actions.loadAreas(row);
            actions.redraw();
          });
        return chapterName(row, expandedChapters.has(row.chapter), () => {
            expandedChapters.has(row.chapter) ? expandedChapters.delete(row.chapter) : expandedChapters.add(row.chapter);
            actions.redraw();
          }); } },
      { id: "status", label: "SITUAÇÃO", render: statusMark },
      { id: "progress", label: "PROGRESSO", render: progressMark },
      { id: "actions", label: "AÇÕES", render: (row) => row.rowType === "page"
          ? pageActions(row, busy, actions.inspect, actions.reexecutePage)
          : row.rowType === "chapter" ? viewButton(row, actions.inspect) : "—" },
    ];
    const result = createTable(columns, visible, "Capítulos e páginas do Auto-Cleaner Sólidos", {
      emptyMessage: "Nenhum capítulo corresponde ao filtro.",
      rowClass: (row) => `solid-${row.rowType}-row`,
    });
    result.classList.add("solid-table"); container.append(result);
    container.append(createPaginationControls(view, (delta) => actions.changePage(page + delta),
      { leading: sizeControl.element }));
    waiting.forEach(actions.loadAreas);
  } };
}

function areaMessage(row, message) {
  return { chapter: row.chapter, name: row.name, rowType: "area-state", message };
}

function viewButton(row, inspect) {
  const button = document.createElement("button");
  button.type = "button"; button.className = "btn comparison-open artistico-icon-button";
  const target = row.rowType === "page" ? `página ${row.name} do capítulo ${row.chapter}`
    : `capítulo ${row.chapter}`;
  button.title = `Visualizar ${target}`;
  button.setAttribute("aria-label", `Visualizar ${target}`);
  button.innerHTML = iconMarkup("eye"); button.disabled = !row.processed;
  button.addEventListener("click", () => inspect(row)); return button;
}
