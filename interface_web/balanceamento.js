(() => {
  "use strict";

  let state = null;
  let selectedChapter = null;
  let selectedMerges = new Set();
  let filter = "unbalanced";
  let pageIndex = 1;
  const pageSize = 10;
  let query = "";
  const openSections = {table: true, chapter: true, preview: true, proposal: true};
  let activeView = "validate";
  let submittedChapter = null;
  let submittedMerges = [];
  let proposalZoom = 100;

  const escLocal = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));

  function apiUrl() {
    return `/api/balance-analysis?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&_=${Date.now()}`;
  }

  function imageUrl(chapter, file) {
    return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=balance&chapter=${encodeURIComponent(chapter)}&file=${encodeURIComponent(file)}`;
  }

  function proposalImageUrl(chapter, proposalId, file) {
    return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=balance_proposal&chapter=${encodeURIComponent(chapter)}&proposal=${encodeURIComponent(proposalId)}&file=${encodeURIComponent(file)}`;
  }

  function flow(chapter) {
    const canRebalance = !!selectedChapter && selectedMerges.size >= 2;
    const canFinal = chapter?.proposal?.status === "PROPOSTA_GERADA";
    const steps = [
      ["validate", "Validar balanceamento", true],
      ["rebalance", "Efetuar balanceamento", canRebalance || activeView === "rebalance" || canFinal],
      ["final", "Composição final", canFinal],
    ];
    return `<div class="bal-flow">
      ${steps.map(([view,label,enabled]) => `<button type="button"
        class="bal-node ${activeView===view ? "current" : ""}"
        ${enabled ? "" : "disabled"}
        onclick="BalanceamentoUI.setView('${view}')"><i></i><span>${label}</span></button>`).join("")}
    </div>`;
  }

  function setView(view) {
    if (!["validate","rebalance","final"].includes(view)) return;
    const current = (state?.chapters || []).find(x => String(x.chapter) === String(selectedChapter));
    if (view === "final" && current?.proposal?.status !== "PROPOSTA_GERADA") {
      toast("A composição final só fica disponível após uma proposta SAFE.");
      return;
    }
    activeView = view;
    renderBody();
  }

  async function load() {
    try {
      state = await api(apiUrl());
      const badge = document.querySelector("#badgeBalance");
      if (badge) badge.textContent = state?.summary?.unbalanced ?? 0;
      if (selectedChapter && !state.chapters.some(x => String(x.chapter) === String(selectedChapter))) {
        selectedChapter = null;
        selectedMerges.clear();
      }
      renderBody();
    } catch (e) {
      toast(e.message || "Não foi possível validar o balanceamento.");
    }
  }

  function statusBadge(ch) {
    return ch.status === "DESBALANCEADO"
      ? `<span class="bal-status attention">Desbalanceado</span>`
      : `<span class="bal-status ok">Balanceado</span>`;
  }

  function filteredChapters() {
    let list = state?.chapters || [];
    if (filter === "balanced") list = list.filter(x => x.status === "BALANCEADO");
    if (filter === "unbalanced") list = list.filter(x => x.status === "DESBALANCEADO");
    const q = query.trim().toLowerCase();
    if (q) list = list.filter(x => String(x.chapter).toLowerCase().includes(q));
    return list;
  }

  function pagedChapters() {
    const list = filteredChapters();
    const totalPages = Math.max(1, Math.ceil(list.length / pageSize));
    pageIndex = Math.min(Math.max(1, pageIndex), totalPages);
    const start = (pageIndex - 1) * pageSize;
    return {list, totalPages, rows: list.slice(start, start + pageSize)};
  }

  function pager(totalPages, totalRows) {
    if (totalRows <= pageSize) return "";
    const start = totalRows ? ((pageIndex - 1) * pageSize + 1) : 0;
    const end = Math.min(pageIndex * pageSize, totalRows);
    return `<div class="table-pager">
      <span>${start}–${end} de ${totalRows}</span>
      <div>
        <button class="btn" ${pageIndex<=1 ? "disabled" : ""} onclick="BalanceamentoUI.changePage(-1)">&lt;&lt;</button>
        <span class="page-indicator">${pageIndex} / ${totalPages}</span>
        <button class="btn" ${pageIndex>=totalPages ? "disabled" : ""} onclick="BalanceamentoUI.changePage(1)">&gt;&gt;</button>
      </div>
    </div>`;
  }

  function toggleSection(which) {
    openSections[which] = !openSections[which];
    renderBody();
  }

  function selectChapter(chapter) {
    selectedChapter = String(chapter);
    selectedMerges.clear();
    renderBody();
  }

  function toggleMerge(file, checked) {
    if (checked) selectedMerges.add(file);
    else selectedMerges.delete(file);
    const submitButton = document.querySelector("#balSubmitSelected");
    if (submitButton) submitButton.disabled = selectedMerges.size < 2;
    renderPreviewOnly();
  }

  function renderPreviewOnly() {
    const chapter = (state?.chapters || []).find(x => String(x.chapter) === String(selectedChapter));
    const host = document.querySelector("#balSelectedPreview");
    const count = document.querySelector("#balSelectedCount");
    if (!host || !chapter) return;
    const chosen = chapter.merges.filter(x => selectedMerges.has(x.file));
    if (count) count.textContent = `${chosen.length} selecionado(s)`;
    host.innerHTML = chosen.length
      ? chosen.map(x => `<article class="bal-preview-card">
          <div class="bal-preview-stage"><img src="${imageUrl(chapter.chapter,x.file)}" alt="${escLocal(x.file)}"></div>
          <div class="bal-preview-meta"><b>${escLocal(x.file)}</b><span>${Number(x.height||0).toLocaleString("pt-BR")} px</span></div>
        </article>`).join("")
      : `<div class="bal-empty">Selecione um ou mais merges para visualizar.</div>`;
  }

  function chapterSection(chapter) {
    if (!chapter) return "";
    const maxHeight = Math.max(1, ...chapter.merges.map(x => Number(x.height)||0));
    const rows = chapter.merges.map(x => {
      const pct = Math.max(2, Math.round(((Number(x.height)||0) / maxHeight) * 100));
      const issue = x.status === "DESBALANCEADO";
      return `<tr class="${issue ? "bal-row-issue" : ""}">
        <td><input type="checkbox" ${selectedMerges.has(x.file) ? "checked" : ""} onchange="BalanceamentoUI.toggleMerge('${escLocal(x.file)}',this.checked)"></td>
        <td><b>${escLocal(x.file)}</b>${issue ? `<small>${escLocal(x.reason)}</small>` : ""}</td>
        <td>${x.height == null ? "—" : Number(x.height).toLocaleString("pt-BR")+" px"}</td>
        <td><div class="bal-bar"><span style="width:${pct}%"></span></div></td>
      </tr>`;
    }).join("");

    const notice = chapter.status === "DESBALANCEADO"
      ? `<div class="bal-notice"><b>Desbalanceamento localizado.</b> ${chapter.issues_count} merge(s) interno(s) abaixo de 50% da média dos vizinhos.</div>`
      : `<div class="bal-okbox"><b>Capítulo balanceado.</b> Nenhum merge interno violou a regra de balanceamento.</div>`;

    return `<section class="bal-section">
      <button class="bal-section-head" onclick="BalanceamentoUI.toggleSection('chapter')" aria-expanded="${openSections.chapter}">
        <span>Cap. ${escLocal(chapter.chapter)}</span>
        <span class="bal-section-head-right">${statusBadge(chapter)}<i class="bal-chevron">${openSections.chapter ? "▼" : "▶"}</i></span>
      </button>
      ${openSections.chapter ? `<div class="bal-section-body">${notice}
        <table class="bal-merge-table"><thead><tr><th></th><th>MERGE</th><th>ALTURA</th><th>DISTRIBUIÇÃO</th></tr></thead><tbody>${rows}</tbody></table>
        <div class="bal-actions"><button id="balSubmitSelected" class="btn primary" ${selectedMerges.size >= 2 ? "" : "disabled"} onclick="BalanceamentoUI.submitSelected()" title="Gera uma proposta SAFE sem alterar o MERGE final">Submeter selecionados a novo balanceamento</button></div>
      </div>` : ""}
    </section>`;
  }

  function previewSection() {
    return `<section class="bal-section">
      <button class="bal-section-head" onclick="BalanceamentoUI.toggleSection('preview')" aria-expanded="${openSections.preview}">
        <span>Visualização dos merges selecionados</span>
        <span class="bal-section-head-right"><small id="balSelectedCount">${selectedMerges.size} selecionado(s)</small><i class="bal-chevron">${openSections.preview ? "▼" : "▶"}</i></span>
      </button>
      ${openSections.preview ? `<div class="bal-section-body"><div id="balSelectedPreview" class="bal-preview-grid"></div></div>` : ""}
    </section>`;
  }

  function proposalSection(chapter) {
    const proposal = chapter?.proposal;
    if (!proposal) return "";

    const ok = proposal.status === "PROPOSTA_GERADA";
    const artifacts = Array.isArray(proposal.artifacts) ? proposal.artifacts : [];
    const cuts = Array.isArray(proposal.cuts) ? proposal.cuts : [];

    const cards = ok && artifacts.length
      ? artifacts.map((x, index) => `<article class="bal-preview-card">
          <div class="bal-preview-stage" style="overflow:auto">
            <img
              src="${proposalImageUrl(chapter.chapter,proposal.proposal_id,x.file)}"
              alt="${escLocal(x.file)}"
              style="width:${proposalZoom}%;max-width:none;height:auto;display:block;margin:0 auto"
            >
          </div>
          <div class="bal-preview-meta">
            <b>Bloco ${index + 1}</b>
            <span>${escLocal(x.file)} · ${Number(x.height||0).toLocaleString("pt-BR")} px</span>
          </div>
        </article>`).join("")
      : `<div class="bal-empty">${escLocal(proposal.message || "Nenhuma proposta SAFE disponível.")}</div>`;

    const cutsHtml = ok && cuts.length
      ? `<div class="bal-notice" style="margin-top:12px">
          <b>Cortes utilizados</b>
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">
            ${cuts.map((cut, index) => {
              const selected = cut?.selected_y ?? cut?.anchor_y ?? "—";
              const reason = cut?.safety_reason || cut?.anchor_reason || "";
              return `<span class="bal-status ok">Corte ${index + 1}: ${escLocal(selected)}${reason ? ` · ${escLocal(reason)}` : ""}</span>`;
            }).join("")}
          </div>
        </div>`
      : "";

    const zoomControls = ok && artifacts.length
      ? `<div style="display:flex;align-items:center;gap:8px;margin:12px 0">
          <span class="muted">ZOOM</span>
          <button type="button" class="btn" onclick="BalanceamentoUI.changeProposalZoom(-10)" ${proposalZoom <= 30 ? "disabled" : ""}>−</button>
          <b style="min-width:48px;text-align:center">${proposalZoom}%</b>
          <button type="button" class="btn" onclick="BalanceamentoUI.changeProposalZoom(10)" ${proposalZoom >= 200 ? "disabled" : ""}>+</button>
          <button type="button" class="btn" onclick="BalanceamentoUI.resetProposalZoom()" ${proposalZoom === 100 ? "disabled" : ""}>100%</button>
        </div>`
      : "";

    return `<section class="bal-section">
      <button class="bal-section-head" onclick="BalanceamentoUI.toggleSection('proposal')" aria-expanded="${openSections.proposal}">
        <span>Efetuar balanceamento · Cap. ${escLocal(chapter.chapter)}</span>
        <span class="bal-section-head-right"><small>${ok ? "Proposta SAFE" : "Sem proposta"}</small><i class="bal-chevron">${openSections.proposal ? "▼" : "▶"}</i></span>
      </button>
      ${openSections.proposal ? `<div class="bal-section-body">
        <div class="${ok ? "bal-okbox" : "bal-notice"}"><b>${ok ? "Proposta gerada." : "Proposta não gerada."}</b> ${escLocal(proposal.message || "")}</div>
        ${cutsHtml}
        ${zoomControls}
        ${ok ? `<div class="bal-preview-grid">${cards}</div>` : cards}
      </div>` : ""}
    </section>`;
  }

  async function submitSelected() {
    if (!selectedChapter) return;
    if (selectedMerges.size < 2) {
      toast("Selecione pelo menos 2 merges contíguos.");
      return;
    }

    const chapter = selectedChapter;
    const merges = [...selectedMerges];
    submittedChapter = String(chapter);
    submittedMerges = [...merges];

    activeView = "rebalance";
    renderBody();

    const button = document.querySelector("#balSubmitSelected");
    const originalText = button?.textContent || "Submeter selecionados a novo balanceamento";

    if (button) {
      button.disabled = true;
      button.textContent = "Processando...";
    }

    try {
      const created = await api("/api/action", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          action: "balance_prepare",
          provider: data.provider,
          manga: data.manga,
          chapters: [chapter],
          merges
        })
      });

      const jobId = created?.job_id;
      if (!jobId) throw new Error("Job de balanceamento não foi criado.");

      while (true) {
        await new Promise(resolve => setTimeout(resolve, 500));
        const currentJob = await api("/api/job/" + encodeURIComponent(jobId));

        if (currentJob.status === "error") {
          throw new Error(currentJob.error || currentJob.message || "Falha ao efetuar balanceamento.");
        }
        if (currentJob.status === "done") break;
      }

      openSections.proposal = true;
      activeView = "rebalance";
      await load();

      const current = (state?.chapters || []).find(x => String(x.chapter) === String(chapter));
      const proposal = current?.proposal;
      if (proposal?.status === "PROPOSTA_GERADA") {
        toast("Cortes atuais carregados para edição.");
      } else if (proposal) {
        toast(proposal.message || "Nenhuma proposta SAFE encontrada.");
      }

      // Submissão concluída. Permanecer em Validar.
      renderBody();
    } catch (e) {
      toast(e.message || "Não foi possível gerar a proposta de balanceamento.");
    } finally {
      const currentButton = document.querySelector("#balSubmitSelected");
      if (currentButton) {
        currentButton.textContent = originalText;
        currentButton.disabled = selectedMerges.size === 0;
      }
    }
  }

  function rebalanceSection(chapter) {
    if (!chapter) return `<div class="bal-empty">Nenhum capítulo submetido para balanceamento.</div>`;
    const proposal = proposalSection(chapter);
    return `<div class="bal-detail-stack">
      ${proposal || `<section class="bal-section">
        <div class="bal-section-head">
          <span>Efetuar balanceamento · Cap. ${escLocal(chapter.chapter)}</span>
          <span class="bal-section-head-right"><small>Aguardando proposta</small></span>
        </div>
        <div class="bal-section-body">
          <div class="bal-notice"><b>Região submetida.</b> O sistema está procurando a composição SAFE com melhor distribuição de alturas.</div>
        </div>
      </section>`}
    </div>`;
  }

  function finalSection(chapter) {
    const proposal = chapter?.proposal;
    const ready = proposal?.status === "PROPOSTA_GERADA";
    return `<section class="bal-section">
      <div class="bal-section-head">
        <span>Composição final${chapter ? ` · Cap. ${escLocal(chapter.chapter)}` : ""}</span>
        <span class="bal-section-head-right"><small>${ready ? "Proposta SAFE disponível" : "Aguardando proposta"}</small></span>
      </div>
      <div class="bal-section-body">
        <div class="${ready ? "bal-okbox" : "bal-notice"}">
          <b>${ready ? "Proposta pronta para aprovação." : "Composição final indisponível."}</b>
          ${ready ? " Esta etapa ainda não altera o MERGE final." : " Gere uma proposta SAFE em Efetuar balanceamento."}
        </div>
        <div class="bal-actions">
          <button class="btn" onclick="BalanceamentoUI.setView('rebalance')">Voltar</button>
          <button class="btn primary" disabled>Aplicar composição final</button>
        </div>
      </div>
    </section>`;
  }

  function detailForActiveView(current) {
    if (activeView === "validate") {
      return current ? `<div class="bal-detail-stack">${chapterSection(current)}${previewSection()}</div>` : "";
    }
    if (activeView === "rebalance") return rebalanceSection(current);
    return finalSection(current);
  }

  function sourcePreviewUrl(chapter, proposal) {
    return proposalImageUrl(chapter.chapter, proposal.proposal_id, proposal.source_preview || "manual-source.png");
  }

  function manualEditorSection(chapter) {
    const proposal = chapter?.proposal;
    if (!proposal || !proposal.region || !proposal.source_preview) {
      return `<div class="bal-empty">Nenhum capítulo submetido para balanceamento.</div>`;
    }
    const start = Number(proposal.region.global_start);
    const end = Number(proposal.region.global_end);
    const total = end - start;
    const cuts = (proposal.cuts || []).map(x => Number(x.selected_y)).filter(Number.isFinite);
    if (!Array.isArray(window.__balManualCuts) || window.__balManualProposalId !== proposal.proposal_id) {
      window.__balManualCuts = cuts;
      window.__balManualProposalId = proposal.proposal_id;
    }
    const sliceLabels = (proposal.source_slices || []).map((x, idx) => {
      const sliceStart = Number(x.global_start);
      const sliceEnd = Number(x.global_end);
      const top = total > 0 && Number.isFinite(sliceStart) ? ((sliceStart - start) / total) * 100 : 0;
      const height = total > 0 && Number.isFinite(sliceStart) && Number.isFinite(sliceEnd)
        ? ((sliceEnd - sliceStart) / total) * 100 : 0;
      return `<span class="bal-manual-slice-label ${idx % 2 === 0 ? "is-tinted" : ""}" style="top:${top}%;height:${height}%"><b>${escLocal(x.file)}</b></span>`;
    }).join("");

    const sliceBands = (proposal.source_slices || []).map((x, idx) => {
      const sliceStart = Number(x.global_start);
      const sliceEnd = Number(x.global_end);
      const top = total > 0 && Number.isFinite(sliceStart) ? ((sliceStart - start) / total) * 100 : 0;
      const height = total > 0 && Number.isFinite(sliceStart) && Number.isFinite(sliceEnd)
        ? ((sliceEnd - sliceStart) / total) * 100 : 0;
      return `<span class="bal-manual-slice-band ${idx % 2 === 0 ? "is-tinted" : ""}" style="top:${top}%;height:${height}%"></span>`;
    }).join("");
    const lines = window.__balManualCuts.map((y, idx) => {
      const pct = total > 0 ? ((y - start) / total) * 100 : 0;
      return `<div class="bal-manual-cut" data-cut-index="${idx}" style="top:${pct}%"
                   onpointerdown="BalanceamentoUI.startCutDrag(event,${idx})"><span>Corte ${idx + 1}</span></div>`;
    }).join("");
    const result = proposal.status === "PROPOSTA_GERADA" && Array.isArray(proposal.artifacts)
      ? `<div class="bal-preview-grid">${proposal.artifacts.map((x, idx) =>
          `<article class="bal-preview-card"><div class="bal-preview-stage"><img src="${proposalImageUrl(chapter.chapter,proposal.proposal_id,x.file)}" alt="Bloco ${idx+1}"></div>
           <div class="bal-preview-meta"><b>Bloco ${idx+1}</b><span>${Number(x.height||0).toLocaleString("pt-BR")} px</span></div></article>`).join("")}</div>`
      : "";
    return `<div class="bal-detail-stack">
      <section class="bal-section">
        <div class="bal-section-head">
          <span>Cap. ${escLocal(chapter.chapter)}</span>
          <span class="bal-section-head-right" style="display:flex;align-items:center;gap:8px">
            <small>Réguas de corte</small>
            <input id="balManualCutCount" type="number" min="1" max="20" step="1" value="${window.__balManualCuts.length}" onchange="BalanceamentoUI.setManualCutCount(this.value)" style="width:58px;text-align:center;padding:5px 6px">
            <button type="button" class="btn" style="min-width:32px;padding:4px 8px" onclick="BalanceamentoUI.changeManualCutCount(-1)">−</button>
            <button type="button" class="btn" style="min-width:32px;padding:4px 8px" onclick="BalanceamentoUI.changeManualCutCount(1)">+</button>
          </span>
        </div>
        <div class="bal-section-body">
          <div class="bal-manual-toolbar" style="display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-bottom:12px">
            <span style="font-size:12px;font-weight:700">Zoom</span>
            <button type="button" class="btn" style="min-width:34px;padding:5px 9px" onclick="BalanceamentoUI.changeManualZoom(-10)">−</button>
            <span style="min-width:42px;text-align:center;font-size:12px;font-weight:800">${Number(window.__balManualZoom || 50)}%</span>
            <button type="button" class="btn" style="min-width:34px;padding:5px 9px" onclick="BalanceamentoUI.changeManualZoom(10)">+</button>
          </div>
          <div id="balManualViewport" style="overflow:auto">
            <div id="balManualWrap" style="position:relative;width:${Number(window.__balManualZoom || 50)}%;margin:0 auto;padding-right:118px;box-sizing:border-box">
              <div id="balManualCanvas" style="position:relative;width:100%;line-height:0;user-select:none;touch-action:none">
                <img src="${sourcePreviewUrl(chapter, proposal)}" alt="Slices originais do capítulo ${escLocal(chapter.chapter)}" style="display:block;width:100%;height:auto">
                <div class="bal-manual-slice-bands">${sliceBands}</div>
                ${lines}
              </div>
              <div class="bal-manual-slice-labels" style="position:absolute;top:0;bottom:0;right:0;width:108px;line-height:normal">${sliceLabels}</div>
            </div>
          </div>
          <style>
            #balManualCanvas .bal-manual-slice-bands{position:absolute;inset:0;pointer-events:none;z-index:2}
            #balManualCanvas .bal-manual-slice-band{position:absolute;left:0;right:0;box-sizing:border-box;border-top:1px solid rgba(133,105,114,.20)}
            #balManualCanvas .bal-manual-slice-band.is-tinted{background:rgba(193,220,145,.20)}
            #balManualCanvas .bal-manual-cut{position:absolute;left:0;right:0;height:0;border-top:3px solid #e5484d;cursor:ns-resize;z-index:4;line-height:normal}
            #balManualCanvas .bal-manual-cut:before{content:"";position:absolute;left:0;right:0;top:-10px;height:20px}
            #balManualCanvas .bal-manual-cut span{position:absolute;right:8px;top:-28px;padding:3px 7px;border-radius:6px;background:#e5484d;color:#fff;font-size:11px;font-weight:800}
            #balManualWrap .bal-manual-slice-label{position:absolute;left:8px;right:0;display:flex;align-items:flex-start;padding:2px 4px;box-sizing:border-box;border-top:1px solid rgba(120,90,100,.18);font-size:11px;color:#55494d;overflow:visible}
            #balManualWrap .bal-manual-slice-label.is-tinted{background:rgba(193,220,145,.20)}
            #balManualWrap .bal-manual-slice-label b{white-space:nowrap}
          </style>
          <div class="bal-actions" style="margin-top:14px"><button id="balExecuteManual" class="btn primary" onclick="BalanceamentoUI.executeManual()">Executar balanceamento</button></div>
        </div>
      </section>
      ${result ? `<section class="bal-section"><div class="bal-section-head"><span>Resultado</span></div><div class="bal-section-body">${result}</div></section>` : ""}
    </div>`;
  }

  function startCutDrag(event, index) {
    event.preventDefault();
    const canvas = document.querySelector("#balManualCanvas");
    const line = canvas?.querySelector(`[data-cut-index="${index}"]`);
    const current = (state?.chapters || []).find(x => String(x.chapter) === String(submittedChapter));
    const proposal = current?.proposal;
    if (!canvas || !line || !proposal?.region) return;
    const start = Number(proposal.region.global_start), end = Number(proposal.region.global_end), total = end-start;
    const move = ev => {
      const rect = canvas.getBoundingClientRect();
      const pct = Math.max(0.001, Math.min(0.999, (ev.clientY - rect.top) / rect.height));
      line.style.top = `${pct * 100}%`;
      window.__balManualCuts[index] = Math.round(start + pct * total);
    };
    const up = () => {
      document.removeEventListener("pointermove", move);
      window.__balManualCuts = [...window.__balManualCuts].sort((a,b) => a-b);
      renderBody();
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up, {once:true});
  }

  async function executeManual() {
    const current = (state?.chapters || []).find(x => String(x.chapter) === String(submittedChapter));
    if (!current?.proposal) return;
    const cuts = [...(window.__balManualCuts || [])].map(Number).sort((a,b)=>a-b);
    const button = document.querySelector("#balExecuteManual");
    if (button) { button.disabled = true; button.textContent = "Executando..."; }
    try {
      const created = await api("/api/action", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({action:"balance_execute",provider:data.provider,manga:data.manga,
          chapters:[submittedChapter],merges:[...submittedMerges],cuts})
      });
      const jobId = created?.job_id;
      if (!jobId) throw new Error("Job de balanceamento não foi criado.");
      while (true) {
        await new Promise(resolve => setTimeout(resolve, 500));
        const job = await api("/api/job/" + encodeURIComponent(jobId));
        if (job.status === "error") throw new Error(job.error || job.message || "Falha ao executar balanceamento.");
        if (job.status === "done") break;
      }
      await load();
      toast("Balanceamento gerado nos cortes definidos.");
    } catch (e) {
      toast(e.message || "Não foi possível executar o balanceamento.");
      if (button) { button.disabled = false; button.textContent = "Executar balanceamento"; }
    }
  }

  function persistedExecutionChapter() {
    const chapters = (state?.chapters || []).filter(ch => {
      const proposal = ch?.proposal;
      return proposal
        && proposal.proposal_id
        && proposal.region
        && proposal.source_preview
        && Array.isArray(proposal.source_slices)
        && proposal.source_slices.length > 0;
    });

    if (!chapters.length) return null;

    chapters.sort((a, b) => {
      const ta = Date.parse(a?.proposal?.generated_at || "") || 0;
      const tb = Date.parse(b?.proposal?.generated_at || "") || 0;
      if (ta !== tb) return tb - ta;
      return String(b?.proposal?.proposal_id || "").localeCompare(
        String(a?.proposal?.proposal_id || "")
      );
    });
    return chapters[0];
  }

  function renderExecutionBody(host) {
    let current = submittedChapter
      ? (state?.chapters || []).find(x => String(x.chapter) === String(submittedChapter))
      : null;

    if (!current?.proposal?.region || !current?.proposal?.source_preview) {
      current = persistedExecutionChapter();
    }

    if (!current) {
      host.innerHTML = `<div class="bal-empty">Nenhum capítulo submetido para balanceamento.</div>`;
      return;
    }

    submittedChapter = String(current.chapter);
    submittedMerges = [...(current.proposal?.selected_files || [])];
    host.innerHTML = manualEditorSection(current);
  }

  function renderBody() {
    const host = document.querySelector("#balanceBody");
    if (!host || !["balance","balance_execute"].includes(page)) return;
    if (!state) {
      host.innerHTML = `<div class="bal-empty">Carregando análise...</div>`;
      return;
    }
    if (page === "balance_execute") {
      renderExecutionBody(host);
      return;
    }
    const paging = pagedChapters();
    const current = (state.chapters || []).find(x => String(x.chapter) === String(selectedChapter));
    const rows = paging.rows.map(ch => `<tr class="${String(ch.chapter)===String(selectedChapter) ? "bal-table-active" : ""}" onclick="BalanceamentoUI.selectChapter('${escLocal(ch.chapter)}')">
      <td><b>${escLocal(ch.chapter)}</b></td>
      <td>${ch.merge_count}</td><td>${ch.issues_count}</td><td>${statusBadge(ch)}</td>
    </tr>`).join("");
    host.innerHTML = `
      <div class="toolbar standard-filterbar">
        <input class="search" placeholder="Buscar capítulo..." value="${escLocal(query)}" oninput="BalanceamentoUI.setQuery(this.value)">
        <div class="status-filter">
          <button class="tab ${filter==="all"?"active":""}" onclick="BalanceamentoUI.setFilter('all')">Todos <span>${state.summary.chapters}</span></button>
          <button class="tab ${filter==="balanced"?"active":""}" onclick="BalanceamentoUI.setFilter('balanced')">Balanceados <span>${state.summary.balanced}</span></button>
          <button class="tab ${filter==="unbalanced"?"active":""}" onclick="BalanceamentoUI.setFilter('unbalanced')">Desbalanceados <span>${state.summary.unbalanced}</span></button>
        </div>
        <button class="btn primary filter-primary-action" onclick="BalanceamentoUI.reload()">Analisar</button>
      </div>
      <div class="panel bal-table-panel">
        <table class="bal-main-table">
          <thead>
            <tr>
              <th>CAP.</th>
              <th>MERGES</th>
              <th>DIVERGÊNCIAS</th>
              <th class="bal-expand-th">
                <span>STATUS</span>
                <button class="bal-expand-btn" type="button" onclick="BalanceamentoUI.toggleSection('table')" aria-expanded="${openSections.table}" title="${openSections.table ? 'Recolher tabela' : 'Expandir tabela'}">${openSections.table ? "▼" : "▶"}</button>
              </th>
            </tr>
          </thead>
          ${openSections.table ? `<tbody>${rows || '<tr><td colspan="4" class="bal-empty">Nenhum capítulo encontrado.</td></tr>'}</tbody>` : ""}
        </table>
        ${openSections.table ? pager(paging.totalPages, paging.list.length) : ""}
      </div>

      ${detailForActiveView(current)}
    `;
    if (current && openSections.preview) renderPreviewOnly();
  }

  function renderValidation(root) {
    root.innerHTML = head(
      "Validar balanceamento",
      "Analise a distribuição dos merges concluídos e identifique capítulos balanceados ou desbalanceados."
    )+`<div id="balanceBody"></div>`;
    state = null;
    filter = "unbalanced";
    pageIndex = 1;
    renderBody();
    load();
  }

  function renderExecution(root) {
    root.innerHTML = head(
      "Executar balanceamento",
      "Execute o balanceamento somente nos capítulos já classificados como desbalanceados e inspecione a proposta SAFE gerada."
    )+`<div id="balanceBody"></div>`;
    state = null;
    renderBody();
    load();
  }

  function render(root) {
    return page === "balance_execute" ? renderExecution(root) : renderValidation(root);
  }

  window.BalanceamentoUI = {
    startCutDrag,
    executeManual,
    setManualCutCount(value){
      const current = (state?.chapters || []).find(x => String(x.chapter) === String(submittedChapter));
      const proposal = current?.proposal;
      if (!proposal?.region) return;
      const start = Number(proposal.region.global_start);
      const end = Number(proposal.region.global_end);
      const total = end - start;
      if (!(total > 0)) return;
      let count = Math.trunc(Number(value));
      if (!Number.isFinite(count)) count = Array.isArray(window.__balManualCuts) ? window.__balManualCuts.length : 1;
      count = Math.max(1, Math.min(20, count));
      window.__balManualCuts = Array.from({length: count}, (_, idx) =>
        Math.round(start + (total * (idx + 1) / (count + 1)))
      );
      window.__balManualProposalId = proposal.proposal_id;
      renderBody();
    },

    changeManualCutCount(delta){
      const current = Array.isArray(window.__balManualCuts) ? window.__balManualCuts.length : 1;
      BalanceamentoUI.setManualCutCount(current + (Number(delta) || 0));
    },

    changeManualZoom(delta){
      const current = Number(window.__balManualZoom || 50);
      const next = Math.max(20, Math.min(100, current + (Number(delta) || 0)));
      if (next === current) return;
      window.__balManualZoom = next;
      renderBody();
    },
    changeProposalZoom(delta){
      const next = Math.max(30, Math.min(200, proposalZoom + (Number(delta) || 0)));
      if (next === proposalZoom) return;
      proposalZoom = next;
      renderBody();
    },
    resetProposalZoom(){
      if (proposalZoom === 100) return;
      proposalZoom = 100;
      renderBody();
    },
    render,
    renderValidation,
    renderExecution,
    reload: load,
    selectChapter,
    toggleMerge,
    toggleSection,
    submitSelected,
    setView,
    changePage(delta){ pageIndex += Number(delta)||0; renderBody(); },
    setFilter(value){ filter=value; pageIndex=1; renderBody(); },
    setQuery(value){ query=value; pageIndex=1; renderBody(); }
  };
})();
