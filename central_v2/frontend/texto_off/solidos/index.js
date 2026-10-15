import { getContext, subscribeContext } from "/_app/state/context.js";

const API = "/api/textoff/solidos";
const url = (path, params) => path + "?" + new URLSearchParams(params);

export function render(container) {
  const root = document.createElement("section");
  root.style.cssText = "padding:18px;display:grid;gap:14px;color:#14516c";
  root.innerHTML = `<h3 style="margin:0">05 — Auto-Cleaner: Sólidos</h3>
    <p style="margin:0">Prévia independente · áreas aprovadas no Check · mesmo motor do Laboratório</p>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <label>Capítulo <select data-chapter></select></label>
      <button data-run type="button">Executar Sólidos</button>
      <label>Página <select data-page></select></label>
    </div><div data-state role="status"></div>
    <div style="display:flex;gap:14px;overflow:auto;align-items:start">
      <section><strong>ANTES</strong><img data-before style="display:block;width:320px;height:auto" /></section>
      <section><strong>DEPOIS</strong><img data-after style="display:block;width:320px;height:auto" /></section>
    </div>`;
  container.replaceChildren(root);
  const chapter = root.querySelector("[data-chapter]");
  const page = root.querySelector("[data-page]");
  const state = root.querySelector("[data-state]");
  const run = root.querySelector("[data-run]");
  const before = root.querySelector("[data-before]");
  const after = root.querySelector("[data-after]");
  let chapters = [], disposed = false, abort = new AbortController();
  const current = () => getContext();
  function showImages() {
    const selected = chapters.find(row => row.chapter === chapter.value);
    const hasResult = Boolean(selected?.processed && page.value);
    for (const [img, kind] of [[before, "before"], [after, "after"]]) {
      if (!hasResult) { img.removeAttribute("src"); img.hidden = true; continue; }
      img.hidden = false;
      img.src = url(API + "/image", { provider: current().provider,
        manga: current().manga, chapter: chapter.value, page: page.value, kind });
    }
  }
  function selectChapter() {
    const selected = chapters.find(row => row.chapter === chapter.value);
    page.replaceChildren(...(selected?.pages || []).map(name => new Option(name, name)));
    run.disabled = !selected || selected.processed;
    state.textContent = selected ? `${selected.regions} áreas aprovadas · ${selected.processed ? "Prévia disponível" : "Aguardando execução"}` : "Nenhuma área aprovada";
    showImages();
  }
  async function load() {
    abort.abort(); abort = new AbortController();
    const { provider, manga } = current();
    if (!provider || !manga) { state.textContent = "Selecione uma obra"; return; }
    state.textContent = "Consultando ocorrências aprovadas…";
    try {
      const res = await fetch(url(API, { provider, manga }), { signal: abort.signal });
      const data = await res.json(); if (!res.ok) throw Error(data.error || "Falha ao consultar");
      if (disposed) return;
      chapters = data.chapters || [];
      const old = chapter.value;
      chapter.replaceChildren(...chapters.map(c => new Option(`Cap. ${c.chapter}`, c.chapter)));
      if (chapters.some(c => c.chapter === old)) chapter.value = old;
      selectChapter();
    } catch (e) { if (e.name !== "AbortError") state.textContent = e.message; }
  }
  async function execute() {
    const { provider, manga } = current();
    run.disabled = true; state.textContent = "Executando Sólidos…";
    try {
      const response = await fetch(API + "/execute", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, manga, chapter: chapter.value }), signal: abort.signal });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Falha ao iniciar");
      let job = data.job;
      while (!disposed && job?.status !== "completed" && job?.status !== "failed") {
        await new Promise(resolve => setTimeout(resolve, 600));
        const poll = await fetch(`/api/jobs/${encodeURIComponent(job.id)}`, { signal: abort.signal });
        const payload = await poll.json(); job = payload.job;
        state.textContent = job?.progress?.message || "Processando regiões aprovadas…";
      }
      if (job?.status === "failed") throw Error(job.error || "Tratamento falhou");
      if (!disposed) await load();
    } catch (e) {
      if (e.name !== "AbortError" && !disposed) state.textContent = e.message;
      if (!disposed) run.disabled = false;
    }
  }
  chapter.addEventListener("change", selectChapter);
  page.addEventListener("change", showImages);
  run.addEventListener("click", execute);
  const unsubscribe = subscribeContext(load);
  load();
  return () => { disposed = true; abort.abort(); unsubscribe(); root.remove(); };
}
