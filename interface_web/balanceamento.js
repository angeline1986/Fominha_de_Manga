(() => {
  "use strict";

  let state = null;
  let selectedChapter = null;
  let selectedMerges = new Set();
  let filter = "unbalanced";
  let pageIndex = 1;
  const pageSize = 10;
  let query = "";
  const openSections = {table: true, chapter: true, preview: true, proposal: true, manual: true, result: true};
  let activeView = "validate";
  let submittedChapter = null;
  let submittedMerges = [];
  let proposalZoom = 100;
  let selectedPreviewZoom = 100;
  let resultZoom = 100;

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
    return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=balance_proposal&chapter=${encodeURIComponent(chapter)}&proposal=${encodeURIComponent(proposalId || "")}&file=${encodeURIComponent(file)}`;
  }

  function editorImageUrl(chapter, file) {
    return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=balance_editor&chapter=${encodeURIComponent(chapter)}&file=${encodeURIComponent(file)}`;
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
    const stickyCount = document.querySelector("#balStickySelectedCount");
    if (stickyCount) stickyCount.textContent = `${chosen.length} merge(s) selecionado(s)`;
    host.innerHTML = chosen.length
      ? chosen.map(x => `<article class="bal-preview-card">
          <div class="bal-preview-stage" style="overflow:auto"><img src="${imageUrl(chapter.chapter,x.file)}" alt="${escLocal(x.file)}" style="width:${selectedPreviewZoom}%;max-width:none;height:auto;display:block;margin:0 auto"></div>
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

    return `<section class="bal-section bal-validate-sticky-section">
      <button class="bal-section-head" onclick="BalanceamentoUI.toggleSection('chapter')" aria-expanded="${openSections.chapter}">
        <span>Cap. ${escLocal(chapter.chapter)}</span>
        <span class="bal-section-head-right">${statusBadge(chapter)}<i class="bal-chevron">${openSections.chapter ? "▼" : "▶"}</i></span>
      </button>
      ${openSections.chapter ? `<div class="bal-section-body">${notice}
        <table class="bal-merge-table"><thead><tr><th></th><th>MERGE</th><th>ALTURA</th><th>DISTRIBUIÇÃO</th></tr></thead><tbody>${rows}</tbody></table>
        <div class="bal-sticky-submit">
          <span id="balStickySelectedCount" class="bal-sticky-submit-count">${selectedMerges.size} merge(s) selecionado(s)</span>
          <button id="balSubmitSelected" class="btn primary" ${selectedMerges.size >= 2 ? "" : "disabled"} onclick="BalanceamentoUI.submitSelected()" title="Gera uma proposta SAFE sem alterar o MERGE final">Submeter a Novos Cortes</button>
        </div>
      </div>` : ""}
    </section>`;
  }

  function previewSection() {
    const zoomControls = `<div class="bal-zoom-row">
      <span class="bal-zoom-control" aria-label="Controle de zoom">
        <button id="balSelectedZoomOut" type="button" class="bal-zoom-action" onclick="BalanceamentoUI.changeSelectedPreviewZoom(-10)" ${selectedPreviewZoom <= 30 ? "disabled" : ""} aria-label="Diminuir zoom">−</button>
        <b id="balSelectedZoomValue" class="bal-zoom-value">${selectedPreviewZoom}%</b>
        <button id="balSelectedZoomIn" type="button" class="bal-zoom-action" onclick="BalanceamentoUI.changeSelectedPreviewZoom(10)" ${selectedPreviewZoom >= 200 ? "disabled" : ""} aria-label="Aumentar zoom">+</button>
        <button id="balSelectedZoomReset" type="button" class="bal-zoom-reset" onclick="BalanceamentoUI.resetSelectedPreviewZoom()" ${selectedPreviewZoom === 100 ? "disabled" : ""}>100%</button>
      </span>
    </div>`;

    return `<section class="bal-section">
      <button class="bal-section-head" onclick="BalanceamentoUI.toggleSection('preview')" aria-expanded="${openSections.preview}">
        <span>Visualização dos merges selecionados</span>
        <span class="bal-section-head-right"><small id="balSelectedCount">${selectedMerges.size} selecionado(s)</small><i class="bal-chevron">${openSections.preview ? "▼" : "▶"}</i></span>
      </button>
      ${openSections.preview ? `<div class="bal-section-body">${zoomControls}<div id="balSelectedPreview" class="bal-preview-grid"></div></div>` : ""}
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

    activeView = "validate";
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
      activeView = "validate";
      await load();

      const current = (state?.chapters || []).find(x => String(x.chapter) === String(chapter));
      const proposal = current?.proposal;
      if (proposal?.status === "PROPOSTA_GERADA") {
        toast("Cortes atuais carregados para edição.");
      } else if (proposal) {
        {
          const message = proposal.message || "Nenhuma proposta SAFE encontrada.";
          if (message === "Ajuste os cortes livremente e execute para gerar a proposta.") {
            showBalancePopup(message, "Novos Cortes");
          } else {
            toast(message);
          }
        }
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
    const effected = proposal?.status === "EFETIVADO";
    return `<section class="bal-section">
      <div class="bal-section-head">
        <span>Composição final${chapter ? ` · Cap. ${escLocal(chapter.chapter)}` : ""}</span>
        <span class="bal-section-head-right"><small>${effected ? "Efetivado" : (ready ? "Proposta SAFE disponível" : "Aguardando proposta")}</small></span>
      </div>
      <div class="bal-section-body">
        <div class="${ready || effected ? "bal-okbox" : "bal-notice"}">
          <b>${effected ? "Composição final efetivada." : (ready ? "Proposta pronta para aprovação." : "Composição final indisponível.")}</b>
          ${effected ? " O MERGE oficial já contém esta proposta." : (ready ? " Esta etapa ainda não altera o MERGE final." : " Gere uma proposta em Novos Cortes.")}
        </div>
        <div class="bal-actions">
          <button class="btn" onclick="BalanceamentoUI.setView('rebalance')">Voltar</button>
          <button id="balApplyFinal" class="btn primary" onclick="BalanceamentoUI.applyFinal()" ${ready ? "" : "disabled"}>${effected ? "Composição aplicada" : "Aplicar composição final"}</button>
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
    return editorImageUrl(chapter.chapter, proposal.source_preview || "manual-source.png");
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
    const canApplyFinal = proposal.status === "PROPOSTA_GERADA";
    const result = canApplyFinal && Array.isArray(proposal.artifacts)
      ? `<div id="balResultPreview" class="bal-preview-grid">${proposal.artifacts.map((x, idx) =>
          `<article class="bal-preview-card"><div class="bal-preview-stage" style="overflow:auto"><img src="${proposalImageUrl(chapter.chapter,proposal.proposal_id,x.file)}" alt="Bloco ${idx+1}" style="width:${resultZoom}%;max-width:none;height:auto;display:block;margin:0 auto"></div>
           <div class="bal-preview-meta"><b>Bloco ${idx+1}</b><span>${Number(x.height||0).toLocaleString("pt-BR")} px</span></div></article>`).join("")}</div>`
      : "";
    const resultZoomControls = canApplyFinal && Array.isArray(proposal.artifacts) && proposal.artifacts.length
      ? `<span class="bal-zoom-control" aria-label="Controle de zoom do resultado">
          <button id="balResultZoomOut" type="button" class="bal-zoom-action" onclick="BalanceamentoUI.changeResultZoom(-10)" ${resultZoom <= 30 ? "disabled" : ""} aria-label="Diminuir zoom">−</button>
          <b id="balResultZoomValue" class="bal-zoom-value">${resultZoom}%</b>
          <button id="balResultZoomIn" type="button" class="bal-zoom-action" onclick="BalanceamentoUI.changeResultZoom(10)" ${resultZoom >= 200 ? "disabled" : ""} aria-label="Aumentar zoom">+</button>
          <button id="balResultZoomReset" type="button" class="bal-zoom-reset" onclick="BalanceamentoUI.resetResultZoom()" ${resultZoom === 100 ? "disabled" : ""}>100%</button>
        </span>`
      : "";
    return `<div class="bal-detail-stack">
      <section class="bal-section bal-manual-editor-section">
        <div class="bal-section-head bal-manual-sticky-toolbar">
          <span>Cap. ${escLocal(chapter.chapter)}</span>
          <span class="bal-section-head-right bal-manual-toolbar-controls">
            <span class="bal-zoom-control" aria-label="Controle de zoom do capítulo">
              <button type="button" class="bal-zoom-action" onclick="BalanceamentoUI.changeManualZoom(-10)" ${Number(window.__balManualZoom || 50) <= 20 ? "disabled" : ""} aria-label="Diminuir zoom">−</button>
              <b class="bal-zoom-value">${Number(window.__balManualZoom || 50)}%</b>
              <button type="button" class="bal-zoom-action" onclick="BalanceamentoUI.changeManualZoom(10)" ${Number(window.__balManualZoom || 50) >= 100 ? "disabled" : ""} aria-label="Aumentar zoom">+</button>
              <button type="button" class="bal-zoom-reset" onclick="BalanceamentoUI.resetManualZoom()" ${Number(window.__balManualZoom || 50) === 100 ? "disabled" : ""}>100%</button>
            </span>
            <span class="bal-manual-toolbar-divider" aria-hidden="true"></span>
            <small>Réguas de corte</small>
            <input id="balManualCutCount" type="number" min="1" max="20" step="1" value="${window.__balManualCuts.length}" onchange="BalanceamentoUI.setManualCutCount(this.value)" style="width:58px;text-align:center;padding:5px 6px">
            <button type="button" class="btn" style="min-width:32px;padding:4px 8px" onclick="BalanceamentoUI.changeManualCutCount(-1)">−</button>
            <button type="button" class="btn" style="min-width:32px;padding:4px 8px" onclick="BalanceamentoUI.changeManualCutCount(1)">+</button>
            <button id="balExecuteManual" class="btn primary" onclick="BalanceamentoUI.executeManual()">Novos Cortes</button>
            <button class="bal-expand-btn" type="button" data-bal-exec-toggle="manual" onclick="BalanceamentoUI.toggleExecutionSection('manual')" aria-expanded="${openSections.manual}" title="${openSections.manual ? 'Recolher capítulo' : 'Expandir capítulo'}">${openSections.manual ? "▼" : "▶"}</button>
          </span>
        </div>
        <div class="bal-section-body" data-bal-exec-body="manual" ${openSections.manual ? "" : "hidden"}>
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
        </div>
      </section>
      ${result ? `<section class="bal-section">
        <div class="bal-section-head" style="cursor:default">
          <span class="bal-result-title-wrap"><span>Resultado</span>${resultZoomControls}</span>
          <span class="bal-section-head-right">
            ${canApplyFinal ? `<button id="balApplyFinal" class="btn primary" onclick="BalanceamentoUI.applyFinal()">Aplicar composição final</button>` : ""}
            <button class="bal-expand-btn" type="button" data-bal-exec-toggle="result" onclick="BalanceamentoUI.toggleExecutionSection('result')" aria-expanded="${openSections.result}" title="${openSections.result ? 'Recolher resultado' : 'Expandir resultado'}">${openSections.result ? "▼" : "▶"}</button>
          </span>
        </div>
        <div class="bal-section-body" data-bal-exec-body="result" ${openSections.result ? "" : "hidden"}>${result}</div>
      </section>` : ""}
    </div>`;
  }


  function showBalancePopup(message, title="Balanceamento") {
    const existing = document.querySelector("#balFeedbackPopup");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "balFeedbackPopup";
    overlay.className = "bal-feedback-overlay";
    overlay.innerHTML = `
      <div class="bal-feedback-popup" role="dialog" aria-modal="true" aria-labelledby="balFeedbackTitle">
        <div class="bal-feedback-popup-head">
          <strong id="balFeedbackTitle">${escLocal(title)}</strong>
          <button type="button" class="bal-feedback-popup-close" aria-label="Fechar">×</button>
        </div>
        <div class="bal-feedback-popup-body">${escLocal(message)}</div>
        <div class="bal-feedback-popup-actions">
          <button type="button" class="btn primary">OK</button>
        </div>
      </div>
    `;

    const close = () => overlay.remove();
    overlay.addEventListener("click", (ev) => {
      if (ev.target === overlay) close();
    });
    overlay.querySelector(".bal-feedback-popup-close")?.addEventListener("click", close);
    overlay.querySelector(".bal-feedback-popup-actions .btn")?.addEventListener("click", close);

    document.body.appendChild(overlay);
    overlay.querySelector(".bal-feedback-popup-actions .btn")?.focus();
  }

  function updateSelectedPreviewZoomUi() {
    document.querySelectorAll("#balSelectedPreview .bal-preview-stage img").forEach(img => {
      img.style.width = `${selectedPreviewZoom}%`;
    });
    const value = document.querySelector("#balSelectedZoomValue");
    const zoomOut = document.querySelector("#balSelectedZoomOut");
    const zoomIn = document.querySelector("#balSelectedZoomIn");
    const reset = document.querySelector("#balSelectedZoomReset");
    if (value) value.textContent = `${selectedPreviewZoom}%`;
    if (zoomOut) zoomOut.disabled = selectedPreviewZoom <= 30;
    if (zoomIn) zoomIn.disabled = selectedPreviewZoom >= 200;
    if (reset) reset.disabled = selectedPreviewZoom === 100;
  }

  function updateResultZoomUi() {
    document.querySelectorAll("#balResultPreview .bal-preview-stage img").forEach(img => {
      img.style.width = `${resultZoom}%`;
    });
    const value = document.querySelector("#balResultZoomValue");
    const zoomOut = document.querySelector("#balResultZoomOut");
    const zoomIn = document.querySelector("#balResultZoomIn");
    const reset = document.querySelector("#balResultZoomReset");
    if (value) value.textContent = `${resultZoom}%`;
    if (zoomOut) zoomOut.disabled = resultZoom <= 30;
    if (zoomIn) zoomIn.disabled = resultZoom >= 200;
    if (reset) reset.disabled = resultZoom === 100;
  }

  function toggleExecutionSection(which) {
    if (!Object.prototype.hasOwnProperty.call(openSections, which)) return;
    openSections[which] = !openSections[which];
    const body = document.querySelector(`[data-bal-exec-body="${which}"]`);
    const button = document.querySelector(`[data-bal-exec-toggle="${which}"]`);
    if (body) body.hidden = !openSections[which];
    if (button) {
      button.textContent = openSections[which] ? "▼" : "▶";
      button.setAttribute("aria-expanded", String(openSections[which]));
      button.title = openSections[which]
        ? (which === "manual" ? "Recolher capítulo" : "Recolher resultado")
        : (which === "manual" ? "Expandir capítulo" : "Expandir resultado");
    }
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
      showBalancePopup("Balanceamento gerado nos cortes definidos.", "Proposta gerada");
    } catch (e) {
      toast(e.message || "Não foi possível executar o balanceamento.");
      if (button) { button.disabled = false; button.textContent = "Novos Cortes"; }
    }
  }

  async function applyFinal() {
    const current = (state?.chapters || []).find(x => String(x.chapter) === String(submittedChapter));
    if (!current?.proposal || current.proposal.status !== "PROPOSTA_GERADA") {
      toast("Não existe proposta gerada pendente de efetivação.");
      return;
    }
    const button = document.querySelector("#balApplyFinal");
    if (button) { button.disabled = true; button.textContent = "Aplicando..."; }
    try {
      const created = await api("/api/action", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({action:"balance_effect",provider:data.provider,manga:data.manga,chapters:[submittedChapter]})
      });
      const jobId = created?.job_id;
      if (!jobId) throw new Error("Job de efetivação não foi criado.");
      while (true) {
        await new Promise(resolve => setTimeout(resolve, 500));
        const job = await api("/api/job/" + encodeURIComponent(jobId));
        if (job.status === "error") throw new Error(job.error || job.message || "Falha ao efetivar balanceamento.");
        if (job.status === "done") break;
      }
      selectedMerges.clear();
      submittedMerges = [];
      await load();
      showBalancePopup("Composição final aplicada ao MERGE oficial.", "Composição aplicada");
    } catch (e) {
      toast(e.message || "Não foi possível aplicar a composição final.");
      if (button) { button.disabled = false; button.textContent = "Aplicar composição final"; }
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
      "Novos Cortes",
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
      const existingCuts = Array.isArray(window.__balManualCuts)
        ? window.__balManualCuts.map(Number).filter(Number.isFinite)
        : [];

      let nextCuts = [...existingCuts];

      if (count < nextCuts.length) {
        nextCuts = nextCuts.slice(0, count);
      } else {
        while (nextCuts.length < count) {
          const ordered = [...nextCuts].sort((a, b) => a - b);
          const boundaries = [start, ...ordered, end];

          let bestStart = boundaries[0];
          let bestEnd = boundaries[1];
          let bestSize = bestEnd - bestStart;

          for (let idx = 1; idx < boundaries.length - 1; idx += 1) {
            const gapStart = boundaries[idx];
            const gapEnd = boundaries[idx + 1];
            const gapSize = gapEnd - gapStart;
            if (gapSize > bestSize) {
              bestStart = gapStart;
              bestEnd = gapEnd;
              bestSize = gapSize;
            }
          }

          const newCut = Math.round(bestStart + ((bestEnd - bestStart) / 2));
          nextCuts.push(newCut);
        }
      }

      window.__balManualCuts = nextCuts.sort((a, b) => a - b);
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
    resetManualZoom(){
      const current = Number(window.__balManualZoom || 50);
      if (current === 100) return;
      window.__balManualZoom = 100;
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
    changeSelectedPreviewZoom(delta){
      const next = Math.max(30, Math.min(200, selectedPreviewZoom + (Number(delta) || 0)));
      if (next === selectedPreviewZoom) return;
      selectedPreviewZoom = next;
      updateSelectedPreviewZoomUi();
    },
    resetSelectedPreviewZoom(){
      if (selectedPreviewZoom === 100) return;
      selectedPreviewZoom = 100;
      updateSelectedPreviewZoomUi();
    },
    changeResultZoom(delta){
      const next = Math.max(30, Math.min(200, resultZoom + (Number(delta) || 0)));
      if (next === resultZoom) return;
      resultZoom = next;
      updateResultZoomUi();
    },
    resetResultZoom(){
      if (resultZoom === 100) return;
      resultZoom = 100;
      updateResultZoomUi();
    },
    render,
    renderValidation,
    renderExecution,
    reload: load,
    selectChapter,
    toggleMerge,
    toggleSection,
    toggleExecutionSection,
    submitSelected,
    applyFinal,
    setView,
    changePage(delta){ pageIndex += Number(delta)||0; renderBody(); },
    setFilter(value){ filter=value; pageIndex=1; renderBody(); },
    setQuery(value){ query=value; pageIndex=1; renderBody(); }
  };
})();
