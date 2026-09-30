import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchMergedTextoff, startMergedSpecialTextoff, waitForTextoffJob } from "/_app/api/textoff.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createTable } from "/_shared/table/table.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

const labels = { IV: "Transparência normal", V: "Transparência Legado" };

export function renderSpecial(container, level) {
  let disposed = false;
  const selectedChapters = new Set();
  const root = document.createElement("section");
  root.className = "auto-merge-page textoff-merged-page";
  root.innerHTML = `<header><h1>Texto Off — Merged Nível ${level}: ${labels[level]}</h1></header>
    <p class="textoff-level-description">Disponível após um Nível I íntegro. Os resultados são experimentais e não substituem os arquivos oficiais.</p>
    <section class="textoff-special-toolbar" aria-label="Seleção da execução">
      <div><strong>Capítulos elegíveis</strong><p>Selecione um ou mais capítulos com Nível I íntegro.</p></div>
      <div class="textoff-special-actions"><button type="button" data-select-all>Selecionar todos</button>
      <button type="button" data-clear-selection>Limpar seleção</button>
      <button type="button" class="textoff-special-run" data-run>Executar Nível ${level}</button></div>
    </section>
    <p data-status role="status" aria-live="polite"></p>
    <div data-results></div>`;
  container.replaceChildren(root);
  const results = root.querySelector("[data-results]"), status = root.querySelector("[data-status]");
  const progress = createJobProgress(`Texto Off Merged Nível ${level}`);
  root.querySelector("[data-run]").after(progress.element);
  let rows = [], request;

  function showRows() {
    const eligible = rows.filter((row) => row.level1_ready);
    const columns = [{ label: "Selecionar", render: (row) => {
      const input = document.createElement("input"); input.type = "checkbox";
      input.checked = selectedChapters.has(row.chapter); input.setAttribute("aria-label", `Selecionar ${row.chapter}`);
      input.addEventListener("change", () => input.checked ? selectedChapters.add(row.chapter) : selectedChapters.delete(row.chapter));
      return input;
    }}];
    columns.push(
      { label: "Capítulo", render: (row) => row.chapter },
      { label: "Disponibilidade", render: () => "Nível I íntegro" },
      { label: "Páginas", render: (row) => row.level1_pages?.length || 0 },
    );
    results.replaceChildren(createTable(columns, eligible, `Capítulos elegíveis para Nível ${level}`, { emptyMessage: "Nenhum capítulo com Nível I íntegro. Execute o Nível I primeiro." }));
  }

  root.querySelector("[data-select-all]").addEventListener("click", () => {
    rows.filter((row) => row.level1_ready).forEach((row) => selectedChapters.add(row.chapter));
    showRows();
  });
  root.querySelector("[data-clear-selection]").addEventListener("click", () => {
    selectedChapters.clear(); showRows();
  });

  root.querySelector("[data-run]").addEventListener("click", async () => {
    const selected = [...selectedChapters];
    if (!selected.filter(Boolean).length) return showMessage({ title: "Sem capítulo elegível", message: "Execute o Nível I primeiro." });
    if (!await confirmMessage({ title: `Executar Nível ${level}`, message: `${selected.length} capítulo(s) partirão do Nível I.`, confirmText: "Executar" })) return;
    try {
      const { job } = await startMergedSpecialTextoff(getContext().provider, getContext().manga, selected, level);
      const result = await waitForTextoffJob(job, progress.update);
      await showOperationSummary({ title: `Nível ${level} concluído`, summary: {
        headline: `${result.length} capítulo(s)`, items: result.map((item) => ({ chapter: item.chapter,
          status: item.status, count: `${item.pages?.length || 0} imagem(ns)`, warning: item.status !== "ok",
          details: [{ label: "Resultado", value: item.error || "Execução registrada para revisão visual." }] })) } });
    } catch (error) { await showMessage({ title: `Falha no Nível ${level}`, message: error.message }); }
  });

  async function load() {
    const { provider, manga } = getContext();
    if (!provider || !manga) return;
    request?.abort(); request = new AbortController();
    try { const value = await fetchMergedTextoff(provider, manga, request.signal, level);
      if (!disposed) { rows = value.chapters || []; showRows(); }
    } catch (error) { if (!disposed && error.name !== "AbortError") status.textContent = error.message; }
  }
  const unsubscribe = subscribeContext(load); load();
  return () => { disposed = true; request?.abort(); unsubscribe(); root.remove(); };
}
