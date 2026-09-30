import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergedTextoff, startMergedSpecialTextoff, waitForTextoffJob } from "/_app/api/textoff.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createTable } from "/_shared/table/table.js";
import { createPagination } from "/_shared/pagination/model.js";
import { createPaginationControls } from "/_shared/pagination/pagination.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

const titles = {
  IV: "Auto-Cleaner — Passo 3: Transparência Normal",
  V: "Auto-Cleaner — Passo 4: Transparência Legada",
};
const descriptions = {
  IV: "Aplicação da variante padrão de transparência.",
  V: "Processamento isolado com o algoritmo legado.",
};
const FILTERS = [["all", "Todos"], ["ready", "Nível I íntegro"], ["missing", "Nível I ausente"]];

export function renderSpecial(container, level) {
  let disposed = false, rows = [], request, filter = "ready";
  const selected = new Set(), pagination = createPagination();
  const root = document.createElement("section");
  root.className = "auto-merge-page textoff-merged-page";
  root.innerHTML = `<header><h1 class="textoff-page-title-hint" data-tooltip="${descriptions[level]}" tabindex="0" aria-description="${descriptions[level]}">${titles[level]}</h1></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span><input type="search" data-query placeholder="Buscar capítulo..."></label>
      <div class="auto-merge-filters" role="group" aria-label="Filtrar capítulos"></div>
      <button class="auto-merge-execute" type="button" data-run>Executar Nível ${level}</button>
    </div>
    <p class="auto-merge-status" data-status role="status" aria-live="polite"></p>
    <div class="auto-merge-results" data-results></div>`;
  container.replaceChildren(root);
  const query = root.querySelector("[data-query]"), filters = root.querySelector(".auto-merge-filters");
  const results = root.querySelector("[data-results]"), status = root.querySelector("[data-status]");
  const execute = root.querySelector("[data-run]"), progress = createJobProgress(`Texto Off Merged Nível ${level}`);
  root.querySelector(".auto-merge-toolbar").after(progress.element);

  function draw() {
    filters.replaceChildren();
    FILTERS.forEach(([key, label]) => {
      const count = rows.filter((row) => key === "all" || (key === "ready") === row.level1_ready).length;
      const button = document.createElement("button");
      button.className = "auto-merge-filter-button";
      button.type = "button"; button.textContent = `${label} (${count})`;
      button.classList.toggle("active", filter === key);
      button.setAttribute("aria-pressed", String(filter === key));
      button.addEventListener("click", () => { filter = key; pagination.reset(); draw(); });
      filters.append(button);
    });
    const term = query.value.trim().toLocaleLowerCase("pt-BR");
    const visible = rows.filter((row) => row.chapter.toLocaleLowerCase("pt-BR").includes(term)
      && (filter === "all" || (filter === "ready") === row.level1_ready));
    const page = pagination.select(visible);
    const eligible = page.rows.filter((row) => row.level1_ready).map((row) => row.chapter);
    const columns = [
      { id: "select", header: () => checkbox("Selecionar capítulos elegíveis desta página", eligible.length > 0
        && eligible.every((chapter) => selected.has(chapter)), (checked) => {
        eligible.forEach((chapter) => checked ? selected.add(chapter) : selected.delete(chapter)); draw();
      }), render: (row) => checkbox(`Selecionar ${row.chapter}`, selected.has(row.chapter), (checked) => {
        checked ? selected.add(row.chapter) : selected.delete(row.chapter); draw();
      }) },
      { id: "chapter", label: "Cap.", render: (row) => row.chapter },
      { id: "pages", label: "Páginas", render: (row) => row.level1_pages?.length || 0 },
      { id: "availability", label: "Disponibilidade", render: (row) => row.level1_ready ? "Nível I íntegro" : "Execute o Nível I" },
    ];
    results.replaceChildren(createTable(columns, page.rows, `Capítulos elegíveis para Nível ${level}`, {
      emptyMessage: "Nenhum capítulo com Nível I íntegro. Execute o Nível I primeiro.",
    }));
    if (visible.length) results.append(createPaginationControls(page, (delta) => { pagination.move(delta); draw(); }));
    status.textContent = rows.length ? "" : "Selecione uma obra com MERGE válido para consultar os capítulos.";
    status.hidden = Boolean(rows.length);
    execute.disabled = selected.size === 0;
  }

  async function load() {
    const { provider, manga } = getContext();
    if (!provider || !manga) { rows = []; draw(); return; }
    request?.abort(); request = new AbortController();
    try {
      const data = await fetchMergedTextoff(provider, manga, request.signal, level);
      if (!disposed) { rows = data.chapters || []; draw(); }
    } catch (error) {
      if (!disposed && error.name !== "AbortError") { rows = []; status.textContent = error.message; status.hidden = false; }
    }
  }

  async function run() {
    const chapters = [...selected];
    if (!chapters.length) return showMessage({ title: "Sem capítulo elegível", message: "Selecione capítulos com Nível I íntegro." });
    if (!await confirmMessage({ title: `Executar Nível ${level}`, message: `${chapters.length} capítulo(s) partirão do Nível I.`, confirmText: "Executar" })) return;
    try {
      const { provider, manga } = getContext();
      const { job } = await startMergedSpecialTextoff(provider, manga, chapters, level);
      const output = await waitForTextoffJob(job, progress.update);
      await showOperationSummary({ title: `Nível ${level} concluído`, summary: { headline: `${output.length} capítulo(s)`,
        items: output.map((item) => ({ chapter: item.chapter, status: item.status,
          count: `${item.pages?.length || 0} imagem(ns)`, warning: item.status !== "ok",
          details: [{ label: "Resultado", value: item.error || "Execução registrada para revisão visual." }] })) } });
    } catch (error) { await showMessage({ title: `Falha no Nível ${level}`, message: error.message }); }
  }

  const onQuery = () => { pagination.reset(); draw(); };
  query.addEventListener("input", onQuery);
  execute.addEventListener("click", run);
  const unsubscribe = subscribeContext(load);
  load();
  return () => { disposed = true; request?.abort(); unsubscribe(); query.removeEventListener("input", onQuery); root.remove(); };
}

function checkbox(label, checked, onChange) {
  const input = document.createElement("input");
  input.type = "checkbox"; input.checked = checked; input.setAttribute("aria-label", label);
  input.addEventListener("change", () => onChange(input.checked));
  return input;
}
