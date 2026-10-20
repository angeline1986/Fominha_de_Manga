import { getContext, subscribeContext } from "/_app/state/context.js";
import { invalidateCleanerOverview } from "/_app/state/cleaner_revision.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createSolidTable } from "/texto_off/solidos/table.js";
import { createSolidInspector } from "/texto_off/solidos/inspector.js";
import { confirmMessage } from "/_shared/messages/messages.js";
import { createSolidAreaLoader } from "/texto_off/solidos/area_loader.js";
import { createSolidAreaPreview } from "/texto_off/solidos/area_preview.js";
import { filterSolidChapters } from "/texto_off/solidos/filter.js";

const API = "/api/textoff/solidos";
const endpoint = (path, params) => path + "?" + new URLSearchParams(params);
async function responseJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
export function render(container) {
  const root = document.createElement("section");
  root.className = "auto-merge-page textoff-merged-page cleaner-overview";
  root.innerHTML = `<header class="solid-page-heading"><h1 class="textoff-page-title-hint" tabindex="0"
    data-tooltip="Limpeza direcionada às áreas sólidas aprovadas no Check"
    aria-description="Limpeza direcionada às áreas sólidas aprovadas no Check">Auto-Cleaner · Sólidos</h1>
    <span title="Exibe apenas áreas classificadas e salvas no Auto-Cleaner Check">Áreas aprovadas no Check · Capítulo → Página → Balão</span></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search solid-search"><span class="visually-hidden">Buscar capítulo ou página</span>
      <input type="search" data-search placeholder="Buscar capítulo ou página"></label>
      <div class="auto-merge-filters" data-filters role="group" aria-label="Filtrar capítulos"></div>
      <button class="auto-merge-execute" data-run type="button">Executar Sólidos</button>
    </div>
    <p class="auto-merge-status" data-state role="status" aria-live="polite"></p>
    <div class="auto-merge-results" data-results></div>`;
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/texto_off/solidos/style.css";
  document.head.append(stylesheet);
  container.replaceChildren(root);
  const status = root.querySelector("[data-state]");
  const runButton = root.querySelector("[data-run]");
  const search = root.querySelector("[data-search]");
  const filters = root.querySelector("[data-filters]");
  const progress = createJobProgress("Auto-Cleaner: Sólidos");
  root.querySelector(".auto-merge-toolbar").after(progress.element);
  const inspector = createSolidInspector(root, API);
  const areaPreview = createSolidAreaPreview(getContext);
  let rows = [], selected = new Set(), filter = "all", page = 0;
  let busy = false, disposed = false, controller = null, generation = 0;
  const areaLoader = createSolidAreaLoader(getContext, () => rows, draw);
  const table = createSolidTable(root.querySelector("[data-results]"), {
    onSelect(chapter, checked) { checked ? selected.add(chapter) : selected.delete(chapter); draw(); },
    onSelectPage(chapters, checked) {
      chapters.forEach(chapter => checked ? selected.add(chapter) : selected.delete(chapter)); draw();
    },
    inspect(row) { inspector.open(row, getContext()); },
    changePage(next) { page = next; draw(); },
    redraw() { draw(); },
    loadAreas(row) { areaLoader.load(row); },
    preview: areaPreview,
    reexecutePage(row) { reexecutePage(row); },
  });
  function matching() {
    return filterSolidChapters(rows, search.value, filter);
  }
  function drawFilters() {
    filters.replaceChildren();
    for (const [key, label] of [["all","All"],["pending","Do"],["processed","Done"]]) {
      const count = rows.filter(row => key === "all" || (key === "processed") === Boolean(row.processed)).length;
      const button = document.createElement("button");
      button.className = "auto-merge-filter-button";
      button.classList.toggle("active", key === filter);
      button.setAttribute("aria-pressed", String(key === filter));
      button.textContent = `${label} (${count})`;
      button.type = "button";
      button.onclick = () => { filter = key; page = 0; draw(); };
      filters.append(button);
    }
  }
  function draw() {
    drawFilters();
    const current = matching();
    const valid = new Set(rows.filter(r => !r.processed).map(r => r.chapter));
    selected = new Set([...selected].filter(ch => valid.has(ch)));
    table.draw(current, selected, page, busy);
    runButton.disabled = busy || selected.size === 0;
  }
  async function load() {
    controller?.abort();
    controller = new AbortController();
    const id = ++generation;
    const { provider, manga } = getContext();
    areaLoader.beginLoad({ provider, manga });
    rows = []; selected.clear(); page = 0;
    if (!provider || !manga) {
      status.textContent = "Selecione uma obra."; draw(); return;
    }
    status.textContent = "Consultando capítulos...";
    draw();
    try {
      const data = await responseJson(endpoint(API, { provider, manga }), { signal: controller.signal });
      if (disposed || id !== generation) return;
      rows = data.chapters || [];
      areaLoader.attach(rows);
      status.textContent = rows.length ? "" : "Nenhuma área sólida aprovada no Check.";
      draw();
    } catch (error) {
      if (!disposed && id === generation && error.name !== "AbortError") status.textContent = error.message;
    }
  }
  async function runJobs(jobs) {
    if (busy || !jobs.length) return;
    busy = true; draw();
    const context = getContext();
    try {
      for (let i = 0; i < jobs.length; i++) {
        const { chapter, page: pageName, result_sha256 } = jobs[i];
        status.textContent = `${pageName ? `Página ${pageName} · ` : ""}Capítulo ${chapter} (${i+1}/${jobs.length})`;
        progress.update({ busy:true, title:"Auto-Cleaner: Sólidos",
          completed:i, total:jobs.length, percent:Math.floor(i*100/jobs.length),
          message:`Executando capítulo ${chapter}` });
        const payload = {provider:context.provider,manga:context.manga,chapter};
        if (pageName) Object.assign(payload, {page:pageName,expected_result_sha256:result_sha256});
        const data = await responseJson(API+"/execute", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify(payload),
        });
        let job = data.job;
        while (!disposed && job?.status !== "completed" && job?.status !== "failed") {
          await new Promise(resolve => setTimeout(resolve, 600));
          job = (await responseJson(`/api/jobs/${encodeURIComponent(job.id)}`)).job;
          status.textContent = job?.progress?.message || `Processando capítulo ${chapter}...`;
        }
        if (disposed) return;
        if (job?.status === "failed") throw new Error(`Capítulo ${chapter}: ${job.error || "falha"}`);
        progress.update({busy:true, title:"Auto-Cleaner: Sólidos",
          completed:i+1, total:jobs.length, percent:Math.floor((i+1)*100/jobs.length),
          message:pageName ? `${pageName} reexecutada` : `Capítulo ${chapter} concluído`});
      }
      await load();
    } catch (error) {
      if (!disposed) status.textContent = error.message;
    } finally {
      invalidateCleanerOverview(context.provider, context.manga);
      busy = false; progress.update({busy:false}); if (!disposed) draw();
    }
  }
  async function execute() {
    if (!selected.size) return;
    await runJobs([...selected].map((chapter) => ({chapter})));
  }
  async function reexecutePage(row) {
    if (busy || !row.result_sha256) return;
    const confirmed = await confirmMessage({
      title: "Reexecutar página em Sólidos",
      message: `Reexecutar somente ${row.name} do capítulo ${row.chapter} com as áreas aprovadas atualmente no Check? A prévia anterior dessa página será arquivada e continuará preservada. As outras páginas do capítulo não serão reexecutadas.`,
      confirmText: "Reexecutar página",
    });
    if (!confirmed || busy) return;
    await runJobs([{chapter:row.chapter,page:row.name,result_sha256:row.result_sha256}]);
  }
  search.addEventListener("input", () => {page=0;draw();});
  runButton.addEventListener("click", execute);
  const unsubscribe = subscribeContext(load);
  load();
  return () => {
    disposed = true; generation++; controller?.abort(); unsubscribe();
    areaLoader.dispose(); areaPreview.dispose(); inspector.dispose(); progress.element.remove(); stylesheet.remove(); root.remove();
  };
}
