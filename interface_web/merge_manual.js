(() => {
  "use strict";

  const STORAGE_KEY = "fominha.mergeManual.selection.v1";
  const ui = {
    cacheKey: "",
    payload: null,
    loading: false,
    error: "",
    query: "",
    status: "all",
    selectedChapter: null,
    selected: null,
  };

  let previewZoom = 100;
  const cutEditor = {
    cuts: [],
    selectedIndex: null,
    draggingIndex: null,
  };
  let proposalBusy = false;
  let currentProposal = null;

  const htmlEsc = value => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function context() {
    const provider = document.getElementById("provider")?.value || "";
    const manga = document.getElementById("manga")?.value || "";
    return { provider, manga, key: `${provider}::${manga}` };
  }

  function sourceUrl(ctx, chapter, file) {
    return `/media?provider=${encodeURIComponent(ctx.provider)}&manga=${encodeURIComponent(ctx.manga)}&kind=source&chapter=${encodeURIComponent(chapter)}&file=${encodeURIComponent(file)}`;
  }

  function statusLabel(status) {
    if (status === "pending") return '<span class="mm-status mm-status-pending">Pendente</span>';
    if (status === "resolved") return '<span class="mm-status mm-status-ok">Resolvido</span>';
    return '<span class="mm-status mm-status-blocked">Bloqueado</span>';
  }

  async function ensurePayload(root, force = false) {
    const ctx = context();
    if (!ctx.manga) return;
    if (!force && ui.payload && ui.cacheKey === ctx.key) return;
    if (ui.loading) return;

    ui.loading = true;
    ui.error = "";
    ui.cacheKey = ctx.key;
    root.innerHTML = '<div class="mm-page"><div class="mm-loading">Carregando pendências autoritativas da Revisão Merge…</div></div>';

    try {
      const response = await fetch(`/api/merge-manual?provider=${encodeURIComponent(ctx.provider)}&manga=${encodeURIComponent(ctx.manga)}&_=${Date.now()}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload?.error) throw new Error(payload?.error || `HTTP ${response.status}`);
      if (ui.cacheKey !== ctx.key) return;
      ui.payload = payload;
    } catch (error) {
      ui.payload = null;
      ui.error = error?.message || String(error);
    } finally {
      ui.loading = false;
    }

    if (typeof page !== "undefined" && page === "merge_manual") renderValidation(root);
  }

  function filteredRows() {
    const rows = ui.payload?.chapters || [];
    const query = ui.query.trim().toLowerCase();
    return rows.filter(item => {
      if (query && !String(item.chapter).toLowerCase().includes(query)) return false;
      if (ui.status === "pending" && item.status !== "pending") return false;
      if (ui.status === "resolved" && item.status !== "resolved") return false;
      return true;
    });
  }

  function rangeSelection(chapter, block) {
    const key = `${chapter}::${block.id}`;
    if (!ui.selected || ui.selected.key !== key) {
      const first = block.pages?.[0]?.file || "";
      const last = block.pages?.[block.pages.length - 1]?.file || first;
      return { key, chapter, blockId: block.id, start: first, end: last };
    }
    return ui.selected;
  }

  function setRange(chapter, blockId, field, value) {
    const row = (ui.payload?.chapters || []).find(item => String(item.chapter) === String(chapter));
    const block = row?.pending_blocks?.find(item => item.id === blockId);
    if (!block) return;
    const current = rangeSelection(chapter, block);
    const next = { ...current, [field]: value };
    const names = (block.pages || []).map(item => item.file);
    const startIndex = names.indexOf(next.start);
    let endIndex = names.indexOf(next.end);
    if (startIndex < 0) next.start = names[0] || "";
    if (endIndex < startIndex) next.end = names[Math.max(0, startIndex)] || "";
    ui.selected = next;
    renderValidation(document.getElementById("page"));
  }

  function selectedSummary() {
    if (!ui.selected) return null;
    const row = (ui.payload?.chapters || []).find(item => String(item.chapter) === String(ui.selected.chapter));
    const block = row?.pending_blocks?.find(item => item.id === ui.selected.blockId);
    if (!block) return null;
    const names = (block.pages || []).map(item => item.file);
    const a = names.indexOf(ui.selected.start);
    const b = names.indexOf(ui.selected.end);
    if (a < 0 || b < a) return null;
    const pages = block.pages.slice(a, b + 1);
    return {
      ...ui.selected,
      files: pages.map(item => item.file),
      slices: pages.map(item => ({
        file: item.file,
        sourceYStart: Number(item.source_y_start || 0),
        sourceYEnd: Number(item.source_y_end ?? item.height ?? 0),
        sourceHeight: Number(item.height || 0),
        pendingHeight: Number(item.pending_height || 0),
      })),
      count: pages.length,
      globalStart: Math.max(Number(block.global_start), Number(pages[0].global_start)),
      globalEnd: Math.min(Number(block.global_end), Number(pages[pages.length - 1].global_end)),
    };
  }

  function submitRange() {
    const selection = selectedSummary();
    if (!selection) {
      if (typeof toast === "function") toast("Selecione uma faixa válida dentro do mesmo bloco pendente.");
      return;
    }
    const ctx = context();
    const snapshot = { ...selection, provider: ctx.provider, manga: ctx.manga };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
    page = "merge_manual_cuts";
    document.querySelectorAll("nav button[data-page]").forEach(button => button.classList.toggle("active", button.dataset.page === "merge_manual_cuts"));
    if (typeof render === "function") render();
  }

  function selectedRow() {
    if (ui.selectedChapter == null) return null;
    return (ui.payload?.chapters || []).find(item => String(item.chapter) === String(ui.selectedChapter)) || null;
  }

  function ensureSelectedRange(row) {
    if (!row || row.status !== "pending") {
      ui.selected = null;
      return null;
    }
    const block = (row.pending_blocks || [])[0];
    if (!block) {
      ui.selected = null;
      return null;
    }
    const next = rangeSelection(row.chapter, block);
    if (!ui.selected || ui.selected.key !== next.key) ui.selected = next;
    return block;
  }

  function selectedChapterSection(row) {
    if (!row) return "";

    if (row.status === "blocked") {
      return `
        <section class="panel mm-chapter-section">
          <div class="mm-chapter-section-head">
            <div class="mm-chapter-title">Cap. ${htmlEsc(row.chapter)}</div>
            ${statusLabel(row.status)}
          </div>
          <div class="mm-detail-error"><b>Merge Manual indisponível para este capítulo.</b><span>${htmlEsc(row.error || "Estado autoritativo inválido.")}</span></div>
        </section>`;
    }

    if (row.status !== "pending") {
      return `
        <section class="panel mm-chapter-section">
          <div class="mm-chapter-section-head">
            <div class="mm-chapter-title">Cap. ${htmlEsc(row.chapter)}</div>
            ${statusLabel(row.status)}
          </div>
          <div class="mm-resolved-note">Nenhum residual pendente da Revisão Merge.</div>
        </section>`;
    }

    const block = ensureSelectedRange(row);
    if (!block) return "";

    const selected = rangeSelection(row.chapter, block);
    const names = (block.pages || []).map(item => item.file);
    const startIndex = Math.max(0, names.indexOf(selected.start));
    const endOptions = (block.pages || []).slice(startIndex);
    const currentEnd = endOptions.some(item => item.file === selected.end) ? selected.end : (endOptions[0]?.file || "");
    if (ui.selected?.key === selected.key && currentEnd !== ui.selected.end) ui.selected.end = currentEnd;
    const endIndex = names.indexOf(currentEnd);
    const rangeCount = endIndex >= startIndex ? endIndex - startIndex + 1 : 0;
    const selectedPages = endIndex >= startIndex
      ? (block.pages || []).slice(startIndex, endIndex + 1)
      : [];

    return `
      <section class="panel mm-chapter-section">
        <div class="mm-chapter-section-head">
          <div class="mm-chapter-title">Cap. ${htmlEsc(row.chapter)}</div>
          <div class="mm-range-row mm-range-row-inline">
            <label><span>Início</span><select onchange="MergeManualUI.setRange('${htmlEsc(row.chapter)}','${htmlEsc(block.id)}','start',this.value)">${(block.pages || []).map(item => `<option value="${htmlEsc(item.file)}" ${item.file === selected.start ? "selected" : ""}>${htmlEsc(item.file)}</option>`).join("")}</select></label>
            <span class="mm-range-arrow" aria-hidden="true">→</span>
            <label><span>Fim</span><select onchange="MergeManualUI.setRange('${htmlEsc(row.chapter)}','${htmlEsc(block.id)}','end',this.value)">${endOptions.map(item => `<option value="${htmlEsc(item.file)}" ${item.file === currentEnd ? "selected" : ""}>${htmlEsc(item.file)}</option>`).join("")}</select></label>
          </div>
          <div class="mm-range-summary mm-range-summary-inline"><b>${rangeCount} imagem(ns) na faixa</b><span>${htmlEsc(selected.start)} → ${htmlEsc(currentEnd)}</span></div>
          ${statusLabel(row.status)}
        </div>

        <div class="mm-preview-toolbar">
          <div class="mm-preview-zoom">
            <span>Zoom do preview</span>
            <button type="button" class="btn" onclick="MergeManualUI.changePreviewZoom(-10)" ${previewZoom <= 60 ? "disabled" : ""}>−</button>
            <b>${previewZoom}%</b>
            <button type="button" class="btn" onclick="MergeManualUI.changePreviewZoom(10)" ${previewZoom >= 180 ? "disabled" : ""}>+</button>
            <button type="button" class="btn" onclick="MergeManualUI.resetPreviewZoom()" ${previewZoom === 100 ? "disabled" : ""}>Redefinir</button>
          </div>
        </div>

        <section class="mm-selected-preview">
          <div class="mm-selected-preview-head">
            <span class="mm-eyebrow">PREVIEW DA FAIXA SELECIONADA</span>
            <span>${rangeCount} imagem(ns)</span>
          </div>
          <div class="mm-selected-preview-strip" style="--mm-preview-zoom:${previewZoom / 100}">
            ${selectedPages.map(item => `
              <figure class="mm-preview-thumb">
                <div class="mm-preview-thumb-media">
                  <img loading="lazy"
                       src="${sourceUrl(context(), row.chapter, item.file)}"
                       alt="${htmlEsc(item.file)}">
                </div>
                <figcaption>${htmlEsc(item.file)}</figcaption>
              </figure>`).join("")}
          </div>
        </section>
      </section>`;
  }

  function renderValidation(root) {
    if (!root) return;
    const ctx = context();
    if (!ui.payload || ui.cacheKey !== ctx.key) {
      ensurePayload(root);
      return;
    }
    if (ui.error) {
      root.innerHTML = `<div class="mm-page"><div class="empty">${htmlEsc(ui.error)}</div></div>`;
      return;
    }

    const rows = filteredRows();
    const activeRow = selectedRow();
    if (ui.selectedChapter != null && !activeRow) {
      ui.selectedChapter = null;
      ui.selected = null;
    }
    if (activeRow?.status === "pending") ensureSelectedRange(activeRow);
    const selected = selectedSummary();

    root.innerHTML = `
      <div class="mm-page mm-validation-page">
        ${typeof head === "function" ? head("Validar merge manual", "Selecione uma faixa que permaneceu pendente na Revisão Merge. Esta etapa é somente leitura e não altera o MERGE oficial.") : "<h1>Validar merge manual</h1>"}
        <div class="toolbar standard-filterbar mm-toolbar">
          <input class="search" placeholder="Buscar capítulo..." value="${htmlEsc(ui.query)}" oninput="MergeManualUI.setQuery(this.value)">
          <div class="status-filter" role="group" aria-label="Filtrar Merge Manual">
            <button class="tab ${ui.status === "all" ? "active" : ""}" onclick="MergeManualUI.setStatus('all')">Todos</button>
            <button class="tab ${ui.status === "pending" ? "active" : ""}" onclick="MergeManualUI.setStatus('pending')">Pendentes</button>
            <button class="tab ${ui.status === "resolved" ? "active" : ""}" onclick="MergeManualUI.setStatus('resolved')">Resolvidos</button>
          </div>
        </div>
        <div class="panel mm-table-panel">
          <table class="mm-table">
            <thead><tr><th>CAP.</th><th>RESÍDUOS / PENDÊNCIAS</th><th>BLOCOS</th><th>STATUS</th></tr></thead>
            <tbody>${rows.map(row => `
              <tr class="mm-row ${String(ui.selectedChapter) === String(row.chapter) ? "selected" : ""}">
                <td><button class="mm-chapter-link" onclick="MergeManualUI.selectChapter('${htmlEsc(row.chapter)}')">${htmlEsc(row.chapter)}</button></td>
                <td>${row.status === "pending" ? `${Number(row.pending_pages || 0)} página(s)` : (row.error ? htmlEsc(row.error) : "—")}</td>
                <td>${Number(row.blocks_count || 0)}</td>
                <td>${statusLabel(row.status)}</td>
              </tr>
            `).join("") || '<tr><td colspan="4" class="muted">Nenhum capítulo encontrado para o filtro atual.</td></tr>'}</tbody>
          </table>
        </div>

        ${activeRow ? `<div class="mm-section-gap"></div>${selectedChapterSection(activeRow)}` : ""}

        <div class="mm-actionbar">
          <div>${selected ? `<b>Cap. ${htmlEsc(selected.chapter)}</b><span>${selected.count} imagem(ns) · ${htmlEsc(selected.start)} → ${htmlEsc(selected.end)}</span>` : '<span>Selecione um capítulo pendente e defina início e fim da faixa.</span>'}</div>
          <button class="btn primary" ${selected ? "" : "disabled"} onclick="MergeManualUI.submitRange()">Submeter a Novos Cortes</button>
        </div>
      </div>`;
  }

  function loadSelection() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); }
    catch (_) { return null; }
  }

  function renderCuts(root) {
    if (!root) return;
    const selection = loadSelection();
    const ctx = context();
    if (!selection || selection.provider !== ctx.provider || selection.manga !== ctx.manga) {
      root.innerHTML = `<div class="mm-page">${typeof head === "function" ? head("Novos Cortes", "Composição visual da faixa selecionada no Merge Manual.") : "<h1>Novos Cortes</h1>"}<div class="empty">Nenhuma faixa foi submetida. Volte para <b>Validar merge manual</b> e selecione um intervalo.</div></div>`;
      return;
    }

    root.innerHTML = `
      <div class="mm-page mm-cuts-page">
        ${typeof head === "function" ? head("Novos Cortes", "Defina os cortes manuais e efetive a composição final do capítulo.") : "<h1>Novos Cortes</h1>"}
        <section class="mm-cut-toolbar panel">
          <div><span class="mm-eyebrow">FAIXA SELECIONADA</span><b>Cap. ${htmlEsc(selection.chapter)} · ${htmlEsc(selection.start)} → ${htmlEsc(selection.end)}</b></div>
          <div class="mm-tool-controls">
            <button class="btn" onclick="MergeManualUI.zoom(-0.1)">−</button>
            <span id="mmZoomLabel">100%</span>
            <button class="btn" onclick="MergeManualUI.zoom(0.1)">+</button>
            <span class="mm-separator"></span>
            <button id="mmRemoveRuler" class="btn" onclick="MergeManualUI.removeRuler()" disabled>− régua</button>
            <span id="mmCutCount">0 cortes</span>
            <button id="mmAddRuler" class="btn" onclick="MergeManualUI.addRuler()">+ régua</button>
          </div>
        </section>
        <section class="mm-stream-wrap">
          <div id="mmStream" class="mm-stream">
            ${(selection.slices || []).map(slice => `
              <figure class="mm-source"
                      data-source-y-start="${Number(slice.sourceYStart || 0)}"
                      data-source-y-end="${Number(slice.sourceYEnd || 0)}"
                      data-source-height="${Number(slice.sourceHeight || 0)}"
                      data-logical-height="${Number(slice.pendingHeight || 0)}">
                <figcaption>${htmlEsc(slice.file)}</figcaption>
                <div class="mm-source-slice">
                  <img loading="lazy" src="${sourceUrl(ctx, selection.chapter, slice.file)}" alt="${htmlEsc(slice.file)}">
                </div>
              </figure>`).join("")}
            <div id="mmRulerLayer" class="mm-ruler-layer" aria-label="Réguas de corte"></div>
          </div>
        </section>
        <div class="mm-readonly-note">Somente as fatias ainda não cobertas por merges válidos são exibidas no editor.</div>
        <div id="mmProposalResult"></div>
        <div class="mm-actionbar">
          <div><b>Cap. ${htmlEsc(selection.chapter)}</b><span>${Number(selection.count || 0)} imagem(ns) selecionada(s) · ${cutEditor.cuts.length} corte(s)</span></div>
          <button id="mmGenerateCuts" class="btn primary" ${cutEditor.cuts.length && !proposalBusy ? "" : "disabled"} onclick="MergeManualUI.generateProposal()">Novos Cortes</button>
        </div>
      </div>`;
    window.__mergeManualZoom = 1;
    cutEditor.cuts = [];
    cutEditor.selectedIndex = null;
    cutEditor.draggingIndex = null;
    requestAnimationFrame(() => {
      initCutEditor();
      loadLatestProposal();
    });
  }

  function sourceImages() {
    const stream = document.getElementById("mmStream");
    return stream ? [...stream.querySelectorAll(".mm-source img")] : [];
  }

  function layoutSourceSlices() {
    const stream = document.getElementById("mmStream");
    if (!stream) return;

    const wrapper = stream.closest(".mm-stream-wrap");
    const availableWidth = Math.max(120, Number(wrapper?.clientWidth || 928) - 28);
    let baseWidth = Number(stream.dataset.baseWidth || 0);
    if (!baseWidth) {
      baseWidth = Math.min(900, availableWidth);
      stream.dataset.baseWidth = String(baseWidth);
    }

    const zoomValue = Math.min(1.5, Math.max(0.4, Number(window.__mergeManualZoom || 1)));
    const renderedWidth = Math.max(120, baseWidth * zoomValue);
    stream.style.width = `${renderedWidth}px`;
    stream.style.maxWidth = "none";

    for (const figure of [...stream.querySelectorAll(".mm-source")]) {
      const img = figure.querySelector("img");
      const viewport = figure.querySelector(".mm-source-slice");
      if (!img || !viewport || !img.naturalWidth || !img.naturalHeight) continue;

      const sourceStart = Number(figure.dataset.sourceYStart || 0);
      const sourceEnd = Number(figure.dataset.sourceYEnd || img.naturalHeight);
      const sourceHeight = Math.max(1, Number(figure.dataset.sourceHeight || img.naturalHeight));
      const scale = renderedWidth / Number(img.naturalWidth || 1);

      figure.style.width = `${renderedWidth}px`;
      viewport.style.width = `${renderedWidth}px`;
      viewport.style.height = `${Math.max(1, (sourceEnd - sourceStart) * scale)}px`;
      img.style.marginTop = `${-sourceStart * scale}px`;
      img.style.width = `${renderedWidth}px`;
      img.style.height = `${sourceHeight * scale}px`;
    }
  }

  function logicalMetrics() {
    const stream = document.getElementById("mmStream");
    if (!stream) return {spans:[], total:0};
    layoutSourceSlices();
    const spans=[]; let logicalStart=0;
    for (const figure of [...stream.querySelectorAll(".mm-source")]) {
      const viewport=figure.querySelector(".mm-source-slice");
      const logicalHeight=Number(figure.dataset.logicalHeight || 0);
      if (!viewport || !logicalHeight) continue;
      spans.push({viewport,logicalStart,logicalEnd:logicalStart+logicalHeight,logicalHeight});
      logicalStart += logicalHeight;
    }
    return {spans,total:logicalStart};
  }

  function logicalToRenderedY(logicalY) {
    const stream=document.getElementById("mmStream");
    if(!stream)return 0;
    const {spans,total}=logicalMetrics();
    if(!spans.length||total<=0)return 0;
    const y=Math.max(0,Math.min(total,Number(logicalY||0)));
    const streamRect=stream.getBoundingClientRect();
    const span=spans.find(item=>y>=item.logicalStart&&y<=item.logicalEnd)||spans[spans.length-1];
    const rect=span.viewport.getBoundingClientRect();
    const local=Math.max(0,Math.min(span.logicalHeight,y-span.logicalStart));
    return (rect.top-streamRect.top)+(span.logicalHeight?(local/span.logicalHeight)*rect.height:0);
  }

  function pointerToLogicalY(clientY) {
    const {spans,total}=logicalMetrics();
    if(!spans.length||total<=0)return null;
    for(const span of spans){
      const rect=span.viewport.getBoundingClientRect();
      if(clientY>=rect.top&&clientY<=rect.bottom){
        const ratio=rect.height?(clientY-rect.top)/rect.height:0;
        return Math.round(span.logicalStart+ratio*span.logicalHeight);
      }
    }
    if(clientY<spans[0].viewport.getBoundingClientRect().top)return 1;
    return Math.max(1,total-1);
  }

  function normalizeCuts() {
    const { total } = logicalMetrics();
    cutEditor.cuts = cutEditor.cuts
      .map(Number)
      .filter(y => Number.isFinite(y) && y > 0 && y < total)
      .sort((a, b) => a - b)
      .filter((y, i, arr) => i === 0 || y !== arr[i - 1]);
    if (cutEditor.selectedIndex != null && cutEditor.selectedIndex >= cutEditor.cuts.length) {
      cutEditor.selectedIndex = cutEditor.cuts.length ? cutEditor.cuts.length - 1 : null;
    }
  }

  function renderRulers() {
    const layer = document.getElementById("mmRulerLayer");
    const stream = document.getElementById("mmStream");
    if (!layer || !stream) return;

    normalizeCuts();
    layer.style.height = `${stream.scrollHeight}px`;
    layer.innerHTML = cutEditor.cuts.map((y, index) => `
      <button type="button"
              class="mm-ruler ${cutEditor.selectedIndex === index ? "selected" : ""}"
              style="top:${logicalToRenderedY(y)}px"
              data-index="${index}"
              onpointerdown="MergeManualUI.beginRulerDrag(event,${index})"
              onclick="MergeManualUI.selectRuler(${index})">
        <span>Corte ${index + 1} · Y ${Math.round(y)}</span>
      </button>
    `).join("");

    const count = document.getElementById("mmCutCount");
    if (count) count.textContent = `${cutEditor.cuts.length} corte${cutEditor.cuts.length === 1 ? "" : "s"}`;

    const remove = document.getElementById("mmRemoveRuler");
    if (remove) remove.disabled = !cutEditor.cuts.length;
    const generate=document.getElementById("mmGenerateCuts");
    if(generate)generate.disabled=!cutEditor.cuts.length||proposalBusy;
    const actionText=document.querySelector(".mm-cuts-page .mm-actionbar span");
    const selection=loadSelection();
    if(actionText&&selection)actionText.textContent=`${Number(selection.count||0)} imagem(ns) selecionada(s) · ${cutEditor.cuts.length} corte(s)`;
  }

  function initCutEditor() {
    const images = sourceImages();
    if (!images.length) return;
    const refresh = () => requestAnimationFrame(() => {
      layoutSourceSlices();
      renderRulers();
    });
    for (const img of images) {
      if (img.complete && img.naturalHeight) continue;
      img.addEventListener("load", refresh, { once: true });
    }
    window.addEventListener("resize", refresh, { passive: true });
    refresh();
  }

  function addRuler() {
    const { total } = logicalMetrics();
    if (!total) {
      if (typeof toast === "function") toast("Aguarde o carregamento das imagens antes de adicionar uma régua.");
      return;
    }

    const points = [0, ...cutEditor.cuts, total].sort((a, b) => a - b);
    let bestStart = 0, bestEnd = total, bestSize = -1;
    for (let i = 0; i < points.length - 1; i++) {
      const size = points[i + 1] - points[i];
      if (size > bestSize) {
        bestSize = size;
        bestStart = points[i];
        bestEnd = points[i + 1];
      }
    }

    const y = Math.round((bestStart + bestEnd) / 2);
    if (y <= 0 || y >= total) return;
    cutEditor.cuts.push(y);
    cutEditor.cuts.sort((a, b) => a - b);
    cutEditor.selectedIndex = cutEditor.cuts.indexOf(y);
    renderRulers();
  }

  function removeRuler() {
    if (!cutEditor.cuts.length) return;
    const index = cutEditor.selectedIndex == null ? cutEditor.cuts.length - 1 : cutEditor.selectedIndex;
    cutEditor.cuts.splice(index, 1);
    cutEditor.selectedIndex = cutEditor.cuts.length ? Math.min(index, cutEditor.cuts.length - 1) : null;
    renderRulers();
  }

  function selectRuler(index) {
    cutEditor.selectedIndex = Number(index);
    renderRulers();
  }

  function beginRulerDrag(event, index) {
    event.preventDefault();
    event.stopPropagation();
    cutEditor.draggingIndex = Number(index);
    cutEditor.selectedIndex = Number(index);

    const move = ev => {
      if (cutEditor.draggingIndex == null) return;
      const logicalY = pointerToLogicalY(ev.clientY);
      if (logicalY == null) return;
      const { total } = logicalMetrics();
      cutEditor.cuts[cutEditor.draggingIndex] = Math.max(1, Math.min(total - 1, logicalY));
      cutEditor.cuts.sort((a, b) => a - b);
      cutEditor.selectedIndex = cutEditor.cuts.indexOf(Math.max(1, Math.min(total - 1, logicalY)));
      renderRulers();
    };

    const up = () => {
      cutEditor.draggingIndex = null;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      renderRulers();
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    renderRulers();
  }

  function zoom(delta) {
    const stream = document.getElementById("mmStream");
    if (!stream) return;

    const next = Math.min(
      1.5,
      Math.max(0.4, Number(window.__mergeManualZoom || 1) + Number(delta || 0))
    );

    window.__mergeManualZoom = Number(next.toFixed(2));

    const label = document.getElementById("mmZoomLabel");
    if (label) label.textContent = `${Math.round(window.__mergeManualZoom * 100)}%`;

    requestAnimationFrame(() => {
      layoutSourceSlices();
      renderRulers();
    });
  }

  async function waitJob(jobId){
    while(true){
      const response=await fetch(`/api/job/${encodeURIComponent(jobId)}?_=${Date.now()}`,{cache:"no-store"});
      const job=await response.json();
      if(!response.ok)throw new Error(job?.error||`HTTP ${response.status}`);
      if(job.status==="done")return job.result;
      if(job.status==="error")throw new Error(job.error||job.message||"Falha ao gerar proposta.");
      await new Promise(resolve=>setTimeout(resolve,400));
    }
  }

  function renderProposalResult(proposal){
    const host=document.getElementById("mmProposalResult");
    if(!host)return;
    currentProposal=proposal||null;
    if(!proposal||!["PROPOSTA_GERADA","EFETIVADO"].includes(proposal.status)){host.innerHTML="";return;}
    const ctx=context();
    const applied=proposal.status==="EFETIVADO";
    host.innerHTML=`<section class="panel mm-proposal-result">
      <div class="mm-proposal-head"><div><span class="mm-eyebrow">${applied?"COMPOSIÇÃO FINAL":"RESULTADO"}</span><b>${Number(proposal.outputs?.length||0)} bloco(s)</b></div><span>Proposta ${htmlEsc(proposal.proposal_id)}</span></div>
      <div class="mm-proposal-grid">${(proposal.outputs||[]).map((item,index)=>`<figure class="mm-proposal-card"><div class="mm-proposal-image"><img loading="lazy" src="/media?provider=${encodeURIComponent(ctx.provider)}&manga=${encodeURIComponent(ctx.manga)}&kind=merge_manual_proposal&chapter=${encodeURIComponent(proposal.chapter)}&proposal=${encodeURIComponent(proposal.proposal_id)}&file=${encodeURIComponent(item.file)}" alt="Bloco ${index+1}"></div><figcaption><b>Bloco ${index+1}</b><span>${Number(item.height||0).toLocaleString("pt-BR")} px</span></figcaption></figure>`).join("")}</div>
      <div class="mm-proposal-actions">
        <span>${applied?"Composição efetivada e MERGE oficial validado.":"A proposta foi gerada, mas a efetivação não foi concluída."}</span>
      </div>
    </section>`;
  }

  async function loadLatestProposal(){
    const selection=loadSelection(),ctx=context();
    if(!selection||!ctx.manga)return;
    try{
      const response=await fetch(`/api/merge-manual-proposal?provider=${encodeURIComponent(ctx.provider)}&manga=${encodeURIComponent(ctx.manga)}&chapter=${encodeURIComponent(selection.chapter)}&_=${Date.now()}`,{cache:"no-store"});
      const payload=await response.json();
      if(response.ok&&["PROPOSTA_GERADA","EFETIVADO"].includes(payload?.proposal?.status))renderProposalResult(payload.proposal);
    }catch(_){ }
  }

  async function generateProposal(){
    const selection=loadSelection(),ctx=context();
    if(!selection||proposalBusy)return;
    normalizeCuts();
    const {total}=logicalMetrics();
    if(!total||!cutEditor.cuts.length){
      if(typeof toast==="function")toast("Adicione pelo menos uma régua válida antes de gerar Novos Cortes.");
      return;
    }

    proposalBusy=true;
    renderRulers();

    let proposal=null;
    try{
      const generateResponse=await fetch("/api/action",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          action:"merge_manual_generate",
          provider:ctx.provider,
          manga:ctx.manga,
          chapters:[String(selection.chapter)],
          chapter:String(selection.chapter),
          block_id:String(selection.blockId),
          start:String(selection.start),
          end:String(selection.end),
          cuts:[...cutEditor.cuts]
        })
      });
      const generateAccepted=await generateResponse.json();
      if(!generateResponse.ok||!generateAccepted?.job_id){
        throw new Error(generateAccepted?.error||`HTTP ${generateResponse.status}`);
      }

      proposal=await waitJob(generateAccepted.job_id);
      currentProposal=proposal;

      const applyResponse=await fetch("/api/action",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          action:"merge_manual_apply",
          provider:ctx.provider,
          manga:ctx.manga,
          chapters:[String(selection.chapter)],
          chapter:String(selection.chapter),
          proposal_id:String(proposal.proposal_id)
        })
      });
      const applyAccepted=await applyResponse.json();
      if(!applyResponse.ok||!applyAccepted?.job_id){
        throw new Error(applyAccepted?.error||`HTTP ${applyResponse.status}`);
      }

      const result=await waitJob(applyAccepted.job_id);
      const applied={
        ...proposal,
        status:"EFETIVADO",
        applied_at:new Date().toISOString(),
        official_merge:{merged_images:Number(result?.merged_images||0)}
      };
      currentProposal=applied;
      renderProposalResult(applied);

      if(typeof toast==="function"){
        toast(
          result?.already_applied
            ? "Esta composição já havia sido efetivada."
            : "Novos Cortes aplicados. MERGE oficial validado."
        );
      }

      try{
        const page=document.getElementById("page");
        ui.payload=null;
        ui.cacheKey="";
        if(page)await ensurePayload(page,true);
      }catch(_){}

    }catch(error){
      if(proposal){
        currentProposal=proposal;
        renderProposalResult(proposal);
      }
      if(typeof toast==="function")toast(error?.message||String(error));
    }finally{
      proposalBusy=false;
      renderRulers();
      if(currentProposal)renderProposalResult(currentProposal);
    }
  }


  function setQuery(value) { ui.query = value || ""; renderValidation(document.getElementById("page")); }
  function setStatus(value) { ui.status = value || "all"; renderValidation(document.getElementById("page")); }
  function selectChapter(chapter) {
    ui.selectedChapter = chapter;
    ui.selected = null;
    const row = (ui.payload?.chapters || []).find(item => String(item.chapter) === String(chapter));
    if (row?.status === "pending") ensureSelectedRange(row);
    renderValidation(document.getElementById("page"));
  }

  function applyNavState() {
    const group = document.querySelector("[data-merge-manual-nav]");
    if (!group) return;
    const saved = localStorage.getItem("fominha.mergeManual.expanded");
    const open = saved !== "0";
    group.classList.toggle("open", open);
    group.querySelector(".merge-manual-toggle")?.setAttribute("aria-expanded", String(open));
  }

  function toggleNav(button) {
    const group = button?.closest("[data-merge-manual-nav]");
    if (!group) return;
    const open = !group.classList.contains("open");
    group.classList.toggle("open", open);
    button.setAttribute("aria-expanded", String(open));
    localStorage.setItem("fominha.mergeManual.expanded", open ? "1" : "0");
  }

  window.toggleMergeManualNav = toggleNav;
  function changePreviewZoom(delta) {
    previewZoom = Math.max(60, Math.min(180, previewZoom + Number(delta || 0)));
    renderValidation(document.getElementById("page"));
  }

  function resetPreviewZoom() {
    previewZoom = 100;
    renderValidation(document.getElementById("page"));
  }

  window.MergeManualUI = {
    renderValidation,
    renderCuts,
    setQuery,
    setStatus,
    selectChapter,
    setRange,
    submitRange,
    changePreviewZoom,
    resetPreviewZoom,
    addRuler,
    removeRuler,
    selectRuler,
    beginRulerDrag,
    generateProposal,
    zoom,
    refresh() {
      ui.payload = null;
      ui.cacheKey = "";
      ensurePayload(document.getElementById("page"), true);
    },
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", applyNavState, { once: true });
  else applyNavState();
})();
