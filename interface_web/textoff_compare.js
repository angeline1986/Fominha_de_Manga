(() => {
  let state=null,sourceFilter="all",query="",pageIndex=1,selectedKey=null,selectedPage=-1,chapterOpen=false,compareOpen=false,zoom=100,flagging=false,level3State=null,level3SelectedKey=null,level3Loading=false,level3Zoom=100,level3Analysis=null,level3Analyzing=false,level3Syncing=false,level3Selecting=false,level3Selections=[],level3Selection=null,level3Drag=null,level3Preview=null,level3Previewing=false,level3Approving=false,resultsOpen=true;
  const PAGE_SIZE=15;
  const escLocal=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
  const currentRow=()=>state?.rows?.find(x=>String(x.key)===String(selectedKey))||null;

  function formatDate(value){
    if(!value)return "—";
    const d=new Date(value);
    return Number.isNaN(d.getTime())?String(value):d.toLocaleString("pt-BR",{dateStyle:"short",timeStyle:"short"});
  }
  function mediaUrl(kind,row,file){
    return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=${encodeURIComponent(kind)}&source=${encodeURIComponent(row.source_stage)}&chapter=${encodeURIComponent(row.chapter)}&file=${encodeURIComponent(file)}`;
  }
  /* === TEXT OFF · HUB QC ⇄ QC STUDIO · 3.2.1 === */
  /* === TEXT OFF · HUB QC ⇄ QC STUDIO · 3.2.2 VISUAL === */
  let qcStatusFilter="all",studioMode="single",sliderPos=50,pageQuery="",studioKeyBound=false,thumbTimer=null;

  function baseFilteredRows(){
    let rows=Array.isArray(state?.rows)?state.rows:[];
    if(sourceFilter!=="all")rows=rows.filter(x=>String(x.source_stage).toLowerCase()===sourceFilter);
    const q=String(query||"").trim().toLowerCase();
    if(q)rows=rows.filter(x=>String(x.chapter).toLowerCase().includes(q));
    return rows;
  }
  const rowHasLevel3Pending=row=>(Array.isArray(row?.items)?row.items:[]).some(it=>it?.level3_status==="PENDENTE_NIVEL3");
  function filteredRows(){
    const rows=baseFilteredRows();
    if(qcStatusFilter==="pending")return rows.filter(rowHasLevel3Pending);
    if(qcStatusFilter==="waiting")return rows.filter(x=>!rowHasLevel3Pending(x));
    return rows;
  }
  function qcStatus(row){
    const pending=(Array.isArray(row?.items)?row.items:[]).filter(it=>it?.level3_status==="PENDENTE_NIVEL3").length;
    return pending?{kind:"pending",label:`🚩 ${pending} pendência${pending===1?"":"s"}`}:{kind:"waiting",label:"⏳ Aguardando"};
  }
  function sourceLabel(row){return escLocal(row?.source||row?.source_stage||"—")}
  function chapterLabel(row){return `Cap. ${escLocal(row?.chapter||"—")}`}

  function hubSection(){
    const base=baseFilteredRows();
    const pendingCount=base.filter(rowHasLevel3Pending).length;
    const waitingCount=base.length-pendingCount;
    const all=filteredRows();
    const pages=Math.max(1,Math.ceil(all.length/PAGE_SIZE));
    pageIndex=Math.min(Math.max(1,pageIndex),pages);
    const visible=all.slice((pageIndex-1)*PAGE_SIZE,pageIndex*PAGE_SIZE);
    const next=base.find(rowHasLevel3Pending)||base[0]||null;
    const rows=visible.map(x=>{const status=qcStatus(x);const key=encodeURIComponent(String(x.key));return `<tr class="toc-qc-row" onclick="TextOffCompareUI.selectChapter(decodeURIComponent('${key}'))"><td><strong>${chapterLabel(x)}</strong></td><td>${sourceLabel(x)}</td><td>${Number(x.pages||x.items?.length||0)}</td><td>${escLocal(formatDate(x.processed_at))}</td><td><span class="toc-qc-status is-${status.kind}">${status.label}</span></td><td class="toc-qc-action"><button class="btn" type="button" onclick="event.stopPropagation();TextOffCompareUI.selectChapter(decodeURIComponent('${key}'))">Revisar →</button></td></tr>`}).join("");
    const hero=next?`<div class="toc-qc-hero"><div><span>PRÓXIMO NA FILA</span><strong>${chapterLabel(next)} · ${sourceLabel(next)} · ${Number(next.pages||next.items?.length||0)} página(s)</strong></div><button class="btn primary" type="button" onclick="TextOffCompareUI.selectChapter(decodeURIComponent('${encodeURIComponent(String(next.key))}'))">▶ Iniciar Revisão</button></div>`:`<div class="toc-qc-hero is-empty"><strong>Nenhum capítulo disponível para revisão.</strong></div>`;
    const pager=pages>1?`<div class="table-pager toc-table-pager"><button class="btn" ${pageIndex<=1?"disabled":""} onclick="TextOffCompareUI.changePage(-1)">◀</button><span>${pageIndex} / ${pages}</span><button class="btn" ${pageIndex>=pages?"disabled":""} onclick="TextOffCompareUI.changePage(1)">▶</button></div>`:"";
    return `<section class="toc-qc-hub"><div class="toc-qc-title"><h1>Comparar resultados</h1><span class="toc-qc-manga">📖 ${escLocal(data?.manga||"")}</span></div>${hero}<div class="toc-qc-filterbar"><input class="search" placeholder="Buscar capítulo..." value="${escLocal(query)}" oninput="TextOffCompareUI.setQuery(this.value)"><div class="toc-qc-filtergroup"><span>Fonte:</span><button class="tab ${sourceFilter==="all"?"active":""}" onclick="TextOffCompareUI.setSource('all')">Todas</button><button class="tab ${sourceFilter==="original"?"active":""}" onclick="TextOffCompareUI.setSource('original')">Original</button><button class="tab ${sourceFilter==="merged"?"active":""}" onclick="TextOffCompareUI.setSource('merged')">Merged</button></div><div class="toc-qc-filtergroup"><span>Status:</span><button class="tab ${qcStatusFilter==="all"?"active":""}" onclick="TextOffCompareUI.setQcStatus('all')">Todos</button><button class="tab ${qcStatusFilter==="pending"?"active":""}" onclick="TextOffCompareUI.setQcStatus('pending')">🚩 Com pendências (${pendingCount})</button><button class="tab ${qcStatusFilter==="waiting"?"active":""}" onclick="TextOffCompareUI.setQcStatus('waiting')">⏳ Aguardando (${waitingCount})</button></div></div><div class="panel toc-qc-table-panel"><table class="toc-table toc-qc-table"><thead><tr><th>CAP.</th><th>FONTE</th><th>PÁGINAS</th><th>PROCESSADO EM</th><th>STATUS QC</th><th>AÇÃO</th></tr></thead><tbody>${rows||'<tr><td colspan="6" class="toc-empty">Nenhum resultado encontrado para os filtros atuais.</td></tr>'}</tbody></table>${pager}</div></section>`;
  }

  function studioZoomControls(){return `<span class="bal-zoom-control toc-qc-zoom"><button type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeZoom(-10)" ${zoom<=30?"disabled":""}>−</button><b id="tocCompareZoomValue" class="bal-zoom-value">${zoom}%</b><button type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeZoom(10)" ${zoom>=200?"disabled":""}>+</button><button type="button" class="bal-zoom-reset" onclick="TextOffCompareUI.resetZoom()" ${zoom===100?"disabled":""}>↺</button></span>`}
  function studioSection(){
    const row=currentRow(); if(!row)return hubSection();
    const items=Array.isArray(row.items)?row.items:[];
    if(!items.length)return `<section class="toc-qc-studio"><button class="btn" onclick="TextOffCompareUI.backToHub()">← Capítulos</button><div class="toc-empty">Este capítulo não possui páginas para comparar.</div></section>`;
    selectedPage=Math.max(0,Math.min(selectedPage<0?0:selectedPage,items.length-1));
    const item=items[selectedPage]; const flagged=item?.level3_status==="PENDENTE_NIVEL3";
    const pageButtons=items.map((x,i)=>`<button type="button" class="toc-qc-page ${i===selectedPage?"active":""}" data-page-name="${escLocal(String(x.source_file).toLowerCase())}" onclick="TextOffCompareUI.selectImage(${i})" onmouseenter="TextOffCompareUI.showThumb(event,${i})" onmouseleave="TextOffCompareUI.hideThumb()"><span>${escLocal(x.source_file)}</span><b>${i+1}</b></button>`).join("");
    const original=mediaUrl("textoff_source",row,item.source_file), clean=mediaUrl("textoff_clean",row,item.clean_file);
    const canvas=studioMode==="side"?`<div class="toc-qc-side"><figure><figcaption>ORIGINAL</figcaption><div class="toc-qc-image-scroll"><div class="toc-qc-image-shell is-loading"><span class="toc-qc-image-state">Carregando imagem…</span><img class="toc-qc-scale-img" src="${original}" alt="Original · ${escLocal(item.source_file)}"></div></div></figure><figure><figcaption>TEXTO OFF</figcaption><div class="toc-qc-image-scroll"><div class="toc-qc-image-shell is-loading"><span class="toc-qc-image-state">Carregando imagem…</span><img class="toc-qc-scale-img" src="${clean}" alt="Texto Off · ${escLocal(item.clean_file)}"></div></div></figure></div>`:`<div id="tocQcSlider" class="toc-qc-slider" style="--toc-slider:${sliderPos}%"><div class="toc-qc-slider-stage"><div class="toc-qc-image-shell is-loading"><span class="toc-qc-image-state">Carregando imagem…</span><img id="tocQcClean" class="toc-qc-scale-img" src="${clean}" alt="Texto Off · ${escLocal(item.clean_file)}"></div><div class="toc-qc-slider-overlay"><div class="toc-qc-image-shell is-loading"><span class="toc-qc-image-state">Carregando imagem…</span><img id="tocQcOriginal" class="toc-qc-scale-img" src="${original}" alt="Original · ${escLocal(item.source_file)}"></div></div><div class="toc-qc-slider-divider"><span>⇄</span></div></div></div>`;
    return `<section class="toc-qc-studio"><header class="toc-qc-studio-toolbar"><div class="toc-qc-zone toc-qc-zone-left"><button class="btn" type="button" onclick="TextOffCompareUI.backToHub()">← Capítulos</button><div class="toc-qc-breadcrumb">${escLocal(data?.manga||"")} › ${chapterLabel(row)} › ${escLocal(item.source_file)}</div></div><div class="toc-qc-zone toc-qc-zone-center"><div class="toc-qc-mode"><button class="tab ${studioMode==="single"?"active":""}" onclick="TextOffCompareUI.setStudioMode('single')">◐ Visão única</button><button class="tab ${studioMode==="side"?"active":""}" onclick="TextOffCompareUI.setStudioMode('side')">◫ Lado a lado</button></div>${studioZoomControls()}</div><div class="toc-qc-zone toc-qc-zone-right"><button class="btn toc-correction-btn ${flagged?"is-flagged":""}" type="button" onclick="TextOffCompareUI.flagCorrection()" ${flagged||flagging?"disabled":""}>${flagged?"✓ Correção sinalizada":(flagging?"Sinalizando…":"🚩 Sinalizar correção")}</button></div></header><div class="toc-qc-workspace"><aside id="tocQcSidebar" class="toc-qc-sidebar"><div class="toc-qc-sidebar-head"><strong>${chapterLabel(row)}</strong><span>${items.length} páginas</span></div><input class="search" placeholder="Buscar página..." value="${escLocal(pageQuery)}" oninput="TextOffCompareUI.filterStudioPages(this.value)"><div class="toc-qc-pages">${pageButtons}</div></aside><main class="toc-qc-canvas">${canvas}</main></div><footer class="toc-qc-pager"><button class="btn" onclick="TextOffCompareUI.moveImage(-1)" ${selectedPage<=0?"disabled":""}>◀ Anterior</button><strong>${selectedPage+1} / ${items.length}</strong><button class="btn" onclick="TextOffCompareUI.moveImage(1)" ${selectedPage>=items.length-1?"disabled":""}>Próxima ▶</button></footer><div id="compareThumbPopover" class="toc-qc-thumb" hidden><strong id="compareThumbTitle"></strong><span class="toc-qc-thumb-count"></span><div class="toc-qc-thumb-state">Carregando prévia…</div><img alt="Prévia da página" hidden></div></section>`;
  }

  function renderBody(){const host=document.querySelector("#textOffCompareBody");if(!host)return;hideThumb();host.innerHTML=currentRow()?studioSection():hubSection();if(currentRow())bindStudioEvents();}
  async function load(){try{state=await api(`/api/textoff-compare?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&_=${Date.now()}`);renderBody()}catch(e){toast(e.message||"Não foi possível carregar os resultados do Texto Off.")}}
  function render(root){root.innerHTML=`<div id="textOffCompareBody"><div class="muted">Carregando resultados do Texto Off…</div></div>`;state=null;sourceFilter="all";qcStatusFilter="all";query="";pageQuery="";pageIndex=1;selectedKey=null;selectedPage=-1;zoom=100;studioMode="single";sliderPos=50;load()}
  function selectChapter(key){const row=state?.rows?.find(x=>String(x.key)===String(key))||null;const items=Array.isArray(row?.items)?row.items:[];if(!row){toast("Capítulo não encontrado para revisão.");return}if(!items.length){toast("Este capítulo não possui páginas para comparar.");return}hideThumb();selectedKey=String(key);selectedPage=0;pageQuery="";zoom=100;studioMode="single";sliderPos=50;renderBody()}
  function backToHub(){hideThumb();selectedKey=null;selectedPage=-1;pageQuery="";zoom=100;studioMode="single";sliderPos=50;renderBody()}
  function selectImage(index){const items=Array.isArray(currentRow()?.items)?currentRow().items:[];if(!items.length)return;hideThumb();selectedPage=Math.max(0,Math.min(Number(index)||0,items.length-1));sliderPos=50;renderBody()}
  function moveImage(delta){const items=Array.isArray(currentRow()?.items)?currentRow().items:[];if(!items.length)return;hideThumb();selectedPage=Math.max(0,Math.min(items.length-1,selectedPage+Number(delta||0)));sliderPos=50;renderBody()}
  function updateCompareZoomUi(){document.querySelectorAll(".toc-qc-scale-img").forEach(img=>applyStudioImageScale(img));const value=document.querySelector("#tocCompareZoomValue");if(value)value.textContent=`${zoom}%`;}
  function changeZoom(delta){zoom=Math.max(30,Math.min(200,zoom+Number(delta||0)));updateCompareZoomUi()}
  function resetZoom(){zoom=100;updateCompareZoomUi()}
  function setQuery(value){query=String(value||"");pageIndex=1;renderBody()}
  function setSource(value){sourceFilter=String(value||"all");pageIndex=1;renderBody()}
  function setQcStatus(value){qcStatusFilter=String(value||"all");pageIndex=1;renderBody()}
  function changePage(delta){pageIndex=Math.max(1,pageIndex+Number(delta||0));renderBody()}
  function setStudioMode(value){hideThumb();studioMode=value==="side"?"side":"single";renderBody()}
  function filterStudioPages(value){pageQuery=String(value||"").trim().toLowerCase();document.querySelectorAll(".toc-qc-page").forEach(btn=>{btn.hidden=pageQuery&&!String(btn.dataset.pageName||"").includes(pageQuery)})}
  function setImageState(img,stateName){if(!img)return;const shell=img.closest(".toc-qc-image-shell")||img.parentElement;shell?.classList.remove("is-loading","is-ready","is-error");shell?.classList.add(`is-${stateName}`);const msg=shell?.querySelector(".toc-qc-image-state");if(msg)msg.textContent=stateName==="error"?"Não foi possível carregar esta imagem.":stateName==="loading"?"Carregando imagem…":"";}
  function applyStudioImageScale(img){if(!img)return;const apply=()=>{if(img.naturalWidth){img.style.width=`${Math.round(img.naturalWidth*zoom/100)}px`;img.style.maxWidth="none";img.style.height="auto";}setImageState(img,"ready")};const fail=()=>setImageState(img,"error");setImageState(img,"loading");img.addEventListener("load",apply,{once:true});img.addEventListener("error",fail,{once:true});if(img.complete){if(img.naturalWidth)apply();else fail();}}
  function setSliderFromPointer(ev){const slider=document.querySelector("#tocQcSlider");if(!slider)return;const r=slider.getBoundingClientRect();sliderPos=Math.max(0,Math.min(100,(ev.clientX-r.left)/Math.max(1,r.width)*100));slider.style.setProperty("--toc-slider",`${sliderPos}%`)}
  function bindStudioEvents(){
    document.querySelectorAll(".toc-qc-scale-img").forEach(applyStudioImageScale);filterStudioPages(pageQuery);
    const slider=document.querySelector("#tocQcSlider");if(slider){let dragging=false;slider.addEventListener("pointerdown",e=>{dragging=true;slider.setPointerCapture?.(e.pointerId);setSliderFromPointer(e)});slider.addEventListener("pointermove",e=>{if(dragging)setSliderFromPointer(e)});slider.addEventListener("pointerup",()=>dragging=false);slider.addEventListener("pointercancel",()=>dragging=false)}
    if(!studioKeyBound){studioKeyBound=true;document.addEventListener("keydown",e=>{if(!currentRow()||e.metaKey||e.ctrlKey||e.altKey)return;const tag=document.activeElement?.tagName;if(tag==="INPUT"||tag==="TEXTAREA")return;if(e.key==="ArrowLeft"){e.preventDefault();hideThumb();moveImage(-1)}else if(e.key==="ArrowRight"){e.preventDefault();hideThumb();moveImage(1)}})}
  }
  function showThumb(ev,index){clearTimeout(thumbTimer);const btn=ev.currentTarget;thumbTimer=setTimeout(()=>{const row=currentRow(),items=Array.isArray(row?.items)?row.items:[],item=items[index],pop=document.querySelector("#compareThumbPopover"),sidebar=document.querySelector("#tocQcSidebar");if(!row||!item||!pop||!sidebar||!btn?.isConnected)return;const br=btn.getBoundingClientRect(),sr=sidebar.getBoundingClientRect();pop.querySelector("strong").textContent=item.source_file;pop.querySelector(".toc-qc-thumb-count").textContent=`${index+1}/${items.length}`;const img=pop.querySelector("img"),stateEl=pop.querySelector(".toc-qc-thumb-state");img.removeAttribute("src");img.hidden=true;stateEl.textContent="Carregando prévia…";pop.style.left=`${sr.right+12}px`;pop.style.top=`${Math.max(12,Math.min(br.top-20,window.innerHeight-460))}px`;pop.hidden=false;img.onload=()=>{stateEl.textContent="";img.hidden=false};img.onerror=()=>{img.hidden=true;stateEl.textContent="Prévia indisponível."};img.src=mediaUrl("textoff_source",row,item.source_file);},100);}
  function hideThumb(){clearTimeout(thumbTimer);thumbTimer=null;const pop=document.querySelector("#compareThumbPopover");if(pop){pop.hidden=true;const img=pop.querySelector("img");if(img){img.onload=null;img.onerror=null;img.removeAttribute("src")}}}
  /* === /TEXT OFF · HUB QC ⇄ QC STUDIO · 3.2.1 === */

  const level3Current=()=>level3State?.rows?.find(x=>String(x.key)===String(level3SelectedKey))||null;
  function level3MediaUrl(kind,row,file){return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=${encodeURIComponent(kind)}&source=${encodeURIComponent(row.source_stage)}&chapter=${encodeURIComponent(row.chapter)}&file=${encodeURIComponent(file)}`;}
  function level3ProposalMediaUrl(row,preview){return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=textoff_level3_preview&chapter=${encodeURIComponent(row.chapter)}&proposal=${encodeURIComponent(preview.proposal_id)}&file=${encodeURIComponent(preview.preview_file)}&_=${Date.now()}`;}
  async function loadLevel3(){
    level3Loading=true;renderLevel3Body();
    try{
      level3State=await api(`/api/textoff-level3?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&_=${Date.now()}`);
      const rows=Array.isArray(level3State?.rows)?level3State.rows:[];
      if(!rows.some(x=>String(x.key)===String(level3SelectedKey)))level3SelectedKey=rows[0]?.key||null;
    }catch(e){level3State={rows:[],pending:0};level3SelectedKey=null;toast(e.message||"Não foi possível carregar o Nível III.")}
    finally{level3Loading=false;renderLevel3Body()}
  }
  function level3Table(rows){
    const body=rows.map(x=>`<tr class="${String(x.key)===String(level3SelectedKey)?"toc-row-active":""}" onclick="TextOffCompareUI.selectLevel3(decodeURIComponent('${encodeURIComponent(x.key)}'))"><td>${escLocal(x.chapter)}</td><td>${escLocal(x.source_file)}</td><td>${escLocal(x.source)}</td><td><span class="toc-status toc-status-pending">Pendente</span></td></tr>`).join("");
    return `<div class="panel toc-table-panel toc-level3-table-panel"><table class="toc-table"><thead><tr><th>CAP.</th><th>IMAGEM</th><th>FONTE</th><th>STATUS</th></tr></thead><tbody>${body||'<tr><td colspan="4" class="toc-empty">Nenhuma correção sinalizada.</td></tr>'}</tbody></table></div>`;
  }
  function level3Detail(row){
    if(!row)return `<div class="panel toc-level3-empty"><strong>Nenhuma pendência selecionada.</strong><span>As imagens sinalizadas na comparação aparecerão aqui.</span></div>`;
    const note=level3Analysis?(level3Analysis.count?`${level3Analysis.count} região(ões) suspeita(s) destacada(s).`:"Nenhum resíduo seguro identificado automaticamente."):"";
    const manualNote=level3Preview?"Prévia gerada. A imagem oficial permanece inalterada.":(level3Selections.length?`${level3Selections.length} área(s) manual(is) selecionada(s).`:(level3Selecting?"Arraste sobre cada resíduo que deseja corrigir.":""));
    const actionHint=level3Preview?"Confira o resultado antes de aplicar. Em imagens de Merge, a aprovação também atualiza o arquivo correspondente em 02_MERGE.":"Análise automática ou seleção manual da área residual.";
    const actionButtons=level3Preview
      ? `<div class="toc-level3-action-buttons"><button class="btn" type="button" ${level3Approving?"disabled":""} onclick="TextOffCompareUI.resetLevel3Preview()">Refazer seleção</button><button class="btn primary" type="button" ${level3Approving?"disabled":""} onclick="TextOffCompareUI.approveLevel3Preview()">${level3Approving?"Aprovando…":"Aprovar correção"}</button></div>`
      : `<div class="toc-level3-action-buttons"><button class="btn primary" type="button" ${level3Analyzing||level3Previewing?"disabled":""} onclick="TextOffCompareUI.analyzeLevel3()">${level3Analyzing?"Analisando…":"Analisar resíduos"}</button><button id="tocLevel3SelectArea" class="btn" type="button" onclick="TextOffCompareUI.toggleLevel3Selection()">${level3Selecting?"Cancelar seleção":"Selecionar área"}</button><button id="tocLevel3GeneratePreview" class="btn" type="button" ${!level3Selections.length||level3Previewing?"disabled":""} onclick="TextOffCompareUI.generateLevel3Preview()">${level3Previewing?"Gerando prévia…":"Gerar prévia"}</button></div>`;
    const leftTitle=level3Preview?"RESULTADO ATUAL":"ORIGINAL";
    const leftMeta=level3Preview?"Antes":(row.source_stage==="MERGE"?"Fonte: MERGE":"Fonte: IMG");
    const leftUrl=level3Preview?level3MediaUrl("textoff_clean",row,row.clean_file):level3MediaUrl("textoff_source",row,row.source_file);
    const rightTitle=level3Preview?"PREVIEW NÍVEL III":"RESULTADO ATUAL";
    const rightMeta=level3Preview?"Depois · temporário":"Texto Off";
    const rightUrl=level3Preview?level3ProposalMediaUrl(row,level3Preview):level3MediaUrl("textoff_clean",row,row.clean_file);
    const rightOverlays=level3Preview?"":`${level3Boxes()}${level3SelectionBox()}<span id="tocLevel3ManualLayer" class="toc-level3-manual-layer ${level3Selecting?"is-active":""}"><span class="toc-level3-manual-live"></span></span>`;
    return `<section class="panel toc-level3-detail"><div class="toc-level3-detail-head"><div><span class="caption">PENDÊNCIA SELECIONADA</span><h2>Cap. ${escLocal(row.chapter)} · ${escLocal(row.source_file)}</h2></div><div class="toc-level3-head-actions"><span class="bal-zoom-control" aria-label="Controle de zoom sincronizado"><button id="tocLevel3ZoomOut" type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeLevel3Zoom(-10)" ${level3Zoom<=30?"disabled":""}>−</button><b id="tocLevel3ZoomValue" class="bal-zoom-value">${level3Zoom}%</b><button id="tocLevel3ZoomIn" type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeLevel3Zoom(10)" ${level3Zoom>=200?"disabled":""}>+</button><button id="tocLevel3ZoomReset" type="button" class="bal-zoom-reset" onclick="TextOffCompareUI.setLevel3Zoom(100)" ${level3Zoom===100?"disabled":""}>100%</button></span><span class="toc-status toc-status-pending">Pendente</span></div></div><div class="toc-compare-grid toc-level3-grid"><article class="toc-preview-card"><div class="toc-preview-head"><strong>${leftTitle}</strong><span>${leftMeta}</span></div><div class="toc-preview-stage toc-level3-scroll"><div class="toc-level3-image-wrap" style="width:${level3Zoom}%"><img src="${leftUrl}" alt="${leftTitle}"></div></div></article><article class="toc-preview-card"><div class="toc-preview-head"><strong>${rightTitle}</strong><span>${rightMeta}</span></div><div class="toc-preview-stage toc-level3-scroll"><div class="toc-level3-image-wrap" style="width:${level3Zoom}%"><img src="${rightUrl}" alt="${rightTitle}">${rightOverlays}</div></div></article></div><div class="toc-level3-actions"><div><strong>Próxima etapa</strong><span>${actionHint}</span>${note?`<span class="toc-level3-analysis-note">${note}</span>`:""}<span id="tocLevel3ManualNote" class="toc-level3-analysis-note" ${manualNote?"":"hidden"}>${manualNote}</span></div>${actionButtons}</div></section>`;
  }
  function renderLevel3Body(){
    const host=document.querySelector("#textoffLevel3Body");if(!host)return;
    if(level3Loading){host.innerHTML='<div class="muted">Carregando correções sinalizadas…</div>';return}
    const rows=Array.isArray(level3State?.rows)?level3State.rows:[];
    host.innerHTML=`${level3Table(rows)}${level3Detail(level3Current())}`;
    requestAnimationFrame(()=>{bindLevel3Scroll();bindLevel3ManualSelection()});
  }
  function renderCorrection(root){
    root.innerHTML=`<div class="head"><div><div class="caption">TEXTO OFF · NÍVEL III</div><div class="page-title-wrap" tabindex="0"><h1>Correção assistida</h1><span class="page-title-tooltip" role="tooltip">Revise as páginas sinalizadas antes de qualquer correção.</span></div></div></div><div id="textoffLevel3Body"></div>`;
    level3State=null;level3SelectedKey=null;loadLevel3();
  }
  function selectLevel3(key){level3SelectedKey=key;level3Analysis=null;level3Selecting=false;level3Selections=[];level3Selection=null;level3Drag=null;level3Preview=null;level3Previewing=false;level3Approving=false;renderLevel3Body()}
  function level3SelectionBox(){
    return level3Selections.map((b,index)=>`<span class="toc-level3-manual-box" style="left:${b.left}%;top:${b.top}%;width:${b.width}%;height:${b.height}%"><i>Manual ${index+1}</i></span>`).join("");
  }

  function syncLevel3SelectionUi(){
    const layer=document.querySelector("#tocLevel3ManualLayer");
    if(!layer)return;
    layer.classList.toggle("is-active",level3Selecting);
    const wrap=layer.closest(".toc-level3-image-wrap");
    wrap?.querySelectorAll(".toc-level3-manual-box").forEach(box=>box.remove());
    const live=layer.querySelector(".toc-level3-manual-live");
    if(live)live.style.display="none";
    if(wrap){
      level3Selections.forEach((b,index)=>{
        const box=document.createElement("span");
        box.className="toc-level3-manual-box";
        box.style.left=`${b.left}%`;
        box.style.top=`${b.top}%`;
        box.style.width=`${b.width}%`;
        box.style.height=`${b.height}%`;
        box.innerHTML=`<i>Manual ${index+1}</i>`;
        wrap.insertBefore(box,layer);
      });
    }
    const selectBtn=document.querySelector("#tocLevel3SelectArea");
    const previewBtn=document.querySelector("#tocLevel3GeneratePreview");
    const note=document.querySelector("#tocLevel3ManualNote");
    if(selectBtn)selectBtn.textContent=level3Selecting?"Finalizar seleção":"Selecionar áreas";
    if(previewBtn)previewBtn.disabled=!level3Selections.length||level3Previewing;
    if(note){
      const message=level3Selections.length
        ? `${level3Selections.length} área(s) manual(is) selecionada(s).`
        : (level3Selecting?"Arraste sobre cada resíduo que deseja corrigir.":"");
      note.textContent=message;
      note.hidden=!message;
    }
  }

  function toggleLevel3Selection(){
    level3Selecting=!level3Selecting;
    level3Selection=null;
    level3Drag=null;
    level3Preview=null;
    console.log("[NIVEL3][MANUAL] modo seleção",level3Selecting?"ativo":"inativo");
    syncLevel3SelectionUi();
  }
  function bindLevel3ManualSelection(){
    const layer=document.querySelector("#tocLevel3ManualLayer");
    if(!layer||layer.dataset.manualBound==="1")return;
    layer.dataset.manualBound="1";
    const pos=e=>{
      const r=layer.getBoundingClientRect();
      return {
        x:Math.max(0,Math.min(r.width,e.clientX-r.left)),
        y:Math.max(0,Math.min(r.height,e.clientY-r.top)),
        w:r.width,h:r.height
      };
    };
    layer.addEventListener("pointerdown",e=>{
      if(!level3Selecting||e.button!==0)return;
      const p=pos(e);
      level3Drag={x:p.x,y:p.y,w:p.w,h:p.h};
      level3Selection=null;
      layer.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    layer.addEventListener("pointermove",e=>{
      if(!level3Drag)return;
      const p=pos(e);
      const x=Math.min(level3Drag.x,p.x),y=Math.min(level3Drag.y,p.y);
      const w=Math.abs(p.x-level3Drag.x),h=Math.abs(p.y-level3Drag.y);
      level3Selection={
        left:x/p.w*100,top:y/p.h*100,
        width:w/p.w*100,height:h/p.h*100
      };
      const box=layer.querySelector(".toc-level3-manual-live");
      if(box){
        box.style.display="block";
        box.style.left=`${level3Selection.left}%`;
        box.style.top=`${level3Selection.top}%`;
        box.style.width=`${level3Selection.width}%`;
        box.style.height=`${level3Selection.height}%`;
      }
    });
    const finish=e=>{
      if(!level3Drag)return;
      if(layer.hasPointerCapture?.(e.pointerId))layer.releasePointerCapture(e.pointerId);
      level3Drag=null;
      if(level3Selection&&(level3Selection.width<0.3||level3Selection.height<0.3))level3Selection=null;
      if(level3Selection){
        level3Selections.push({...level3Selection});
        console.log("[NIVEL3][MANUAL] seleção adicionada",level3Selection,"total",level3Selections.length);
      }
      level3Selection=null;
      syncLevel3SelectionUi();
    };
    layer.addEventListener("pointerup",finish);
    layer.addEventListener("pointercancel",finish);
  }
  function level3Boxes(){
    const a=level3Analysis;
    if(!a||!Array.isArray(a.candidates)||!a.image_width||!a.image_height)return "";
    return a.candidates.map(c=>{
      const [x,y,w,h]=c.bbox;
      return `<span class="toc-level3-box" style="left:${x/a.image_width*100}%;top:${y/a.image_height*100}%;width:${w/a.image_width*100}%;height:${h/a.image_height*100}%"><i>${c.id}</i></span>`;
    }).join("");
  }
  function bindLevel3Scroll(){
    const panes=[...document.querySelectorAll(".toc-level3-scroll")];
    if(panes.length!==2)return;
    panes.forEach((src,index)=>src.addEventListener("scroll",()=>{
      if(level3Syncing)return;
      const dst=panes[index?0:1];
      level3Syncing=true;
      const sy=Math.max(1,src.scrollHeight-src.clientHeight),dy=Math.max(0,dst.scrollHeight-dst.clientHeight);
      const sx=Math.max(1,src.scrollWidth-src.clientWidth),dx=Math.max(0,dst.scrollWidth-dst.clientWidth);
      dst.scrollTop=(src.scrollTop/sy)*dy;
      dst.scrollLeft=(src.scrollLeft/sx)*dx;
      requestAnimationFrame(()=>level3Syncing=false);
    },{passive:true}));
  }
  function setLevel3Zoom(v){
    const previous=level3Zoom;
    level3Zoom=Math.max(30,Math.min(200,Number(v)||100));
    console.log("[NIVEL3][ZOOM]",{requested:v,previous,applied:level3Zoom});
    document.querySelectorAll(".toc-level3-image-wrap").forEach(wrap=>{wrap.style.width=`${level3Zoom}%`});
    const value=document.querySelector("#tocLevel3ZoomValue"),zoomOut=document.querySelector("#tocLevel3ZoomOut"),zoomIn=document.querySelector("#tocLevel3ZoomIn"),reset=document.querySelector("#tocLevel3ZoomReset");
    if(value)value.textContent=`${level3Zoom}%`; if(zoomOut)zoomOut.disabled=level3Zoom<=30; if(zoomIn)zoomIn.disabled=level3Zoom>=200; if(reset)reset.disabled=level3Zoom===100;
  }
  function changeLevel3Zoom(delta){setLevel3Zoom(level3Zoom+Number(delta||0))}
  function textOffSuccess(title,message){
    if(typeof appModal==="function"){appModal({title,message,kind:"success",confirmText:"OK"});return}
    toast(message);
  }
  async function generateLevel3Preview(){
    const row=level3Current();
    if(!row||!level3Selections.length||level3Previewing)return;
    level3Previewing=true;level3Preview=null;renderLevel3Body();
    try{
      const start=await api("/api/action",{method:"POST",body:JSON.stringify({action:"textoff_level3_preview",provider:data.provider,manga:data.manga,chapters:[row.chapter],chapter:row.chapter,source_stage:row.source_stage,source_file:row.source_file,clean_file:row.clean_file,selections:level3Selections.map(item=>({...item}))})});
      const jobId=start?.job_id;
      if(!jobId)throw new Error("Job de prévia não foi criado.");
      let result=null;
      for(let i=0;i<240;i++){
        await new Promise(r=>setTimeout(r,500));
        const j=await api(`/api/job/${encodeURIComponent(jobId)}?_=${Date.now()}`);
        if(j.status==="done"){result=j.result||null;break}
        if(j.status==="error")throw new Error(j.error||j.message||"Falha ao gerar prévia do Nível III.");
      }
      if(!result)throw new Error("A geração da prévia não concluiu no tempo esperado.");
      level3Preview=result;
      level3Selecting=false;
      textOffSuccess("Prévia gerada",result.message||"Prévia do Nível III gerada.");
    }catch(e){
      console.error("[NIVEL3][PREVIEW] erro",e);
      toast(e.message||"Não foi possível gerar a prévia do Nível III.");
    }finally{
      level3Previewing=false;renderLevel3Body();
    }
  }
  function resetLevel3Preview(){
    if(level3Approving)return;
    level3Preview=null;
    level3Selections=[];
    level3Selection=null;
    level3Analysis=null;
    level3Drag=null;
    level3Selecting=true;
    renderLevel3Body();
  }
  async function approveLevel3Preview(){
    const row=level3Current();
    const preview=level3Preview;
    if(!row||!preview?.proposal_id||level3Approving)return;
    level3Approving=true;renderLevel3Body();
    try{
      const start=await api("/api/action",{method:"POST",body:JSON.stringify({action:"textoff_level3_approve",provider:data.provider,manga:data.manga,chapters:[row.chapter],chapter:row.chapter,source_stage:row.source_stage,source_file:row.source_file,clean_file:row.clean_file,proposal_id:preview.proposal_id})});
      const jobId=start?.job_id;
      if(!jobId)throw new Error("Job de aprovação não foi criado.");
      let result=null;
      for(let i=0;i<60;i++){
        await new Promise(r=>setTimeout(r,500));
        const j=await api(`/api/job/${encodeURIComponent(jobId)}?_=${Date.now()}`);
        if(j.status==="done"){result=j.result||null;break}
        if(j.status==="error")throw new Error(j.error||j.message||"Falha ao aprovar a correção do Nível III.");
      }
      if(!result)throw new Error("A aprovação não concluiu no tempo esperado.");
      textOffSuccess("Correção aplicada",result.message||"Correção Nível III aprovada.");
      level3Preview=null;level3Selections=[];level3Selection=null;level3Analysis=null;level3Selecting=false;
      state=await api(`/api/textoff-compare?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&_=${Date.now()}`);
      await loadLevel3();
    }catch(e){
      console.error("[NIVEL3][APPROVE] erro",e);
      toast(e.message||"Não foi possível aprovar a correção do Nível III.");
    }finally{
      level3Approving=false;renderLevel3Body();
    }
  }
  async function analyzeLevel3(){
    const row=level3Current();
    if(!row||level3Analyzing)return;
    console.log("[NIVEL3][ANALYZE] clique",{chapter:row.chapter,source_stage:row.source_stage,source_file:row.source_file,clean_file:row.clean_file});
    level3Analyzing=true;level3Analysis=null;renderLevel3Body();
    try{
      console.log("[NIVEL3][ANALYZE] POST /api/action");
      const start=await api("/api/action",{method:"POST",body:JSON.stringify({action:"textoff_level3_analyze",provider:data.provider,manga:data.manga,chapters:[row.chapter],chapter:row.chapter,source_stage:row.source_stage,source_file:row.source_file,clean_file:row.clean_file})});
      console.log("[NIVEL3][ANALYZE] resposta criação",start);
      const jobId=start?.job_id;
      if(!jobId)throw new Error("Job de análise não foi criado.");
      let result=null;
      for(let i=0;i<30;i++){
        await new Promise(r=>setTimeout(r,500));
        const j=await api(`/api/job/${encodeURIComponent(jobId)}?_=${Date.now()}`);
        console.log("[NIVEL3][ANALYZE] polling",{attempt:i+1,status:j?.status,message:j?.message,error:j?.error});
        if(j.status==="done"){result=j.result||null;break}
        if(j.status==="error")throw new Error(j.error||j.message||"Falha ao analisar resíduos.");
      }
      if(!result)throw new Error("A análise não concluiu no tempo esperado.");
      level3Analysis=result;
      console.log("[NIVEL3][ANALYZE] concluído",result);
      textOffSuccess("Análise concluída",result.count?`${result.count} região(ões) suspeita(s) encontrada(s).`:"Nenhum resíduo seguro foi identificado automaticamente.");
    }catch(e){
      console.error("[NIVEL3][ANALYZE] erro",e);
      toast(e.message||"Não foi possível analisar resíduos.");
    }finally{
      level3Analyzing=false;renderLevel3Body();
    }
  }
  async function flagCorrection(){
    const row=currentRow();
    const items=Array.isArray(row?.items)?row.items:[];
    const item=selectedPage>=0?items[selectedPage]:null;
    if(!row||!item||flagging||item.level3_status==="PENDENTE_NIVEL3")return;
    flagging=true;renderBody();
    try{
      const response=await fetch("/api/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"textoff_level3_flag",provider:data.provider,manga:data.manga,chapters:[String(row.chapter)],source_stage:row.source_stage,source_file:item.source_file,clean_file:item.clean_file})});
      const created=await response.json();
      if(!response.ok||created.error)throw new Error(created.error||"Não foi possível sinalizar a correção.");
      const jobId=created.job_id;
      if(!jobId)throw new Error("Job do Nível III não retornado.");
      for(let attempt=0;attempt<20;attempt++){
        await new Promise(resolve=>setTimeout(resolve,500));
        const jr=await fetch(`/api/job/${encodeURIComponent(jobId)}?_=${Date.now()}`,{cache:"no-store"});
        const job=await jr.json();
        if(!jr.ok||job.error||job.status==="error")throw new Error(job.error||job.message||"Falha ao sinalizar a correção.");
        if(job.status==="done"){
          state=await api(`/api/textoff-compare?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&_=${Date.now()}`);
          textOffSuccess("Correção sinalizada","Página sinalizada para correção assistida no Nível III.");
          return;
        }
      }
      throw new Error("A sinalização do Nível III demorou mais que o esperado.");
    }catch(e){
      toast(e.message||"Não foi possível sinalizar a correção.");
    }finally{
      flagging=false;renderBody();
    }
  }
  window.TextOffCompareUI={render,renderCorrection,selectChapter,backToHub,selectImage,moveImage,changeZoom,resetZoom,setQuery,setSource,setQcStatus,changePage,setStudioMode,filterStudioPages,showThumb,hideThumb,flagCorrection,selectLevel3,setLevel3Zoom,changeLevel3Zoom,analyzeLevel3,toggleLevel3Selection,generateLevel3Preview,resetLevel3Preview,approveLevel3Preview};

  /* === TEXT OFF · MODO FOCO (UI only) === */
  const textOffFocus={mode:null,scheduled:false};

  function focusClone(node){
    if(!node)return null;
    const clone=node.cloneNode(true);
    if(clone.id)clone.removeAttribute("id");
    clone.querySelectorAll("[id]").forEach(x=>x.removeAttribute("id"));
    clone.querySelectorAll(".bal-zoom-reset").forEach(x=>x.textContent="1:1");
    return clone;
  }

  function ensureFocusBar(){
    let bar=document.querySelector("#tocFocusBar");
    if(bar)return bar;
    bar=document.createElement("div");
    bar.id="tocFocusBar";
    bar.className="toc-focus-bar";
    bar.hidden=true;
    bar.innerHTML=`<div class="toc-focus-identity"><strong id="tocFocusTitle"></strong><span id="tocFocusContext"></span></div>
      <div id="tocFocusActions" class="toc-focus-slot toc-focus-actions"></div>
      <div id="tocFocusZoom" class="toc-focus-slot toc-focus-zoom"></div>
      <div id="tocFocusNav" class="toc-focus-slot toc-focus-nav"></div>
      <div class="toc-focus-system">
        <button class="btn toc-focus-exit" type="button" onclick="TextOffCompareUI.toggleFocus()">Sair do foco</button>
        <button class="btn toc-focus-fullscreen" type="button" onclick="TextOffCompareUI.toggleFullscreen()" aria-label="Alternar tela cheia" title="Tela cheia">⛶</button>
      </div>`;
    document.body.appendChild(bar);
    return bar;
  }

  function focusContext(){
    if(document.querySelector("#textoffLevel3Body .toc-level3-detail"))return "level3";
    if(document.querySelector("#textOffCompareBody .toc-qc-studio-toolbar")&&document.querySelector("#textOffCompareBody .toc-qc-canvas"))return "compare";
    return null;
  }

  function ensureFocusEntryButtons(){
    const compareHead=document.querySelector("#textOffCompareBody .toc-qc-studio-toolbar");
    const compareRight=compareHead?.querySelector(".toc-qc-zone-right");
    if(compareRight&&!compareRight.querySelector(".toc-focus-entry")){
      const b=document.createElement("button");
      b.className="btn toc-focus-entry";
      b.type="button";b.textContent="Modo foco";
      b.onclick=e=>{e.stopPropagation();toggleFocus("compare")};
      compareRight.insertBefore(b,compareRight.firstChild);
    }
    const level3Right=document.querySelector("#textoffLevel3Body .toc-level3-head-actions");
    if(level3Right&&!level3Right.querySelector(".toc-focus-entry")){
      const b=document.createElement("button");
      b.className="btn toc-focus-entry";
      b.type="button";b.textContent="Modo foco";
      b.onclick=()=>toggleFocus("level3");
      level3Right.insertBefore(b,level3Right.firstChild);
    }
  }

  function fillFocusSlot(id,node){
    const slot=document.querySelector(id);
    if(!slot)return;
    slot.replaceChildren();
    const clone=focusClone(node);
    if(clone)slot.appendChild(clone);
  }

  function syncFocusBar(){
    ensureFocusEntryButtons();
    if(!textOffFocus.mode)return;
    const actual=focusContext();
    if(!actual){exitFocus();return}
    textOffFocus.mode=actual;
    document.body.classList.toggle("textoff-focus-compare",actual==="compare");
    document.body.classList.toggle("textoff-focus-level3",actual==="level3");
    const bar=ensureFocusBar();
    bar.hidden=false;

    if(actual==="compare"){
      const caption=document.querySelector("#textOffCompareBody .toc-qc-breadcrumb")?.textContent?.trim()||"";
      document.querySelector("#tocFocusTitle").textContent="TEXTO OFF › Revisar resultados";
      document.querySelector("#tocFocusContext").textContent=caption;
      fillFocusSlot("#tocFocusActions",document.querySelector("#textOffCompareBody .toc-qc-zone-right .toc-correction-btn"));
      const compareHead=document.querySelector("#textOffCompareBody .toc-qc-studio-toolbar");
      fillFocusSlot("#tocFocusZoom",compareHead?.querySelector(".bal-zoom-control"));
      fillFocusSlot("#tocFocusNav",document.querySelector("#textOffCompareBody .toc-qc-pager"));
    }else{
      const context=document.querySelector("#textoffLevel3Body .toc-level3-detail-head h2")?.textContent?.trim()||"";
      document.querySelector("#tocFocusTitle").textContent="TEXTO OFF · NÍVEL III › Correção assistida";
      document.querySelector("#tocFocusContext").textContent=context;
      fillFocusSlot("#tocFocusActions",document.querySelector("#textoffLevel3Body .toc-level3-action-buttons"));
      fillFocusSlot("#tocFocusZoom",document.querySelector("#textoffLevel3Body .toc-level3-detail-head .bal-zoom-control"));
      fillFocusSlot("#tocFocusNav",null);
    }
  }

  function enterFocus(mode){
    const actual=mode||focusContext();
    if(!actual)return;
    textOffFocus.mode=actual;
    document.body.classList.add("textoff-focus-mode");
    syncFocusBar();
  }

  function exitFocus(){
    textOffFocus.mode=null;
    document.body.classList.remove("textoff-focus-mode","textoff-focus-compare","textoff-focus-level3");
    const bar=document.querySelector("#tocFocusBar");
    if(bar)bar.hidden=true;
  }

  function toggleFocus(mode){
    hideThumb();
    if(textOffFocus.mode)exitFocus();
    else enterFocus(mode);
  }

  async function toggleFullscreen(){
    try{
      if(document.fullscreenElement)await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    }catch(e){
      toast(e.message||"Não foi possível alternar a tela cheia.");
    }
  }

  function scheduleFocusSync(){
    if(textOffFocus.scheduled)return;
    textOffFocus.scheduled=true;
    requestAnimationFrame(()=>{
      textOffFocus.scheduled=false;
      ensureFocusEntryButtons();
      if(textOffFocus.mode)syncFocusBar();
    });
  }

  const textOffFocusObserver=new MutationObserver(scheduleFocusSync);
  textOffFocusObserver.observe(document.querySelector("#page")||document.body,{
    childList:true,subtree:true,characterData:true,attributes:true,
    attributeFilter:["disabled","class","hidden","style"]
  });
  document.addEventListener("fullscreenchange",scheduleFocusSync);
  Object.assign(window.TextOffCompareUI,{toggleFocus,toggleFullscreen});
  requestAnimationFrame(scheduleFocusSync);
  /* === /TEXT OFF · MODO FOCO === */


})();