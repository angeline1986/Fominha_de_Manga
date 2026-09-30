import { getContext, subscribeContext } from "/_app/state/context.js";
import { fetchManualSpecial, manualSpecialImageUrl, manualSpecialResultUrl, startManualSpecial,
  waitForTextoffJob } from "/_app/api/textoff.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";
import { createJobProgress } from "/_shared/progress/progress.js";

export function renderSpecial(container, level, title) {
  const root = document.createElement("section");
  root.className = "auto-merge-page textoff-merged-page textoff-special-manual";
  root.innerHTML = `<header><h1>Texto Off — Especiais Nível ${level}: ${title}</h1></header>
    <p class="textoff-level-description">Selecione uma página do Nível I e marque as regiões que devem ser tratadas.</p>
    <div class="auto-merge-toolbar special-toolbar">
      <label class="special-field">Capítulo<select data-chapter aria-label="Capítulo"></select></label>
      <label class="special-field">Página<select data-page aria-label="Página"></select></label>
      <button type="button" class="special-clear" data-clear>Limpar regiões</button>
      <button type="button" class="auto-merge-execute" data-run>Aplicar tratamento</button>
    </div>
    <p class="auto-merge-note" data-selection-count>Regiões selecionadas: 0</p>
    <div class="special-image-panel"><div data-image-wrap class="special-roi-canvas"><img data-image alt="Página do Nível I"><canvas data-canvas></canvas></div></div>
    <section data-comparison class="special-comparison auto-merge-results" hidden>
      <figure><figcaption>Entrada</figcaption><img data-before alt="Entrada"></figure>
      <figure><figcaption>Resultado</figcaption><img data-after alt="Resultado"></figure>
    </section>
    <p class="auto-merge-status" data-status role="status" aria-live="polite"></p>`;
  container.replaceChildren(root);
  const chapterSelect = root.querySelector("[data-chapter]");
  const pageSelect = root.querySelector("[data-page]");
  const image = root.querySelector("[data-image]");
  const canvas = root.querySelector("[data-canvas]");
  const context2d = canvas.getContext("2d");
  const selections = [];
  let rows = [], drag = null, disposed = false, controller;
  const progress = createJobProgress(`Especiais Nível ${level}`);
  root.querySelector("[data-run]").after(progress.element);

  function draw() {
    const bounds = image.getBoundingClientRect();
    canvas.width = Math.max(1, Math.round(bounds.width));
    canvas.height = Math.max(1, Math.round(bounds.height));
    context2d.clearRect(0, 0, canvas.width, canvas.height);
    context2d.strokeStyle = "#e83e8c";
    context2d.lineWidth = 2;
    selections.forEach((box) => context2d.strokeRect(...displayBox(box)));
    root.querySelector("[data-selection-count]").textContent = `Regiões selecionadas: ${selections.length}`;
  }

  function displayBox(box) {
    const sx = canvas.width / image.naturalWidth, sy = canvas.height / image.naturalHeight;
    return [box.x * sx, box.y * sy, box.width * sx, box.height * sy];
  }

  function updateImage() {
    selections.length = 0;
    root.querySelector("[data-comparison]").hidden = true;
    const chapter = chapterSelect.value, filename = pageSelect.value;
    if (!chapter || !filename) { image.removeAttribute("src"); draw(); return; }
    const { provider, manga } = getContext();
    image.src = manualSpecialImageUrl(provider, manga, chapter, filename);
  }

  function loadPages() {
    const row = rows.find((item) => item.chapter === chapterSelect.value);
    const files = (row?.level1_pages || []).map((item) => String(item).split("/").pop());
    pageSelect.replaceChildren(...files.map((file) => new Option(file, file)));
    updateImage();
  }

  async function load() {
    const { provider, manga } = getContext();
    if (!provider || !manga) return;
    controller?.abort(); controller = new AbortController();
    try {
      const data = await fetchManualSpecial(provider, manga, level, controller.signal);
      if (disposed) return;
      rows = (data.chapters || []).filter((row) => row.level1_ready);
      chapterSelect.replaceChildren(...rows.map((row) => new Option(row.chapter, row.chapter)));
      loadPages();
      root.querySelector("[data-status]").textContent = rows.length ? "" : "Execute o Nível I para disponibilizar páginas.";
    } catch (error) {
      if (!disposed && error.name !== "AbortError") root.querySelector("[data-status]").textContent = error.message;
    }
  }

  async function execute() {
    if (!selections.length) return showMessage({ title: "Nenhuma região selecionada", message: "Marque uma ou mais regiões na página." });
    if (!await confirmMessage({ title: `Executar Nível ${level}`, message: `${selections.length} região(ões) serão processadas em ${pageSelect.value}.`, confirmText: "Executar" })) return;
    try {
      const { provider, manga } = getContext();
      const { job } = await startManualSpecial(provider, manga, level, chapterSelect.value, pageSelect.value, selections);
      const results = await waitForTextoffJob(job, progress.update);
      const result = results[0];
      if (result?.execution_status === "succeeded") {
        root.querySelector("[data-before]").src = manualSpecialImageUrl(provider, manga, chapterSelect.value, pageSelect.value);
        root.querySelector("[data-after]").src = manualSpecialResultUrl(result.run_id);
        root.querySelector("[data-comparison]").hidden = false;
      }
      await showOperationSummary({ title: `Nível ${level} concluído`, summary: {
        headline: pageSelect.value, items: results.map((result) => ({ chapter: chapterSelect.value,
          status: result.execution_status, count: "prévia", warning: result.execution_status !== "succeeded",
          details: [{ label: "Execução", value: result.run_id || result.error?.error || "Consulte o diagnóstico." }] })) } });
    } catch (error) { await showMessage({ title: `Falha no Nível ${level}`, message: error.message }); }
  }

  chapterSelect.addEventListener("change", loadPages);
  pageSelect.addEventListener("change", updateImage);
  image.addEventListener("load", draw);
  window.addEventListener("resize", draw);
  canvas.addEventListener("pointerdown", (event) => {
    if (!image.naturalWidth) return;
    const rect = canvas.getBoundingClientRect();
    drag = { x: event.offsetX * image.naturalWidth / rect.width,
      y: event.offsetY * image.naturalHeight / rect.height };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!drag) return;
    const rect = canvas.getBoundingClientRect();
    const end = { x: event.offsetX * image.naturalWidth / rect.width,
      y: event.offsetY * image.naturalHeight / rect.height };
    const x = Math.min(drag.x, end.x), y = Math.min(drag.y, end.y);
    const width = Math.abs(end.x - drag.x), height = Math.abs(end.y - drag.y);
    drag = null;
    if (width > 2 && height > 2) selections.push({ x: Math.round(x), y: Math.round(y),
      width: Math.round(width), height: Math.round(height) });
    draw();
  });
  root.querySelector("[data-clear]").addEventListener("click", () => { selections.length = 0; draw(); });
  root.querySelector("[data-run]").addEventListener("click", execute);
  const unsubscribe = subscribeContext(load);
  load();
  return () => { disposed = true; controller?.abort(); unsubscribe(); window.removeEventListener("resize", draw); root.remove(); };
}
