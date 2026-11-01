import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls, createPageSizeControl } from "/_shared/pagination/pagination.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { iconMarkup } from "/_shared/icons/icons.js";

const names = { pending: "A fazer", review: "Divergência", attention: "Verificar imagem", ok: "OK", applied: "Aplicado" };

export function createValidationList({ onExecute, onOpen }) {
  const element = document.createElement("section");
  element.className = "image-validation";
  element.innerHTML = `<header class="image-validation-heading"><h1>Validar Imagens</h1></header>
    <div class="image-validation-panel"><div class="image-validation-toolbar">
      <label><span class="visually-hidden">Buscar capítulo</span><input type="search" placeholder="Cap." data-search></label>
      <div class="image-validation-filters" role="group" aria-label="Filtrar capítulos"></div>
      <button class="btn primary" type="button" data-execute>Executar</button>
    </div><div data-progress></div><p class="image-validation-status" data-status role="status"></p>
    <div data-results></div></div>`;
  const search = element.querySelector("[data-search]");
  const filters = element.querySelector(".image-validation-filters");
  const results = element.querySelector("[data-results]");
  const status = element.querySelector("[data-status]");
  const execute = element.querySelector("[data-execute]");
  const progress = createJobProgress("Validar Imagens");
  element.querySelector("[data-progress]").append(progress.element);
  let rows = [], selected = new Set(), filter = "all", pagination = createPagination();
  let pageSize = createPageSizeControl((size) => {
    pagination = createPagination(size);
    draw();
  });
  let busy = false, mode = "idle", error = "";

  function checkbox(chapter, checked, label, action) {
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = checked;
    box.setAttribute("aria-label", label);
    box.addEventListener("change", () => action(box.checked, chapter));
    return box;
  }

  function draw() {
    const counts = Object.fromEntries(["pending", "review", "attention", "ok", "applied"].map((key) =>
      [key, rows.filter((row) => row.status === key).length]));
    filters.replaceChildren();
    for (const [key, label] of [["all", "Todos"], ["pending", "A fazer"],
      ["review", "Divergências"], ["attention", "Atenção"], ["ok", "OK"], ["applied", "Aplicados"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `image-validation-filter${filter === key ? " active" : ""}`;
      button.setAttribute("aria-pressed", String(filter === key));
      button.textContent = `${label} (${key === "all" ? rows.length : counts[key]})`;
      button.addEventListener("click", () => { filter = key; pagination.reset(); draw(); });
      filters.append(button);
    }
    execute.disabled = busy || !selected.size || mode !== "ready";
    status.hidden = mode === "ready" && rows.length > 0;
    status.textContent = mode === "idle" ? "Selecione um provider e uma obra." :
      mode === "loading" ? "Carregando capítulos…" : mode === "error" ? error :
      rows.length ? "" : "Nenhum capítulo com imagens encontrado.";
    results.replaceChildren();
    if (mode !== "ready") return;
    const matches = rows.filter((row) => (filter === "all" || row.status === filter)
      && row.chapter.toLocaleLowerCase("pt-BR").includes(search.value.trim().toLocaleLowerCase("pt-BR")));
    const page = pagination.select(matches);
    const visible = page.rows.map((row) => row.chapter);
    const columns = [
      { id: "select", header: () => checkbox("", visible.length > 0 && visible.every((ch) => selected.has(ch)),
        "Selecionar capítulos desta página", (checked) => {
          visible.forEach((ch) => checked ? selected.add(ch) : selected.delete(ch)); draw();
        }), render: (row) => checkbox(row.chapter, selected.has(row.chapter),
          `Selecionar capítulo ${row.chapter}`, (checked, ch) => { checked ? selected.add(ch) : selected.delete(ch); draw(); }) },
      { id: "chapter", label: "Capítulo", render: (row) => row.chapter },
      { id: "images", label: "Imagens", render: (row) => row.image_count ?? "—" },
      { id: "width", label: "Largura dominante", render: (row) => row.dominant_width ? `${row.dominant_width} px` : "—" },
      { id: "exceptions", label: "Divergências", render: (row) => row.exceptions ?? "—" },
      { id: "status", label: "Status", render: (row) => {
        const badge = document.createElement("span");
        badge.className = `image-validation-badge is-${row.status}`;
        badge.textContent = names[row.status] || row.status;
        return badge;
      } },
      { id: "view", label: "Visualizar", render: (row) => {
        if (row.status !== "review" || !row.images.length) return "—";
        const button = document.createElement("button");
        button.className = "btn image-validation-eye";
        button.type = "button";
        button.innerHTML = iconMarkup("eye");
        button.setAttribute("aria-label", `Visualizar divergências do capítulo ${row.chapter}`);
        button.title = `Visualizar divergências do capítulo ${row.chapter}`;
        button.addEventListener("click", () => onOpen(row.chapter));
        return button;
      } },
    ];
    results.append(createTable(columns, page.rows, "Validação de imagens", {
      emptyMessage: "Nenhum capítulo neste filtro.",
    }));
    results.append(createPaginationControls(page, (delta) => { pagination.move(delta); draw(); },
      { leading: pageSize.element }));
  }

  function selectReview() { filter = "review"; pagination.reset(); draw(); }
  function resetContext() { filter = "all"; search.value = ""; selected.clear(); pagination.reset(); draw(); }
  function update(next, nextMode = "ready", nextError = "") {
    mode = nextMode; error = nextError; rows = next;
    pagination.reset(); draw();
  }
  function resetSelection() { selected.clear(); draw(); }
  function selectAll() { selected = new Set(rows.map((row) => row.chapter)); draw(); }
  function onSearch() { pagination.reset(); draw(); }
  function requestExecution() { onExecute([...selected]); }
  search.addEventListener("input", onSearch);
  execute.addEventListener("click", requestExecution);
  draw();
  return { element, update, selectReview, resetContext, resetSelection, selectAll,
    setBusy(value, progressState = {}) { busy = value; execute.disabled = busy || !selected.size;
      progress.update({ busy, ...progressState }); },
    dispose() { search.removeEventListener("input", onSearch); execute.removeEventListener("click", requestExecution); } };
}
