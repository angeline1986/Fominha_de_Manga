import { getContext, subscribeContext } from "/_app/state/context.js";
import { createJobProgress } from "/_shared/progress/progress.js";
import { createSolidTable } from "/texto_off/solidos/table.js";
import { createSolidInspector } from "/texto_off/solidos/inspector.js";

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
  root.innerHTML = `<header><h1 class="textoff-page-title-hint" tabindex="0"
    data-tooltip="Limpeza direcionada às áreas sólidas aprovadas no Check"
    aria-description="Limpeza direcionada às áreas sólidas aprovadas no Check">Auto-Cleaner: Sólidos</h1></header>
    <div class="auto-merge-toolbar">
      <label class="auto-merge-search"><span class="visually-hidden">Buscar capítulo</span>
      <input type="search" data-search placeholder="Capítulo"></label>
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
  let rows = [], selected = new Set(), filter = "all", page = 0;
  let busy = false, disposed = false, controller = null, generation = 0;
  const table = createSolidTable(root.querySelector("[data-results]"), {
    onSelect(chapter, checked) { checked ? selected.add(chapter) : selected.delete(chapter); draw(); },
    onSelectPage(chapters, checked) {
      chapters.forEach(chapter => checked ? selected.add(chapter) : selected.delete(chapter)); draw();
    },
    inspect(row) { inspector.open(row, getContext()); },
    changePage(next) { page = next; draw(); },
  });
  function matching() {
    const term = search.value.trim().toLocaleLowerCase("pt-BR");
    return rows.filter(row => row.chapter.toLocaleLowerCase("pt-BR").includes(term)
      && (filter === "all" || filter === "pending" && !row.processed
        || filter === "processed" && row.processed));
  }
  function drawFilters() {
    filters.replaceChildren();
    for (const [key, label] of [["all","All"],["pending","Pendentes"],["processed","Concluídos"]]) {
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
      status.textContent = rows.length ? "" : "Nenhuma área sólida aprovada no Check.";
      draw();
    } catch (error) {
      if (!disposed && id === generation && error.name !== "AbortError") status.textContent = error.message;
    }
  }
  async function execute() {
    if (busy || !selected.size) return;
    busy = true; draw();
    const context = getContext();
    const chapters = [...selected];
    try {
      for (let i = 0; i < chapters.length; i++) {
        const chapter = chapters[i];
        status.textContent = `Capítulo ${chapter} (${i+1}/${chapters.length})`;
        progress.update({ busy:true, title:"Auto-Cleaner: Sólidos",
          completed:i, total:chapters.length, percent:Math.floor(i*100/chapters.length),
          message:`Executando capítulo ${chapter}` });
        const data = await responseJson(API+"/execute", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({provider:context.provider,manga:context.manga,chapter}),
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
          completed:i+1, total:chapters.length, percent:Math.floor((i+1)*100/chapters.length),
          message:`Capítulo ${chapter} concluído`});
      }
      await load();
    } catch (error) {
      if (!disposed) status.textContent = error.message;
    } finally {
      busy = false; progress.update({busy:false}); if (!disposed) draw();
    }
  }
  search.addEventListener("input", () => {page=0;draw();});
  runButton.addEventListener("click", execute);
  const unsubscribe = subscribeContext(load);
  load();
  return () => {
    disposed = true; generation++; controller?.abort(); unsubscribe();
    inspector.dispose(); progress.element.remove(); stylesheet.remove(); root.remove();
  };
}
