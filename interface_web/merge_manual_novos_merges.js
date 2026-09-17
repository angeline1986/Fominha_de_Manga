(() => {
  const state = {
    selection: null,
    cuts: [],
    color: "red",
    zoom: 50,
    proposal: null,
    busy: false,
    focus: false,
    dragIndex: null,
    totalHeight: 0,
    renderedHeight: 0,
  };

  const esc = s => String(s ?? "").replace(/[&<>"']/g, m => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[m]));

  const ctx = () => ({
    provider: document.querySelector("#provider")?.value || "",
    manga: document.querySelector("#manga")?.value || ""
  });

  function storedSelection() {
    try {
      return JSON.parse(localStorage.getItem("fominha.mergeManual.selection.v1") || "null");
    } catch (_) {
      return null;
    }
  }

  async function json(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Erro na operação.");
    return payload;
  }

  async function postAction(action, payload) {
    const response = await json("/api/action", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({action, ...payload})
    });
    const id = response.job_id;
    if (!id) throw new Error("Job não foi criado.");
    for (;;) {
      await new Promise(r => setTimeout(r, 350));
      const job = await json(`/api/job/${encodeURIComponent(id)}?_=${Date.now()}`);
      if (job.status === "done") return job;
      if (job.status === "error") throw new Error(job.error || job.message || "Falha no processamento.");
    }
  }

  function mediaUrl(file, slice) {
    const c = ctx();
    const p = new URLSearchParams({
      provider: c.provider,
      manga: c.manga,
      chapter: state.selection.chapter,
      kind: "source",
      file
    });
    return `/media?${p.toString()}`;
  }

  function proposalUrl(file) {
    const c = ctx();
    const p = new URLSearchParams({
      provider: c.provider,
      manga: c.manga,
      chapter: state.selection.chapter,
      kind: "merge_manual_proposal",
      proposal: state.proposal.proposal_id,
      file
    });
    return `/media?${p.toString()}&_=${Date.now()}`;
  }

  function selectionValid(sel) {
    const c = ctx();
    return !!sel &&
      sel.provider === c.provider &&
      sel.manga === c.manga &&
      !!sel.chapter && !!sel.blockId &&
      !!sel.start && !!sel.end &&
      Array.isArray(sel.slices) && sel.slices.length;
  }

  async function refreshAuthoritativeSelection() {
    const sel = storedSelection();
    if (!selectionValid(sel)) return null;
    const c = ctx();
    const p = new URLSearchParams({provider:c.provider, manga:c.manga});
    const payload = await json(`/api/merge-manual?${p.toString()}&_=${Date.now()}`);
    const chapter = (payload.chapters || []).find(x => String(x.chapter) === String(sel.chapter));
    if (!chapter || chapter.status !== "pending") return null;
    const block = (chapter.pending_blocks || []).find(x => String(x.id) === String(sel.blockId));
    if (!block) return null;
    const names = (block.pages || []).map(x => String(x.file));
    const a = names.indexOf(String(sel.start));
    const b = names.indexOf(String(sel.end));
    if (a < 0 || b < a) return null;

    // Não confia nas geometrias persistidas no localStorage. O snapshot serve
    // apenas para identificar a seleção; as fatias são reconstruídas do estado
    // autoritativo atual antes de desenhar ou gerar qualquer proposta.
    const pages = (block.pages || []).slice(a, b + 1);
    const slices = pages.map(item => ({
      file: String(item.file),
      sourceYStart: Number(item.source_y_start || 0),
      sourceYEnd: Number(item.source_y_end ?? item.height ?? 0),
      sourceHeight: Number(item.height || 0),
      pendingHeight: Number(item.pending_height || 0),
    }));
    const globalStart = Math.max(Number(block.global_start), Number(pages[0].global_start));
    const globalEnd = Math.min(Number(block.global_end), Number(pages[pages.length - 1].global_end));
    const pending = (chapter.pending_blocks || []).map(item => ({
      id: String(item.id),
      globalStart: Number(item.global_start),
      globalEnd: Number(item.global_end),
    }));
    const canApplyFinal = pending.length === 1 &&
      String(pending[0].id) === String(block.id) &&
      globalStart === Number(block.global_start) &&
      globalEnd === Number(block.global_end);

    return {
      ...sel,
      files: pages.map(item => String(item.file)),
      slices,
      count: pages.length,
      globalStart,
      globalEnd,
      authoritativeBlockStart: Number(block.global_start),
      authoritativeBlockEnd: Number(block.global_end),
      authoritativePendingBlocks: pending,
      canApplyFinal,
    };
  }

  function logicalHeight() {
    return (state.selection?.slices || []).reduce((sum, s) => sum + Number(s.pendingHeight || 0), 0);
  }

  function cutColor() {
    return state.color === "green" ? "#2f9e62" : state.color === "blue" ? "#3478d4" : "#e5484d";
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function distributeCuts(count) {
    const n = clamp(Number.parseInt(count || 1, 10) || 1, 1, 20);
    if (!state.totalHeight) return [];
    return Array.from({length:n}, (_, i) => Math.round(state.totalHeight * (i + 1) / (n + 1)));
  }

  function focusBarHtml() {
    const s = state.selection;
    return `<div class="mmnm-focus-bar" data-mm-focus-bar hidden>
      <div class="mmnm-focus-identity">
        <strong>MERGE MANUAL › Novos Merges › Capítulo</strong>
        <span>Cap. ${esc(s.chapter)}</span>
      </div>
      <div class="mmnm-focus-controls">
        ${toolbarControlsHtml(true)}
        <button type="button" class="btn" data-mm-focus-exit>Sair do foco</button>
      </div>
    </div>`;
  }

  function colorButtonsHtml() {
    return `<span class="mmnm-colors" aria-label="Cor das réguas">
      ${[["red","#e5484d"],["green","#2f9e62"],["blue","#3478d4"]].map(([name,color]) =>
        `<button type="button" class="mmnm-color-btn ${state.color===name ? "active" : ""}" data-mm-color="${name}" style="--mm-color:${color}" aria-label="Régua ${name}"><i></i></button>`
      ).join("")}
    </span>`;
  }

  function toolbarControlsHtml(focus=false) {
    return `<span class="mmnm-zoom-control" aria-label="Controle de zoom do capítulo">
        <button type="button" class="mmnm-zoom-action" data-mm-zoom-out ${state.zoom<=30 ? "disabled" : ""}>−</button>
        <b class="mmnm-zoom-value" data-mm-zoom-value>${state.zoom}%</b>
        <button type="button" class="mmnm-zoom-action" data-mm-zoom-in ${state.zoom>=200 ? "disabled" : ""}>+</button>
        <button type="button" class="mmnm-zoom-reset" data-mm-zoom-reset ${state.zoom===100 ? "disabled" : ""}>100%</button>
      </span>
      <span class="mmnm-toolbar-divider" aria-hidden="true"></span>
      <small>Réguas de corte</small>
      <input class="mmnm-cut-count" data-mm-cut-count type="number" min="1" max="20" step="1" value="${state.cuts.length || 1}">
      <button type="button" class="btn mmnm-count-action" data-mm-count="-1">−</button>
      <button type="button" class="btn mmnm-count-action" data-mm-count="1">+</button>
      ${colorButtonsHtml()}
      <button type="button" class="btn primary" data-mm-generate ${state.cuts.length && !state.busy ? "" : "disabled"}>${state.busy ? "Processando..." : "Novos Merges"}</button>
      ${focus ? "" : '<button type="button" class="btn mmnm-focus-entry" data-mm-focus>Modo foco</button>'}`;
  }

  function renderShell(root) {
    const s = state.selection;
    root.innerHTML = `${focusBarHtml()}
      <div class="mmnm-page">
        <div class="mmnm-head">
          <div>
            <div class="caption">MERGE MANUAL</div>
            <h1>Novos Merges</h1>
            <p>Capítulo ${esc(s.chapter)} · ${esc(s.start)} → ${esc(s.end)} · ${esc(s.count || s.slices.length)} página(s) residuais</p>
          </div>
          <button class="btn" data-mm-back>Voltar para Validar</button>
        </div>

        <section class="mmnm-editor-card">
          <div class="mmnm-toolbar">
            <strong>Cap. ${esc(s.chapter)}</strong>
            <span class="mmnm-toolbar-controls">${toolbarControlsHtml(false)}</span>
          </div>
          <div class="mmnm-editor-body">
            <div class="mmnm-editor-scroll">
              <div class="mmnm-canvas-wrap" data-mm-wrap style="width:${state.zoom}%">
                <div class="mmnm-canvas" data-mm-canvas>
                  ${(s.slices || []).map((slice, i) => `
                    <div class="mmnm-slice" data-slice="${i}" data-logical-height="${Number(slice.pendingHeight || 0)}">
                      <img src="${mediaUrl(slice.file, slice)}" alt="${esc(slice.file)}"
                           data-y-start="${Number(slice.sourceYStart || 0)}"
                           data-y-end="${Number(slice.sourceYEnd || 0)}">
                    </div>`).join("")}
                  <div class="mmnm-rulers" data-mm-rulers></div>
                </div>
                <div class="mmnm-slice-labels">
                  ${(s.slices || []).map((slice, i) => `<span class="mmnm-slice-label ${i%2===0?'is-tinted':''}" data-mm-slice-label="${i}"><b>${esc(slice.file)}</b></span>`).join("")}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="mmnm-result-card" data-mm-result>
          <div class="mmnm-section-head"><div><div class="caption">RESULTADO</div><h2>Composição proposta</h2></div></div>
          <div class="muted">Gere os novos merges para visualizar a proposta antes de efetivar.</div>
        </section>
      </div>`;
    bind(root);
    syncFocusUi(root);
    requestAnimationFrame(() => prepareImages(root));
  }

  async function prepareImages(root) {
    const slices = [...root.querySelectorAll(".mmnm-slice")];
    for (const slice of slices) {
      const img = slice.querySelector("img");
      await new Promise(resolve => {
        if (img.complete) resolve();
        else { img.onload = resolve; img.onerror = resolve; }
      });
      const y0 = Number(img.dataset.yStart || 0);
      const y1 = Number(img.dataset.yEnd || 0);
      const logical = Number(slice.dataset.logicalHeight || 0);
      if (img.naturalHeight > 0 && y1 > y0) {
        const visibleRatio = (y1 - y0) / img.naturalHeight;
        img.style.height = `${100 / visibleRatio}%`;
        img.style.transform = `translateY(${-100 * (y0 / img.naturalHeight)}%)`;
        slice.style.aspectRatio = `${img.naturalWidth} / ${Math.max(1, y1-y0)}`;
      } else if (logical > 0 && img.naturalWidth > 0) {
        slice.style.aspectRatio = `${img.naturalWidth} / ${logical}`;
      }
    }
    state.totalHeight = logicalHeight();
    if (!state.cuts.length && state.totalHeight) state.cuts = distributeCuts(1);
    positionSliceLabels(root);
    drawRulers(root);
    syncToolbarUi(root);
  }

  function positionSliceLabels(root) {
    const total = state.totalHeight || logicalHeight();
    let offset = 0;
    (state.selection?.slices || []).forEach((slice, i) => {
      const h = Number(slice.pendingHeight || 0);
      const label = root.querySelector(`[data-mm-slice-label="${i}"]`);
      if (label && total > 0) {
        label.style.top = `${offset / total * 100}%`;
        label.style.height = `${h / total * 100}%`;
      }
      offset += h;
    });
  }

  function drawRulers(root) {
    const canvas = root.querySelector("[data-mm-canvas]");
    const layer = root.querySelector("[data-mm-rulers]");
    if (!canvas || !layer || !state.totalHeight) return;
    layer.innerHTML = state.cuts.map((cut, i) => {
      const pct = clamp(cut / state.totalHeight, .001, .999) * 100;
      return `<div class="mmnm-ruler" data-cut-index="${i}" style="top:${pct}%;--mm-ruler-color:${cutColor()}"><span>Corte ${i+1}</span></div>`;
    }).join("");
    layer.querySelectorAll(".mmnm-ruler").forEach(line => {
      line.addEventListener("pointerdown", ev => startCutDrag(ev, Number(line.dataset.cutIndex), root));
    });
  }

  function startCutDrag(event, index, root) {
    event.preventDefault();
    const canvas = root.querySelector("[data-mm-canvas]");
    const line = canvas?.querySelector(`[data-cut-index="${index}"]`);
    if (!canvas || !line || !state.totalHeight) return;
    state.dragIndex = index;
    const move = ev => {
      const rect = canvas.getBoundingClientRect();
      const pct = clamp((ev.clientY - rect.top) / Math.max(1, rect.height), .001, .999);
      line.style.top = `${pct * 100}%`;
      state.cuts[index] = Math.round(pct * state.totalHeight);
    };
    const up = () => {
      document.removeEventListener("pointermove", move);
      state.dragIndex = null;
      state.cuts = [...state.cuts].sort((a,b)=>a-b);
      drawRulers(root);
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up, {once:true});
  }

  function setCutCount(value, root) {
    state.cuts = distributeCuts(value);
    drawRulers(root);
    syncToolbarUi(root);
  }

  function setZoom(value, root) {
    state.zoom = clamp(Number(value), 30, 200);
    const wrap = root.querySelector("[data-mm-wrap]");
    if (wrap) wrap.style.width = `${state.zoom}%`;
    syncToolbarUi(root);
  }

  function syncToolbarUi(root) {
    root.querySelectorAll("[data-mm-zoom-value]").forEach(el => el.textContent = `${state.zoom}%`);
    root.querySelectorAll("[data-mm-zoom-out]").forEach(el => el.disabled = state.zoom <= 30);
    root.querySelectorAll("[data-mm-zoom-in]").forEach(el => el.disabled = state.zoom >= 200);
    root.querySelectorAll("[data-mm-zoom-reset]").forEach(el => el.disabled = state.zoom === 100);
    root.querySelectorAll("[data-mm-cut-count]").forEach(el => el.value = state.cuts.length || 1);
    root.querySelectorAll("[data-mm-generate]").forEach(el => el.disabled = !state.cuts.length || state.busy);
    root.querySelectorAll("[data-mm-color]").forEach(el => el.classList.toggle("active", el.dataset.mmColor === state.color));
  }

  function syncFocusUi(root) {
    document.body.classList.toggle("merge-manual-novos-merges-focus", state.focus);
    const bar = root.querySelector("[data-mm-focus-bar]");
    if (bar) bar.hidden = !state.focus;
  }

  function bindControls(root, scope) {
    scope.querySelector("[data-mm-zoom-out]")?.addEventListener("click", () => setZoom(state.zoom - 10, root));
    scope.querySelector("[data-mm-zoom-in]")?.addEventListener("click", () => setZoom(state.zoom + 10, root));
    scope.querySelector("[data-mm-zoom-reset]")?.addEventListener("click", () => setZoom(100, root));
    scope.querySelector("[data-mm-cut-count]")?.addEventListener("change", ev => setCutCount(ev.target.value, root));
    scope.querySelectorAll("[data-mm-count]").forEach(btn => btn.addEventListener("click", () => setCutCount((state.cuts.length || 1) + Number(btn.dataset.mmCount), root)));
    scope.querySelectorAll("[data-mm-color]").forEach(btn => btn.addEventListener("click", () => {
      state.color = btn.dataset.mmColor;
      drawRulers(root);
      syncToolbarUi(root);
    }));
    scope.querySelector("[data-mm-generate]")?.addEventListener("click", () => generate(root));
  }

  function bind(root) {
    root.querySelector("[data-mm-back]")?.addEventListener("click", () => {
      state.focus = false;
      syncFocusUi(root);
      document.querySelector('button[data-page="merge_manual"]')?.click();
    });
    bindControls(root, root.querySelector(".mmnm-toolbar"));
    bindControls(root, root.querySelector("[data-mm-focus-bar]"));
    root.querySelector("[data-mm-focus]")?.addEventListener("click", () => { state.focus = true; syncFocusUi(root); });
    root.querySelector("[data-mm-focus-exit]")?.addEventListener("click", () => { state.focus = false; syncFocusUi(root); });
    window.addEventListener("resize", () => drawRulers(root), {once:true});
  }

  async function generate(root) {
    if (!state.cuts.length || state.busy) return;
    state.busy = true;
    renderShell(root);
    try {
      const c = ctx();
      const s = state.selection;
      await postAction("merge_manual_generate", {
        provider:c.provider, manga:c.manga,
        chapters:[s.chapter],
        chapter:s.chapter,
        block_id:s.blockId,
        start:s.start,
        end:s.end,
        cuts:state.cuts
      });
      const p = new URLSearchParams({provider:c.provider, manga:c.manga, chapter:s.chapter});
      const latest = await json(`/api/merge-manual-proposal?${p.toString()}&_=${Date.now()}`);
      if (!latest.proposal) throw new Error("A proposta foi processada, mas não pôde ser carregada.");
      state.proposal = latest.proposal;
      renderShell(root);
      renderResult(root);
    } catch (e) {
      alert(e.message || String(e));
      state.busy = false;
      renderShell(root);
    } finally {
      state.busy = false;
    }
  }

  function renderResult(root) {
    const box = root.querySelector("[data-mm-result]");
    const p = state.proposal;
    if (!box || !p) return;
    const outputs = p.outputs || [];
    box.innerHTML = `
      <div class="mmnm-section-head">
        <div>
          <div class="caption">RESULTADO</div>
          <h2>${outputs.length} novo(s) merge(s)</h2>
          <p>Proposta ${esc(p.proposal_id)} · o MERGE oficial ainda não foi alterado.</p>
        </div>
        <button class="btn primary" data-mm-apply ${state.selection.canApplyFinal ? "" : "disabled"}>Efetivar composição</button>
      </div>
      ${state.selection.canApplyFinal ? "" : `
        <div class="mmnm-business-warning">
          A proposta pode ser revisada, mas não pode ser efetivada porque a seleção não cobre todo o residual autoritativo do capítulo.
          Volte para Validar e selecione o bloco residual completo.
        </div>`}
      <div class="mmnm-result-grid">
        ${outputs.map((o,i)=>`
          <figure>
            <img src="${proposalUrl(o.file)}" alt="${esc(o.file)}">
            <figcaption>${esc(o.file)} · ${Number(o.height||0)} px</figcaption>
          </figure>`).join("")}
      </div>`;
    const applyButton = box.querySelector("[data-mm-apply]");
    if (applyButton && state.selection.canApplyFinal) applyButton.onclick = () => apply(root);
    box.scrollIntoView({behavior:"smooth", block:"start"});
  }

  async function apply(root) {
    if (!state.proposal) return;
    const ok = window.askAppModal
      ? await window.askAppModal(
          "Efetivar composição",
          "A proposta será promovida para o MERGE oficial. Confirme somente após revisar o resultado.",
          "Efetivar"
        )
      : confirm("Efetivar a composição no MERGE oficial?");
    if (!ok) return;
    try {
      const c = ctx();
      const s = state.selection;
      await postAction("merge_manual_apply", {
        provider:c.provider, manga:c.manga,
        chapters:[s.chapter],
        chapter:s.chapter,
        proposal_id:state.proposal.proposal_id
      });
      localStorage.removeItem("fominha.mergeManual.selection.v1");
      state.focus = false;
      document.body.classList.remove("merge-manual-novos-merges-focus");
      if (window.appModal) {
        await window.appModal({
          title:"Composição efetivada",
          message:`Capítulo ${s.chapter} atualizado com sucesso.`,
          confirmText:"OK",
          kind:"info"
        });
      } else {
        alert(`Capítulo ${s.chapter} atualizado com sucesso.`);
      }
      if (typeof window.load === "function") await window.load(true);
      document.querySelector('button[data-page="merge_manual"]')?.click();
    } catch (e) {
      alert(e.message || String(e));
    }
  }

  async function render(root) {
    document.body.classList.toggle("merge-manual-novos-merges-focus", state.focus);
    root.innerHTML = '<div class="muted">Validando seleção autoritativa...</div>';
    try {
      const selection = await refreshAuthoritativeSelection();
      if (!selection) {
        state.selection = null;
        root.innerHTML = `
          <div class="mmnm-empty">
            <h2>Nenhuma faixa residual selecionada</h2>
            <p>Volte para Merge Manual → Validar e selecione a faixa que será recomposta.</p>
            <button class="btn primary" data-mm-back-empty>Ir para Validar</button>
          </div>`;
        root.querySelector("[data-mm-back-empty]").onclick = () =>
          document.querySelector('button[data-page="merge_manual"]')?.click();
        return;
      }
      state.selection = selection;
      state.cuts = [];
      state.proposal = null;
      state.zoom = 50;
      state.totalHeight = logicalHeight();
      renderShell(root);
    } catch (e) {
      root.innerHTML = `<div class="mmnm-empty"><h2>Não foi possível abrir Novos Merges</h2><p>${esc(e.message || e)}</p></div>`;
    }
  }

  window.MergeManualNovosMergesUI = {render};
})();