import { getContext, subscribeContext } from "/_app/state/context.js";
import { createJobProgress } from "/_shared/progress/progress.js";

export function createPdfView(container, source) {
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "/gerar_pdf/style.css";
  document.head.append(css);
  const progressCss = document.createElement("link");
  progressCss.rel = "stylesheet";
  progressCss.href = "/_shared/progress/progress.css";
  document.head.append(progressCss);
  const root = document.createElement("section");
  root.className = "pdf-v2";
  root.innerHTML = `
    <div class="pdf-v2-heading"><h1>${source === "merged" ? "PDF do Merge" : "PDF de Imagens Originais"}</h1><span class="pdf-v2-title-help" tabindex="0" role="note" aria-label="Gere PDFs dos capítulos selecionados com os perfis Q93 ou Q88." title="Gere PDFs dos capítulos selecionados com os perfis Q93 ou Q88.">ⓘ</span></div>
    <section class="pdf-v2-card">
      <div class="pdf-v2-toolbar">
        <input data-search type="search" aria-label="Buscar capítulo" placeholder="Buscar capítulo..." />
        <div class="pdf-v2-filters" role="group" aria-label="Filtro de PDFs">
          <button type="button" data-filter="all" aria-pressed="true">Todos</button>
          <button type="button" data-filter="missing" aria-pressed="false">Sem PDF</button>
          <button type="button" data-filter="generated" aria-pressed="false">Gerados</button>
        </div>
        <div class="pdf-v2-quality-switch" role="group" aria-label="Qualidade do PDF">
          <button type="button" data-quality-option="93" aria-pressed="true" title="Q93 — Alta qualidade">Q93</button>
          <button type="button" data-quality-option="88" aria-pressed="false" title="Q88 — Compacto">Q88</button>
        </div>
        <button class="pdf-v2-run" type="button" data-generate disabled title="Selecione capítulos para gerar PDFs">Gerar PDF</button>
      </div>
      <div class="pdf-v2-table-scroll"><table class="pdf-v2-table"><thead><tr>
        <th><input type="checkbox" data-checkall aria-label="Selecionar os capítulos visíveis"/></th>
        <th>CAP.</th><th>${source === "merged" ? "MERGE" : "IMAGENS"}</th><th>PDF</th><th>AÇÕES</th>
      </tr></thead><tbody data-rows></tbody></table></div>
      <footer class="pdf-v2-footer">
        <label class="pdf-v2-page-size">Exibir: <select data-size><option>13</option><option>26</option><option>52</option></select></label>
        <div class="pdf-v2-page-controls">
          <button type="button" data-prev aria-label="Página anterior">&lt;&lt;</button>
          <span data-counter>1 / 1</span>
          <button type="button" data-next aria-label="Próxima página">&gt;&gt;</button>
        </div>
        <span class="pdf-v2-sr-only" data-status aria-live="polite">Selecione uma obra.</span>
      </footer>
    </section>
    <p class="pdf-v2-disclaimer">A contagem de imagens não certifica a validade do MERGE oficial. PDFs existentes serão preservados.</p>
    <div class="pdf-v2-toast" data-toast role="status" aria-live="polite" hidden></div>
    <dialog class="pdf-v2-confirm" data-confirm aria-labelledby="pdf-v2-confirm-title">
      <form method="dialog">
        <h2 id="pdf-v2-confirm-title">Gerar PDF</h2>
        <p data-confirm-message></p>
        <div class="pdf-v2-confirm-actions">
          <button type="submit" value="cancel" class="pdf-v2-cancel">Cancelar</button>
          <button type="submit" value="confirm" class="pdf-v2-confirm-button">Gerar PDF</button>
        </div>
      </form>
    </dialog>`;
  container.replaceChildren(root);
  const $ = selector => root.querySelector(selector);
  const chosen = new Set();
  const generateButton = $("[data-generate]");
  const qualityButtons = [...root.querySelectorAll("[data-quality-option]")];
  let selectedQuality = 93;
  qualityButtons.forEach(button => button.addEventListener("click", () => {
    selectedQuality = Number(button.dataset.qualityOption);
    qualityButtons.forEach(option => option.setAttribute("aria-pressed", String(option === button)));
  }));
  const progressView = createJobProgress("Gerando PDFs");
  root.querySelector(".pdf-v2-card").after(progressView.element);
  const showProgress = (job, fallbackTotal) => {
    const progress = job?.progress || {};
    const completed = Number(progress.completed) || 0;
    const total = Number(progress.total) || fallbackTotal;
    const percent = Number.isFinite(Number(progress.percent))
      ? Number(progress.percent)
      : (total > 0 ? 100 * completed / total : 0);
    progressView.update({
      busy: true, title: "Gerando PDFs",
      message: progress.message || "Preparando geração…",
      completed, total, percent,
      countUnit: "capítulo(s)",
    });
  };
  const toast = $("[data-toast]");
  const confirmation = $("[data-confirm]");
  function notify(message, kind = "success") {
    toast.textContent = message;
    toast.dataset.kind = kind;
    toast.hidden = false;
    toast.focus?.();
  }
  function confirmGeneration(count, quality) {
    return new Promise(resolve => {
      if (typeof confirmation.showModal !== "function") {
        resolve(window.confirm(`Gerar ${count} PDF(s) em Q${quality}? PDFs existentes serão preservados.`));
        return;
      }
      $("[data-confirm-message]").textContent = `Gerar ${count} PDF(s) com qualidade Q${quality}? PDFs existentes serão preservados.`;
      confirmation.addEventListener("close", () => resolve(confirmation.returnValue === "confirm"), { once: true });
      confirmation.showModal();
    });
  }
  let generating = false;
  function updateGenerate() {
    generateButton.disabled = generating || loading || chosen.size === 0;
    generateButton.title = generating ? "Geração em andamento" : chosen.size ? "Gerar PDFs selecionados; existentes serão preservados" : "Selecione capítulos";
    generateButton.textContent = generating ? "Gerando…" : `Gerar PDF${chosen.size ? ` (${chosen.size})` : ""}`;
  }
  let items = [], page = 0, filter = "all", loading = false, errorText = "", disposed = false, revision = 0, request;
  function filtered() {
    const term = $("[data-search]").value.trim().toLowerCase();
    return items.filter(item => item.chapter.toLowerCase().includes(term) &&
      (filter === "all" || (filter === "missing" ? !item.has_pdf : item.has_pdf)));
  }
  function draw() {
    const rows = filtered();
    const limit = Number($("[data-size]").value);
    const total = Math.max(1, Math.ceil(rows.length / limit));
    page = Math.max(0, Math.min(page, total - 1));
    const subset = rows.slice(page * limit, (page + 1) * limit);
    const tbody = $("[data-rows]");
    tbody.replaceChildren();
    if (!subset.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td"); td.colSpan = 5; td.className = "pdf-v2-empty";
      td.textContent = loading ? "Carregando capítulos…" : (errorText || "Nenhum capítulo encontrado.");
      tr.append(td); tbody.append(tr);
    }
    for (const item of subset) {
      const tr = document.createElement("tr");
      const boxCell = document.createElement("td");
      const check = document.createElement("input"); check.type = "checkbox"; check.checked = chosen.has(item.chapter);
      check.setAttribute("aria-label", `Selecionar capítulo ${item.chapter}`);
      check.addEventListener("change", () => { if (check.checked) chosen.add(item.chapter); else chosen.delete(item.chapter); draw(); });
      boxCell.append(check); tr.append(boxCell);
      for (const value of [item.chapter, item.image_count ? `✓ ${item.image_count} imagens` : "—"]) {
        const td = document.createElement("td"); td.textContent = value; tr.append(td);
      }
      const pdfCell = document.createElement("td");
      if (item.has_pdf) {
        const checkmark = document.createElement("span");
        checkmark.className = "pdf-v2-pdf-ok";
        checkmark.textContent = "✓";
        checkmark.setAttribute("aria-label", "PDF gerado");
        const size = document.createElement("span");
        size.textContent = ` ${(Number(item.pdf_bytes || 0) / 1000000).toFixed(1).replace(".", ",")} MB`;
        pdfCell.append(checkmark, size);
      } else {
        pdfCell.textContent = "—";
      }
      tr.append(pdfCell);
      const actions = document.createElement("td"); actions.textContent = "—"; tr.append(actions);
      tbody.append(tr);
    }
    $("[data-status]").textContent = errorText || `${rows.length ? page * limit + 1 : 0}–${Math.min((page + 1) * limit, rows.length)} de ${rows.length} · ${chosen.size} selecionado(s)`;
    $("[data-counter]").textContent = `${page + 1} / ${total}`;
    $("[data-prev]").disabled = page === 0;
    $("[data-next]").disabled = page === total - 1;
    const checkall = $("[data-checkall]");
    checkall.checked = subset.length > 0 && subset.every(item => chosen.has(item.chapter));
    checkall.indeterminate = !checkall.checked && subset.some(item => chosen.has(item.chapter));
    updateGenerate();
  }
  $("[data-search]").addEventListener("input", () => { page = 0; draw(); });
  $("[data-size]").addEventListener("change", () => { page = 0; draw(); });
  root.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => {
    filter = button.dataset.filter; page = 0;
    root.querySelectorAll("[data-filter]").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
    draw();
  }));
  $("[data-checkall]").addEventListener("change", event => {
    const limit = Number($("[data-size]").value);
    for (const item of filtered().slice(page * limit, (page + 1) * limit)) {
      if (event.target.checked) chosen.add(item.chapter); else chosen.delete(item.chapter);
    }
    draw();
  });
  $("[data-prev]").addEventListener("click", () => { page--; draw(); });
  $("[data-next]").addEventListener("click", () => { page++; draw(); });
  generateButton.addEventListener("click", async () => {
    if (generating || !chosen.size) return;
    const { provider, manga } = getContext();
    if (!provider || !manga) return;
    const selection = [...chosen];
    const quality = selectedQuality;
    if (!await confirmGeneration(selection.length, quality)) return;
    generating = true;
    updateGenerate();
    showProgress({ progress: { message: "Iniciando geração…", completed: 0, total: selection.length, percent: 0 } }, selection.length);
    try {
      const response = await fetch("/api/pdf/execute", {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ provider, manga, source, chapters: selection, quality, existing_policy: "skip" }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      let job = payload.job;
      if (!job?.id) throw new Error("O servidor não confirmou o job.");
      showProgress(job, selection.length);
      while (!disposed && !["completed", "failed"].includes(job.status)) {
        await new Promise(resolve => setTimeout(resolve, 700));
        if (disposed) return;
        const statusResponse = await fetch(`/api/jobs/${encodeURIComponent(job.id)}`, { cache: "no-store" });
        const statusPayload = await statusResponse.json();
        if (!statusResponse.ok) throw new Error(statusPayload.error || `HTTP ${statusResponse.status}`);
        job = statusPayload.job;
        if (!job) throw new Error("Resposta do job inválida.");
        showProgress(job, selection.length);
      }
      if (disposed) return;
      const results = job.results || [];
      const created = results.filter(item => item.status === "generated").length;
      const skipped = results.filter(item => item.status === "skipped").length;
      const failures = results.filter(item => item.status === "failed").length;
      progressView.update({ busy: false });
      notify(job.status === "completed" ? `✓ ${created} PDF(s) gerado(s) com sucesso${skipped ? ` · ${skipped} existente(s) preservado(s)` : ""}.` : `A geração terminou com ${failures} falha(s). ${job.error || ""}`, job.status === "completed" ? "success" : "error");
      await load();
    } catch (error) {
      if (!disposed) { progressView.update({ busy: false }); notify(`Falha na geração: ${error.message}`, "error"); }
    } finally {
      generating = false;
      if (!disposed) updateGenerate();
    }
  });
  async function load() {
    const id = ++revision;
    request?.abort(); request = new AbortController();
    const { provider, manga } = getContext();
    items = []; chosen.clear(); page = 0; errorText = "";
    loading = Boolean(provider && manga); draw();
    if (!provider || !manga) { $("[data-status]").textContent = "Selecione uma obra no menu lateral."; return; }
    try {
      const q = new URLSearchParams({ provider, manga, source });
      const resp = await fetch(`/api/pdf?${q}`, { cache: "no-store", signal: request.signal });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
      if (disposed || id !== revision) return;
      items = data.chapters || [];
    } catch (error) {
      if (error.name !== "AbortError" && !disposed && id === revision) errorText = `Falha: ${error.message}`;
    } finally {
      if (!disposed && id === revision) { loading = false; draw(); }
    }
  }
  const unsubscribe = subscribeContext(load);
  load();
  return () => { disposed = true; revision++; request?.abort(); unsubscribe(); confirmation.open && confirmation.close(); progressCss.remove(); css.remove(); root.remove(); };
}
