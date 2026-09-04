const $=s=>document.querySelector(s);let cat={},data=null,page="overview",reviewCh=null,lastUpdated="",tablePage=1,tableStatus="all";const PAGE_SIZE=10;const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));async function api(u,o){let r=await fetch(u,o),j=await r.json();if(!r.ok)throw Error(j.error||"Erro");return j}function toast(m){let t=$("#toast");t.textContent=m;t.style.display="block";setTimeout(()=>t.style.display="none",4000)}
let appModalResolve=null;
function closeAppModal(value=false){document.querySelector("#appModal")?.remove();document.removeEventListener("keydown",appModalKey);if(appModalResolve){let r=appModalResolve;appModalResolve=null;r(value)}}
function appModalKey(e){if(e.key==="Escape")closeAppModal(false)}
function appModal({title,message="",chips=[],details=[],confirm=false,confirmText="OK",cancelText="Cancelar",kind="info"}){
  document.querySelector("#appModal")?.remove();
  return new Promise(resolve=>{
    appModalResolve=resolve;let overlay=document.createElement("div");overlay.id="appModal";overlay.className="app-modal-overlay";
    let chipHtml=chips.length?`<div class="app-modal-chips">${chips.map(x=>`<span class="app-modal-chip"><b>${esc(x.value)}</b> ${esc(x.label)}</span>`).join("")}</div>`:"";
    let detailHtml=details.length?`<div class="app-modal-details">${details.map(x=>`<div class="app-modal-detail"><b>${esc(x.title||"Ocorrência")}</b><span>${esc(x.message||"")}</span></div>`).join("")}</div>`:"";
    overlay.innerHTML=`<div class="app-modal app-modal-${esc(kind)} ${confirm&&!chips.length&&!details.length?"app-modal-compact":""}" role="dialog" aria-modal="true"><div class="app-modal-head"><div><div class="caption">PROCESSAMENTO</div><h2>${esc(title)}</h2></div><button class="app-modal-x" aria-label="Fechar">&times;</button></div>${message?`<p class="app-modal-message">${esc(message)}</p>`:""}${chipHtml}${detailHtml}<div class="app-modal-actions">${confirm?`<button class="btn" data-modal-cancel>${esc(cancelText)}</button>`:""}<button class="btn primary" data-modal-ok>${esc(confirmText)}</button></div></div>`;
    overlay.onclick=e=>{if(e.target===overlay)closeAppModal(false)};overlay.querySelector(".app-modal-x").onclick=()=>closeAppModal(false);
    overlay.querySelector("[data-modal-cancel]")?.addEventListener("click",()=>closeAppModal(false));overlay.querySelector("[data-modal-ok]").onclick=()=>closeAppModal(true);
    document.body.appendChild(overlay);document.addEventListener("keydown",appModalKey);
  });
}
async function askAppModal(title,message,confirmText="Confirmar"){return appModal({title,message,confirm:true,confirmText})}
function applySidebarState(){
  let collapsed=localStorage.getItem("fominha.sidebar.collapsed")==="1";
  document.body.classList.toggle("sidebar-collapsed",collapsed);
  let b=$("#sidebarToggle");if(b)b.setAttribute("aria-expanded",String(!collapsed));
}
function toggleSidebar(){
  let collapsed=!document.body.classList.contains("sidebar-collapsed");
  document.body.classList.toggle("sidebar-collapsed",collapsed);
  localStorage.setItem("fominha.sidebar.collapsed",collapsed?"1":"0");
  let b=$("#sidebarToggle");if(b)b.setAttribute("aria-expanded",String(!collapsed));
}
function applyTextoOffNavState(){
  const group=document.querySelector("[data-texto-off-nav]");
  if(!group)return;
  const saved=localStorage.getItem("fominha.textoOff.expanded");
  const open=saved!=="0";
  group.classList.toggle("open",open);
  const toggle=group.querySelector(".texto-off-toggle");
  if(toggle)toggle.setAttribute("aria-expanded",String(open));
}
function toggleTextoOffNav(button){
  const group=button?.closest("[data-texto-off-nav]");
  if(!group)return;
  const open=!group.classList.contains("open");
  group.classList.toggle("open",open);
  button.setAttribute("aria-expanded",String(open));
  localStorage.setItem("fominha.textoOff.expanded",open?"1":"0");
}
async function init(){applySidebarState();applyTextoOffNavState();cat=await api("/api/catalog");$("#provider").innerHTML=Object.keys(cat).map(x=>`<option>${x}</option>`).join("");$("#provider").onchange=fill;$("#manga").onchange=load;document.querySelectorAll("nav button[data-page]").forEach(b=>b.onclick=()=>{page=b.dataset.page;tablePage=1;tableStatus="all";window._tableQuery="";document.querySelectorAll("nav button[data-page]").forEach(x=>x.classList.toggle("active",x===b));render()});fill()}function fill(){let p=$("#provider").value;$("#manga").innerHTML=(cat[p]||[]).map(x=>`<option>${esc(x)}</option>`).join("");load()}async function load(){let p=$("#provider").value,m=$("#manga").value;if(!m){data=null;return render()}data=await api(`/api/state?provider=${encodeURIComponent(p)}&manga=${encodeURIComponent(m)}&_=${Date.now()}`);lastUpdated=new Date().toLocaleTimeString("pt-BR");$("#badge").textContent=data.summary.review_pending??data.summary.pending??0;let b2=$("#badgeLevel2");if(b2)b2.textContent=data.summary.partial||0;render()}async function refreshStatus(){let p=$("#provider").value,m=$("#manga").value;cat=await api(`/api/catalog?_=${Date.now()}`);let providers=Object.keys(cat);$("#provider").innerHTML=providers.map(x=>`<option>${x}</option>`).join("");$("#provider").value=providers.includes(p)?p:(providers[0]||"");let works=cat[$("#provider").value]||[];$("#manga").innerHTML=works.map(x=>`<option>${esc(x)}</option>`).join("");$("#manga").value=works.includes(m)?m:(works[0]||"");await load()}function head(t,d){return `<div class="head"><div><h1>${esc(t)}</h1><div class="muted">${esc(d)}</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Sincronizar</button></div>`}
function normalizePdfMergeTable(){
  const tables=[...document.querySelectorAll("table")];
  const table=tables.find(t=>{
    const labels=[...t.querySelectorAll("thead th")].map(x=>x.textContent.trim().toUpperCase());
    return labels.includes("PDF MERGE");
  });
  if(!table) return;

  const headCells=[...table.querySelectorAll("thead th")];
  const removeHeaderIndexes=[];
  headCells.forEach((th,i)=>{
    const label=th.textContent.trim().toUpperCase();
    if(label==="IMAGENS" || label==="PDF") removeHeaderIndexes.push(i);
  });
  removeHeaderIndexes.sort((a,b)=>b-a).forEach(i=>{
    table.querySelectorAll("tr").forEach(tr=>{
      const cells=[...tr.children];
      if(cells[i]) cells[i].remove();
    });
  });

  const desiredHead=[...table.querySelectorAll("thead th")].length;
  table.querySelectorAll("tbody tr").forEach(tr=>{
    let cells=[...tr.children];
    if(desiredHead===5 && cells.length===7){
      cells[5]?.remove();
      cells=[...tr.children];
      cells[2]?.remove();
    }
  });
}

async function enhancePdfMergeSuccessModal(){
  const modal=document.querySelector("#appModal");
  if(!modal) return;

  const title=modal.querySelector("h1,h2,.app-modal-title")?.textContent?.trim() || "";
  if(title!=="PDF do Merge gerado") return;
  if(modal.dataset.pdfMergeEnhanced==="1") return;
  modal.dataset.pdfMergeEnhanced="1";

  let files=[];
  try{
    const r=await api(`/api/pdf-merge-latest?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}`);
    files=Array.isArray(r?.files)?r.files:[];
  }catch(e){}

  const detail=modal.querySelector(".app-modal-detail");
  if(detail && files.length){
    const grouped=new Map();
    files.forEach(x=>{
      const ch=String(x.chapter||"");
      if(!grouped.has(ch)) grouped.set(ch,[]);
      grouped.get(ch).push(x.file);
    });

    detail.innerHTML=[...grouped.entries()].map(([ch,names])=>`
      <div class="pdf-merge-result-group">
        <strong>${ch?`Cap. ${esc(ch)}`:"Resultado"}</strong>
        ${names.map(n=>`<span>${esc(n)}</span>`).join("")}
      </div>
    `).join("");
  }

  const actions=modal.querySelector(".app-modal-actions");
  const closeBtn=actions?.querySelector("[data-modal-ok]") || actions?.querySelector("button:last-child");
  if(actions && closeBtn && !actions.querySelector(".pdf-merge-open-folder")){
    const chapters=[...new Set(files.map(x=>String(x.chapter||"")).filter(Boolean))];
    const openBtn=document.createElement("button");
    openBtn.className="btn pdf-merge-open-folder";
    openBtn.textContent="Abrir pasta";
    openBtn.onclick=async()=>{
      const chapter=chapters.length===1?chapters[0]:"";
      try{
        await api(`/api/open-folder?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(chapter)}&kind=pdf_merge`);
      }catch(e){
        toast(e.message||"Não foi possível abrir a pasta.");
      }
    };
    actions.insertBefore(openBtn,closeBtn);
  }
}

function installPdfMergeUiNormalizer(){
  if(window.__pdfMergeUiNormalizerInstalled) return;
  window.__pdfMergeUiNormalizerInstalled=true;
  const run=()=>{
    normalizePdfMergeTable();
    enhancePdfMergeSuccessModal();
  };
  const observer=new MutationObserver(()=>requestAnimationFrame(run));
  observer.observe(document.body,{childList:true,subtree:true});
  requestAnimationFrame(run);
}

function render(){let b3=$("#badgeLevel3");if(b3&&data)b3.textContent=data.chapters.filter(x=>x.merge_level3_pending).length;let root=$("#page");if(!data){root.innerHTML='<div class="muted">Nenhuma obra encontrada.</div>';return}if(page==="overview")return overview(root);if(page==="validate_images")return validateImages(root);if(page==="merge_level2")return mergeLevel2(root);if(page==="merge_level3")return mergeLevel3(root);if(page==="review")return review(root);if(page==="review_v2")return reviewV2(root);table(root,page)}function overview(r){let s=data.summary,p=data.chapters.filter(x=>x.merge_state==="pendente_review"||(x.merge_state==="parcial"&&!x.merge_level2_validated)).slice(0,4);r.innerHTML=`<div class="head"><div><div class="caption">VISÃO GERAL</div><h1>${esc(data.manga)}</h1><div class="muted">${esc(data.provider)} · pós-processamento</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Sincronizar</button></div><div class="kpis"><div class="kpi"><b>${s.chapters}</b><span>CAPÍTULOS</span></div><div class="kpi"><b>${s.merges}</b><span>MERGES</span></div><div class="kpi"><b>${s.pending}</b><span>PENDENTES DE REVISÃO</span></div><div class="kpi"><b>${s.partial??0}</b><span>NÍVEL II</span></div><div class="kpi"><b>${s.review}</b><span>EM REVISÃO</span></div><div class="kpi"><b>${s.pdfs}</b><span>PDFs ORIGINAIS</span></div></div><h3>Atividade da obra</h3><div class="activity">${p.map(x=>`<div class="card"><div><b>Capítulo ${esc(x.chapter)} <span class="warn">· ${x.merge_state==="parcial"?"NÍVEL II":"PENDENTE DE REVISÃO"}</span></b><div class="muted">${mergePartialText(x)}</div></div><button class="btn primary" onclick="${x.merge_state==="parcial"?`goLevel2('${esc(x.chapter)}')`:`goReview('${esc(x.chapter)}')`}">Tratar agora</button></div>`).join("")||'<div class="card ok">Todos os merges concluídos.</div>'}</div>`}function mergeLabel(x){
  if(x.merge)return {cls:"ok",text:`✓ ${x.merged_images}`};
  if(x.merge_error)return {cls:"warn",text:"⚠ Inválido"};
  if(x.merge_state==="parcial")return {cls:"warn",text:"Parcial"};
  if(x.merge_state==="pendente_review"||x.merge_state==="pendente"||x.merge_failed)return {cls:"warn",text:"Pendente"};
  return {cls:"muted",text:"Novo"};
}
let dimensionData=null,dimensionChapter=null,dimensionStep=1,dimensionTolerance=3,dimensionFilter="all";
async function loadDimensionAnalysis(){
  try{
    dimensionData=await api(`/api/dimension-analysis?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&_=${Date.now()}`);
    let badge=$("#badgeDimensions");if(badge)badge.textContent=dimensionData?.summary?.chapters_requiring_analysis||0;
    if(page==="validate_images")renderValidateImagesBody();
  }catch(e){toast(e.message||"Não foi possível carregar a análise de dimensões.")}
}
function dimensionFlow(){return `<div class="dim-flow"><div class="dim-node ${dimensionStep>1?'done':dimensionStep===1?'current':''}"><i></i><span>Validar imagens</span></div><div class="dim-node ${dimensionStep>2?'done':dimensionStep===2?'current':''}"><i></i><span>Efetuar correção</span></div><div class="dim-node ${dimensionStep===3?'current':''}"><i></i><span>Composição final</span></div></div>`}
function validateImages(r){
  r.innerHTML=head("Validar imagens","Analise as imagens baixadas, identifique divergências de dimensão e aplique correções antes das próximas etapas de processamento.")+`<div id="dimensionBody"></div>`;
  renderValidateImagesBody();loadDimensionAnalysis();
}
function dimSelected(){return [...document.querySelectorAll('.dim-ck:checked')].map(x=>x.value)}
function dimSelectChapter(ch){dimensionChapter=String(ch);dimensionStep=1;renderValidateImagesBody()}
function dimSetStep(step){dimensionStep=step;renderValidateImagesBody()}
function dimSetFilter(filter){dimensionFilter=filter;renderValidateImagesBody()}
function dimensionSourceUrl(ch,file){return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=source&chapter=${encodeURIComponent(ch)}&file=${encodeURIComponent(file)}`}
function renderValidateImagesBody(){
  let host=$("#dimensionBody");if(!host||page!=="validate_images")return;
  let analyzed=new Map((dimensionData?.chapters||[]).map(x=>[String(x.chapter),x]));
  let allList=data.chapters.map(x=>{let a=analyzed.get(String(x.chapter));return {...x,dimension:a}});
  let divergentCount=allList.filter(x=>x.dimension?.status==="REQUER_ANALISE").length;
  let okCount=allList.filter(x=>x.dimension?.status==="OK").length;
  let pendingCount=allList.filter(x=>!x.dimension).length;
  let list=dimensionFilter==="divergent"
    ?allList.filter(x=>x.dimension?.status==="REQUER_ANALISE")
    :dimensionFilter==="ok"
      ?allList.filter(x=>x.dimension?.status==="OK")
      :dimensionFilter==="pending"
        ?allList.filter(x=>!x.dimension)
        :allList;
  if(!dimensionChapter||!list.some(x=>String(x.chapter)===String(dimensionChapter))){let first=list.find(x=>x.dimension?.status==="REQUER_ANALISE")||list[0];dimensionChapter=first?String(first.chapter):null}
  let current=allList.find(x=>String(x.chapter)===String(dimensionChapter));let a=current?.dimension;
  let exceptions=(a?.images||[]).filter(x=>x.classification==="EXCECAO_DIMENSAO");
  let detail=dimensionStep===1?`<div class="dim-detail"><div class="dim-title"><div><span class="caption">ETAPA 1</span><h2>${current?`Capítulo ${esc(current.chapter)}`:"Selecione um capítulo"}</h2></div>${a?`<span class="dim-status ${a.status==='OK'?'ok':'attention'}">${a.status==='OK'?'OK':'Requer análise'}</span>`:''}</div>${!a?`<div class="dim-empty">Este capítulo ainda não possui análise de dimensões.</div>`:`<div class="dim-kpis"><div><b>${a.image_count}</b><span>Imagens</span></div><div><b>${a.dominant_width}px</b><span>Largura dominante</span></div><div><b>±${a.tolerance_percent}%</b><span>Tolerância</span></div><div><b>${a.exceptions}</b><span>Exceções</span></div></div><h3>Divergências encontradas</h3><div class="dim-exceptions">${exceptions.map(x=>`<div><b>${esc(x.file)}</b><span>${x.width} × ${x.height}px</span><small>Diferença: ${x.difference_px>0?'+':''}${x.difference_px}px (${x.difference_percent.toFixed(2)}%)</small></div>`).join('')||'<div class="dim-okbox">Nenhuma divergência fora da tolerância.</div>'}</div>${exceptions.length?`<button class="btn primary" onclick="dimSetStep(2)">Sugestão de correção</button>`:''}`}</div>`:
  dimensionStep===2?`<div class="dim-detail"><div class="dim-title"><div><span class="caption">ETAPA 2</span><h2>Capítulo ${esc(current?.chapter||'')}</h2></div><span class="dim-status attention">${exceptions.length} imagem(ns)</span></div><div class="dim-suggestion"><h3>Sugestão de correção</h3><p>Normalizar proporcionalmente somente as imagens fora da tolerância para a largura dominante de <b>${a?.dominant_width||'—'} px</b>. Os originais serão preservados com sufixo _old e as versões corrigidas permanecerão ativas em IMG com os nomes originais.</p><div class="dim-compare-list">${exceptions.map(x=>{let h=Math.max(1,Math.round(x.height*((a?.dominant_width||x.width)/x.width)));let ratio=Math.min(1,(a?.dominant_width||x.width)/x.width);let src=dimensionSourceUrl(current?.chapter||'',x.file);return `<section class="dim-compare"><header><b>${esc(x.file)}</b><span>Normalização proporcional</span></header><div class="dim-before-after"><div class="dim-preview-card"><div class="dim-preview-head"><strong>Antes</strong><span>${x.width} × ${x.height}px</span></div><div class="dim-preview-stage before"><img src="${src}" alt="Antes · ${esc(x.file)}"></div></div><div class="dim-preview-arrow">→</div><div class="dim-preview-card"><div class="dim-preview-head"><strong>Depois</strong><span>${a?.dominant_width} × ${h}px</span></div><div class="dim-preview-stage after"><img src="${src}" alt="Depois · ${esc(x.file)}" style="width:${(ratio*100).toFixed(2)}%"></div></div></div><div class="dim-fix"><div><b>Original preservado</b><span>${x.width} × ${x.height}px</span></div><strong>→</strong><div><b>Correção sugerida</b><span>${a?.dominant_width} × ${h}px</span></div></div></section>`}).join('')}</div><div class="dim-note">A prévia “Depois” representa a escala proporcional proposta. A correção real só é materializada após clicar em “Aplicar correções”. Antes da correção, cada original será preservado como backup _old.</div></div><div class="dim-actions"><button class="btn" onclick="dimSetStep(1)">Voltar</button><button class="btn primary" onclick="applyDimensionCorrection('${esc(current?.chapter||'')}')">Aplicar correções</button></div></div>`:
  `<div class="dim-detail"><div class="dim-title"><div><span class="caption">ETAPA 3</span><h2>Correção aplicada · Capítulo ${esc(current?.chapter||'')}</h2></div><span class="dim-status ${a?.status==='OK'?'ok':'attention'}">${a?.status==='OK'?'OK':'Requer análise'}</span></div><div class="dim-final"><h3>Resultado</h3><p>As imagens ativas foram corrigidas diretamente em IMG e os arquivos originais foram preservados com sufixo _old.</p><div class="dim-kpis"><div><b>${a?.image_count||0}</b><span>Imagens ativas</span></div><div><b>${a?.exceptions||0}</b><span>Exceções restantes</span></div></div><div class="dim-note">IMG é a fonte ativa. Arquivos _old são backups e ficam fora dos processamentos.</div><button class="btn" onclick="openDimensionFolder()">Abrir análise</button></div></div>`;
  host.innerHTML=dimensionFlow()+`<div class="toolbar standard-filterbar"><input class="search" placeholder="Buscar capítulo..." oninput="document.querySelectorAll('.dim-row').forEach(r=>r.hidden=!r.dataset.n.includes(this.value.toLowerCase()))"><div class="status-filter" role="group" aria-label="Filtrar capítulos"><button class="tab ${dimensionFilter==='all'?'active':''}" onclick="dimSetFilter('all')">Todos</button><button class="tab ${dimensionFilter==='ok'?'active':''}" onclick="dimSetFilter('ok')">OK <span>${okCount}</span></button><button class="tab ${dimensionFilter==='divergent'?'active':''}" onclick="dimSetFilter('divergent')">Com exceções <span>${divergentCount}</span></button><button class="tab ${dimensionFilter==='pending'?'active':''}" onclick="dimSetFilter('pending')">Não analisados <span>${pendingCount}</span></button></div><label class="dim-tolerance">Tolerância <input type="number" min="0" max="20" step="0.5" value="${dimensionTolerance}" onchange="dimensionTolerance=Number(this.value)||3"> %</label><button class="btn primary" onclick="analyzeDimensions()">Analisar</button></div><div class="dim-layout"><div class="dim-list"><div class="dim-list-head"><span>${visibleMaster(".dim-ck","dim-visible-master")}</span><b>CAP.</b><span>STATUS</span></div>${list.map(x=>`<div class="dim-row ${String(x.chapter)===String(dimensionChapter)?'active':''}" data-n="${esc(String(x.chapter).toLowerCase())}"><input class="dim-ck" type="checkbox" value="${esc(x.chapter)}" onchange="syncVisibleMaster(document.querySelector('.dim-visible-master'),'.dim-ck')"><button onclick="dimSelectChapter('${esc(x.chapter)}')"><b>${esc(x.chapter)}</b><span class="${x.dimension?.status==='OK'?'ok':x.dimension?.status==='REQUER_ANALISE'?'attention':'muted'}">${x.dimension?.status==='OK'?'✓ OK':x.dimension?.status==='REQUER_ANALISE'?`! ${x.dimension.exceptions} exceção(ões)`:'Não analisado'}</span></button></div>`).join('')||'<div class="dim-filter-empty">Nenhum capítulo com divergência.</div>'}</div>${detail}</div>`;
}
async function analyzeDimensions(){let ch=dimSelected();if(!ch.length)return toast("Selecione ao menos um capítulo.");dimensionStep=1;job("dimension_analyze",ch,{tolerance:dimensionTolerance});setTimeout(loadDimensionAnalysis,1200)}
async function applyDimensionCorrection(ch){if(!ch)return;if(!(await askAppModal("Aplicar correção",`Normalizar proporcionalmente as exceções do Cap. ${ch}? Os originais serão preservados como _old.`,"Aplicar")))return;dimensionStep=3;job("dimension_correct",[ch],{tolerance:dimensionTolerance});setTimeout(loadDimensionAnalysis,1200);renderValidateImagesBody()}
async function openDimensionFolder(){try{await api(`/api/open-folder?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=dimension_analysis`)}catch(e){toast(e.message||"Não foi possível abrir a pasta.")}}

function tableStatusOptions(k){
  if(k==="merge")return [["all","Todos"],["novo","Novos"],["pendente_review","Pendentes"],["parcial","Parciais"]];
  if(k==="pdf")return [["all","Todos"],["pending","Sem PDF"],["done","Gerados"]];
  if(k==="pdf_merge")return [["all","Todos"],["pending","Sem PDF"],["done","Gerados"]];
  if(k==="clean"||k==="clean_merged")return [["all","Todos"],["pending","Não processados"],["done","Processados"]];
  return [];
}
function tableStatusFilter(k){
  let options=tableStatusOptions(k);
  if(!options.length)return "";
  return `<div class="status-filter" role="group" aria-label="Filtrar status">${options.map(([value,label])=>`<button class="tab ${tableStatus===value?"active":""}" onclick="setTableStatus('${value}')">${label}</button>`).join("")}</div>`;
}
function tableFilteredRows(k){
  let q=String(window._tableQuery||"").trim().toLowerCase();
  let rows=data.chapters.filter(x=>String(x.chapter).toLowerCase().includes(q));
  if(k==="clean_merged")rows=rows.filter(x=>x.merge===true);
  if(tableStatus==="all")return rows;
  if(k==="merge")return rows.filter(x=>(x.merge_state||(!x.merge&&!x.merge_failed?"novo":x.merge_failed?"pendente_review":"concluido"))===tableStatus);
  if(k==="pdf")return rows.filter(x=>tableStatus==="done"?!!x.pdf:!x.pdf);
  if(k==="pdf_merge")return rows.filter(x=>tableStatus==="done"?!!x.pdf_merge:!x.pdf_merge);
  if(k==="clean")return rows.filter(x=>tableStatus==="done"?!!x.clean:!x.clean);
  if(k==="clean_merged")return rows.filter(x=>tableStatus==="done"?!!x.clean_merged:!x.clean_merged);
  return rows;
}
function table(r,k){
  let cfg={pdf:["Gerar PDF","Gerar PDFs a partir das imagens originais validadas.","pdf"],merge:["Auto-Merge","Aplicar o Merge V3 preservando IMG.","merge"],clean:["Texto Off — Original","Executar Bubble Cleaner V3.5 nas imagens originais.","clean"],clean_merged:["Texto Off — Merged","Limpeza de texto aplicada às imagens consolidadas em MERGE.","clean_merged"],pdf_merge:["PDF do Merge","Gerar PDF com as imagens oficialmente unificadas.","pdf_merge"]}[k];
  let all=tableFilteredRows(k),pages=Math.max(1,Math.ceil(all.length/PAGE_SIZE));tablePage=Math.min(Math.max(1,tablePage),pages);let cleanField=k==="clean_merged"?"clean_merged":"clean";
  let rows=all.slice((tablePage-1)*PAGE_SIZE,tablePage*PAGE_SIZE);
  let statusFilter=tableStatusFilter(k);
  let pager=`<div class="table-pager"><span>${all.length?((tablePage-1)*PAGE_SIZE+1):0}–${Math.min(tablePage*PAGE_SIZE,all.length)} de ${all.length}</span><div><button class="btn" ${tablePage<=1?"disabled":""} onclick="changeTablePage(-1)">&lt;&lt;</button><span class="page-indicator">${tablePage} / ${pages}</span><button class="btn" ${tablePage>=pages?"disabled":""} onclick="changeTablePage(1)">&gt;&gt;</button></div></div>`;
  let actionLabel={pdf:"Gerar PDF",merge:"Executar",clean:"Limpar",clean_merged:"Limpar",pdf_merge:"Gerar PDF"}[k]||"Executar";
  r.innerHTML=head(cfg[0],cfg[1])+`<div class="toolbar standard-filterbar"><input id="q" class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;tablePage=1;render()">${statusFilter}<button class="btn primary filter-primary-action" onclick="runTableAction('${k}','${cfg[2]}')">${actionLabel}</button></div><div class="panel"><table><thead><tr><th>${visibleMaster()}</th><th>CAP.</th><th>MERGE</th><th>CLEAN</th><th>PDF MERGE</th></tr></thead><tbody>${rows.map(x=>{let ml=mergeLabel(x);return `<tr data-n="${esc(x.chapter).toLowerCase()}"><td><input class="ck" type="checkbox" value="${esc(x.chapter)}" onchange="syncVisibleMaster(document.querySelector('.visible-master'),'.ck')"></td><td>${esc(x.chapter)}</td><td>${x.pages}</td><td class="${ml.cls}">${ml.text}</td><td class="${x[cleanField]?'ok':'muted'}">${x[cleanField]?'✓':'—'}</td><td class="${x.pdf?'ok':'warn'}">${x.pdf?'✓':'Pendente'}</td><td class="${x.pdf_merge?'ok':'muted'}">${x.pdf_merge?'✓':'—'}</td></tr>`}).join("")}</tbody></table>${pager}</div>`;
}
function runTableAction(kind,action){
  runSelected(action);
}
function setTableStatus(v){tableStatus=v;tablePage=1;render()}
function changeTablePage(d){tablePage+=d;render()}
function filter(){tablePage=1;render()}
function allv(){document.querySelectorAll("tbody .ck").forEach(x=>x.checked=true)}
function mergePartialText(x){
  const p=x?.merge_partition||{};
  const resolved=Number(p.resolved_source_pages_count||0),pending=Number(p.pending_source_pages_count||0);
  if(!pending)return "Auto-Merge não conseguiu concluir este capítulo.";
  return `${resolved} página(s) resolvida(s) automaticamente · ${pending} página(s) permanecem para revisão.`;
}
function reviewPendingSummary(x){
  const p=x?.merge_partition||{},segs=Array.isArray(p.pending_segments)?p.pending_segments:[];
  if(!segs.length)return "Este capítulo está pendente e ainda não possui uma proposta de merge.";
  const labels=segs.map(s=>{const src=Array.isArray(s.sources)?s.sources:[];if(!src.length)return `Y ${s.global_start??"?"} → ${s.global_end??"?"}`;return src.length===1?src[0]:`${src[0]} → ${src[src.length-1]}`;});
  return `${Number(p.resolved_source_pages_count||0)} página(s) já foram resolvida(s) automaticamente. ${Number(p.pending_source_pages_count||0)} página(s) permanecem na revisão: ${labels.join("; ")}.`;
}

function segLabel(s){const src=Array.isArray(s?.sources)?s.sources:[];if(src.length)return src.length===1?src[0]:`${src[0]} → ${src[src.length-1]}`;return `Y ${s?.global_start??"?"} → ${s?.global_end??"?"}`}
function level2Chapters(){return data.chapters.filter(x=>x.merge_state==="parcial"&&!x.merge_level2_validated)}
function level2RegionLabel(x){
  const p=x?.merge_partition||{},pending=Array.isArray(p.pending_segments)?p.pending_segments:[];
  if(!pending.length)return "—";
  return pending.map(segLabel).join("; ");
}
function level2ResultModal(j,s){
  if(j.action!=="merge_level2")return false;
  let results=s.results||[];
  let ok=results.filter(x=>["ok","success","done","skipped"].includes(String(x.status||"").toLowerCase()));
  let errors=results.filter(x=>String(x.status||"").toLowerCase()==="error");
  let details=results.map(x=>{
    let row=(data?.chapters||[]).find(c=>String(c.chapter)===String(x.chapter))||{};
    let region=level2RegionLabel(row);
    let resolved=Number(x.resolved_segments||0);
    let pending=Number(x.pending_segments||0);
    let message=String(x.status||"").toLowerCase()==="error"
      ? (x.message||"Falha ao validar este capítulo.")
      : pending>0
        ? `${resolved} novo(s) merge(s) seguro(s) gerado(s) pelo Nível II em MERGE_LEVEL2. ${pending} região(ões) seguem para o Auto-Merge Nível III: ${region}.`
        : `${resolved} novo(s) merge(s) seguro(s) gerado(s) pelo Nível II. Nenhuma região permaneceu pendente para o Auto-Merge Nível III.`;
    return {title:`Cap. ${x.chapter}`,message};
  });
  appModal({
    title:errors.length?"Nível II concluído com ocorrências":"Auto-Merge Nível II concluído",
    message:errors.length
      ?"Alguns capítulos ainda precisam de atenção."
      :results.some(x=>Number(x.pending_segments||0)>0)
        ?"O Nível II executou uma nova busca segura somente sobre o residual. Apenas o que ainda não pôde ser resolvido seguirá para o Auto-Merge Nível III."
        :"O Nível II resolveu automaticamente todo o residual recebido e o capítulo pôde seguir para a composição final.",
    kind:errors.length?(ok.length?"partial":"error"):"success",
    chips:[
      {value:ok.length,label:"validado(s)"},
      ...(errors.length?[{value:errors.length,label:"com ocorrência"}]:[])
    ],
    details,
    confirmText:"Fechar"
  }).then(()=>load());
  return true;
}
function mergeLevel2(r){
 let q=String(window._tableQuery||"").trim().toLowerCase();
 let all=level2Chapters().filter(x=>String(x.chapter).toLowerCase().includes(q));
 let pages=Math.max(1,Math.ceil(all.length/PAGE_SIZE));tablePage=Math.min(Math.max(1,tablePage),pages);
 let rows=all.slice((tablePage-1)*PAGE_SIZE,tablePage*PAGE_SIZE);
 let pager=`<div class="table-pager"><span>${all.length?((tablePage-1)*PAGE_SIZE+1):0}–${Math.min(tablePage*PAGE_SIZE,all.length)} de ${all.length}</span><div><button class="btn" ${tablePage<=1?"disabled":""} onclick="changeTablePage(-1)">&lt;&lt;</button><span class="page-indicator">${tablePage} / ${pages}</span><button class="btn" ${tablePage>=pages?"disabled":""} onclick="changeTablePage(1)">&gt;&gt;</button></div></div>`;
 r.innerHTML=head("Auto-Merge Nível II","Buscar novos cortes seguros somente nas regiões que o Auto-Merge inicial não resolveu.")+`<div class="toolbar standard-filterbar"><input id="q" class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;tablePage=1;render()"><div class="status-filter"><button class="tab active" type="button">Pendentes</button></div><button class="btn primary filter-primary-action" onclick="runSelected('merge_level2')">Executar Nível II</button></div><div class="panel"><table><thead><tr><th>${visibleMaster()}</th><th>CAP.</th><th>RESIDUAL RECEBIDO</th><th>REGIÃO DO RESIDUAL</th></tr></thead><tbody>${rows.map(x=>{let p=x.merge_partition||{},pending=Array.isArray(p.pending_segments)?p.pending_segments.length:0;return `<tr data-n="${esc(x.chapter).toLowerCase()}"><td><input class="ck" type="checkbox" value="${esc(x.chapter)}" onchange="syncVisibleMaster(document.querySelector('.visible-master'),'.ck')"></td><td>${esc(x.chapter)}</td><td>${pending}</td><td>${esc(level2RegionLabel(x))}</td></tr>`}).join("")}</tbody></table>${pager}</div>`;
}

function l3IntervalLabel(seg){
  if(!seg)return "—";
  let a=Number(seg.start??seg.global_start??0),b=Number(seg.end??seg.global_end??0);
  return `${a.toLocaleString("pt-BR")} → ${b.toLocaleString("pt-BR")} px`;
}
function l3ReasonLabel(reason){
  const map={
    connected_component_crossing:"Componente estrutural atravessando o corte",
    strong_diagonal_crossing:"Borda diagonal forte atravessando o corte",
    high_edge_density:"Alta densidade de bordas na região do corte",
    closed_contour_crossing:"Contorno estrutural atravessando o corte",
    probable_text_fx:"Provável texto/onomatopeia próximo ao corte",
    text_fx_near_cut:"Provável texto/onomatopeia próximo ao corte",
    possible_text_fx:"Provável texto/onomatopeia próximo ao corte",
    continuous_scene_too_long:"Cena contínua extensa sem corte seguro comprovado",
    structurally_clear:"Estruturalmente seguro",
    safe_local_alternative:"Alternativa estrutural segura encontrada",
    remaining_within_max_height:"Trecho restante dentro do limite seguro"
  };
  return map[String(reason||"")]||String(reason||"Sem motivo registrado").replaceAll("_"," ");
}

function l3AnalysisSummary(d){
  d=d||{};
  let decisions={SAFE:0,UNSAFE:0,INCONCLUSIVE:0};
  let reasons={};
  let diagnostics=Array.isArray(d.diagnostics)?d.diagnostics:[];
  let add=(obj,key,val)=>{let n=Number(val||0);if(Number.isFinite(n)&&n>0)obj[key]=(obj[key]||0)+n;};
  diagnostics.forEach(it=>{
    let local=it?.local_search_metrics||it?.local_metrics||it||{};
    Object.entries(local.local_decision_counts||{}).forEach(([k,v])=>add(decisions,String(k).toUpperCase(),v));
    Object.entries(local.local_reason_counts||{}).forEach(([k,v])=>add(reasons,String(k),v));
  });
  let evaluated=Object.values(decisions).reduce((a,b)=>a+Number(b||0),0);
  let topReasons=Object.entries(reasons).sort((a,b)=>Number(b[1])-Number(a[1]));
  let residual=Array.isArray(d.residual_pending_segments)?d.residual_pending_segments:[];
  let finalReasons=[...new Set(residual.map(s=>s?.reason).filter(Boolean))];
  let triggerReasons=[...new Set(residual.map(s=>s?.trigger_reason).filter(Boolean))];
  return {decisions,reasons,evaluated,topReasons,finalReasons,triggerReasons};
}

function mergeLevel3(r){
  let list=data.chapters.filter(x=>x.merge_level3_pending||x.merge_level3_detail?.available);
  let filtered=list.filter(x=>!window._tableQuery||String(x.chapter).toLowerCase().includes(String(window._tableQuery).toLowerCase()));
  if(tableStatus==="pending")filtered=filtered.filter(x=>!!x.merge_level3_pending);
  if(tableStatus==="done")filtered=filtered.filter(x=>!x.merge_level3_pending&&x.merge_level3_detail?.available);
  if(!list.length){
    r.innerHTML=head("Auto-Merge Nível III","Executa análise estrutural OpenCV sobre os resíduos validados do Nível II.")+`<div class="empty">Nenhum capítulo aguardando ou com processamento do Auto-Merge Nível III.</div>`;
    return;
  }
  let pages=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE));
  tablePage=Math.min(tablePage,pages);
  let rows=filtered.slice((tablePage-1)*PAGE_SIZE,tablePage*PAGE_SIZE);
  let pager=`<div class="table-pager"><span>${filtered.length?((tablePage-1)*PAGE_SIZE+1):0}-${Math.min(tablePage*PAGE_SIZE,filtered.length)} de ${filtered.length}</span><div><button class="btn" ${tablePage<=1?"disabled":""} onclick="changeTablePage(-1)">&lt;&lt;</button><span class="page-indicator">${tablePage} / ${pages}</span><button class="btn" ${tablePage>=pages?"disabled":""} onclick="changeTablePage(1)">&gt;&gt;</button></div></div>`;
  let body=rows.map(x=>{
    let d=x.merge_level3_detail||{},pending=!!x.merge_level3_pending,safe=Number(d.safe_artifacts_count||(d.safe_artifacts||[]).length||0),res=Number(d.residual_pending_segments_count||(d.residual_pending_segments||[]).length||0);
    let state=pending?`<span class="warn">Pendente</span>`:(!d.valid?`<span class="bad">⚠ Inválido</span>`:`<span class="ok">✓ Analisado</span>`);
    let outcome=!d.valid?"":(res?(safe?"Parcialmente resolvido":"Não resolvido"):"Resolvido automaticamente");
    let result=pending?`<span class="muted">Aguardando análise estrutural</span>`:(!d.valid?esc(d.error||"Manifesto inválido"):res?`<span class="bad">${esc(outcome)}</span> · <button class="l3-result-link" onclick="reviewCh='${esc(x.chapter)}';page='review_v2';document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.page==='review_v2'));render()">Revisão Merge V2</button>`:(x.merge?`<span class="ok">${esc(outcome)}</span>`:`<span class="muted">Analisado sem residual</span>`));
    return `<tr data-n="${esc(String(x.chapter)).toLowerCase()}">
      <td>${pending?`<input class="ck" type="checkbox" value="${esc(x.chapter)}" onchange="syncVisibleMaster(document.querySelector('.visible-master'),'.ck')">`:""}</td>
      <td>${esc(x.chapter)}</td>
      <td>${state}</td>
      <td>${pending?"—":safe}</td>
      <td>${pending?"—":res}</td>
      <td>${result}</td>
      <td>${d.available?`<button class="btn l3-detail-btn" onclick="toggleLevel3Detail('${esc(x.chapter)}')">Detalhes</button>`:""}</td>
    </tr>
    ${d.available?`<tr class="l3-detail-row" id="l3-detail-${esc(x.chapter)}" hidden><td colspan="7">${level3DetailPanel(x)}</td></tr>`:""}`;
  }).join("");
  r.innerHTML=head("Auto-Merge Nível III","Executa análise estrutural OpenCV sobre os resíduos validados do Nível II.")+
    `<div class="toolbar standard-filterbar"><input id="q" class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;tablePage=1;render()"><div class="status-filter" role="group" aria-label="Filtrar Nível III"><button class="tab ${tableStatus==="all"?"active":""}" onclick="setTableStatus('all')">Todos</button><button class="tab ${tableStatus==="pending"?"active":""}" onclick="setTableStatus('pending')">Pendentes</button><button class="tab ${tableStatus==="done"?"active":""}" onclick="setTableStatus('done')">Analisados</button></div><button class="btn primary filter-primary-action" onclick="runSelected('merge_level3')">Analisar Nível III</button></div>
     <div class="panel"><table class="l3-table"><thead><tr><th>${visibleMaster()}</th><th>CAP.</th><th>NÍVEL III</th><th>SAFE</th><th>RESIDUAL</th><th>RESULTADO</th><th></th></tr></thead><tbody>${body||`<tr><td colspan="7" class="muted">Nenhum capítulo encontrado.</td></tr>`}</tbody></table>${pager}</div>`;
}
function toggleLevel3Detail(ch){
  let row=document.getElementById(`l3-detail-${ch}`);
  if(row)row.hidden=!row.hidden;
}
function level3DetailPanel(x){
  let d=x.merge_level3_detail||{},safe=d.safe_artifacts||[],residual=d.residual_pending_segments||[],diagnostics=d.diagnostics||[];
  let stats=l3AnalysisSummary(d);
  let interval=seg=>{if(!seg)return "—";let a=Number(seg.start??seg.global_start??0),b=Number(seg.end??seg.global_end??0);return `${a.toLocaleString("pt-BR")} → ${b.toLocaleString("pt-BR")} px`;};
  let segs=[...safe.map((s,n)=>`<div class="l3-mini-seg safe"><span>SAFE ${n+1}</span><b>${esc(interval(s))}</b></div>`),...residual.map((s,n)=>`<div class="l3-mini-seg residual"><span>Residual ${n+1}</span><b>${esc(interval(s))}</b></div>`)].join("");
  let reasons=stats.topReasons.slice(0,6).map(([raw,count])=>`<div class="l3-mini-seg residual"><span>${Number(count).toLocaleString("pt-BR")} ocorrência(s)</span><b>${esc(l3ReasonLabel(raw))}</b></div>`).join("");
  let finalReason=stats.finalReasons.length?stats.finalReasons.map(l3ReasonLabel).join(" · "):(stats.triggerReasons.length?stats.triggerReasons.map(l3ReasonLabel).join(" · "):"Nenhum motivo final registrado.");
  let conclusion=residual.length?(safe.length?`O Nível III resolveu ${safe.length} região(ões), mas ${residual.length} região(ões) permaneceram sem um corte comprovadamente seguro.`:`O Nível III executou a análise, mas não conseguiu comprovar um corte seguro para ${residual.length} região(ões).`):`O Nível III não deixou região residual pendente.`;
  let diags=diagnostics.map((it,n)=>{let trigger=it.trigger_reason||it.reason||it.level3_reason||"";return `<details class="l3-inline-diag"><summary>Diagnóstico técnico ${n+1} · ${esc(l3ReasonLabel(trigger))}</summary><pre>${esc(JSON.stringify(it,null,2))}</pre></details>`;}).join("");
  return `<div class="l3-detail-panel">
    <div class="l3-detail-summary"><div><span>RESULTADO</span><b>${residual.length?(safe.length?"Parcialmente resolvido":"Não resolvido"):"Resolvido"}</b></div><div><span>SAFE</span><b>${safe.length}</b></div><div><span>RESIDUAIS</span><b>${residual.length}</b></div><div><span>ALTURA TOTAL</span><b>${Number(d.total_height||0).toLocaleString("pt-BR")} px</b></div></div>
    <div class="l3-detail-summary"><div><span>CANDIDATOS AVALIADOS</span><b>${stats.evaluated?stats.evaluated.toLocaleString("pt-BR"):"—"}</b></div><div><span>SAFE</span><b>${Number(stats.decisions.SAFE||0).toLocaleString("pt-BR")}</b></div><div><span>UNSAFE</span><b>${Number(stats.decisions.UNSAFE||0).toLocaleString("pt-BR")}</b></div><div><span>INCONCLUSIVE</span><b>${Number(stats.decisions.INCONCLUSIVE||0).toLocaleString("pt-BR")}</b></div></div>
    <div class="l3-detail-segments">${segs||`<span class="muted">Nenhum segmento persistido.</span>`}</div>
    <div class="l3-detail-diags"><strong>Conclusão da análise</strong><p>${esc(conclusion)}</p>${residual.length?`<p><b>Motivo final:</b> ${esc(finalReason)}</p>`:""}</div>
    ${reasons?`<div class="l3-detail-diags"><strong>Principais motivos encontrados na busca local</strong>${reasons}</div>`:""}
    <div class="l3-detail-diags">${diags||`<span class="muted">Nenhum diagnóstico técnico persistido.</span>`}</div>
  </div>`;
}

function reviewFilterBar(){
  return `<div class="toolbar standard-filterbar review-standard-filterbar"><input class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;render()"><div class="status-filter" role="group" aria-label="Filtrar revisão"><button class="tab ${tableStatus==="all"?"active":""}" onclick="setTableStatus('all')">Todos</button><button class="tab ${tableStatus==="pending"?"active":""}" onclick="setTableStatus('pending')">Pendentes</button><button class="tab ${tableStatus==="reviewing"?"active":""}" onclick="setTableStatus('reviewing')">Em revisão</button></div></div>`;
}
function visibleChecks(selector=".ck"){
  return [...document.querySelectorAll(selector)].filter(x=>!x.disabled&&x.offsetParent!==null);
}
function toggleVisibleChecks(master,selector=".ck"){
  visibleChecks(selector).forEach(x=>x.checked=master.checked);
  syncVisibleMaster(master,selector);
}
function syncVisibleMaster(master,selector=".ck"){
  if(!master)return;
  let items=visibleChecks(selector),checked=items.filter(x=>x.checked).length;
  master.checked=!!items.length&&checked===items.length;
  master.indeterminate=checked>0&&checked<items.length;
}
function visibleMaster(selector=".ck",cls="visible-master"){
  return `<input class="${cls}" type="checkbox" aria-label="Selecionar itens visíveis" title="Selecionar itens visíveis" onclick="toggleVisibleChecks(this,'${selector}')">`;
}
function chosen(){return [...document.querySelectorAll(".ck:checked")].map(x=>x.value)}async function runSelected(a){let ch=chosen();if(!ch.length)return toast("Selecione ao menos um capítulo.");if(await askAppModal("Confirmar",`${ch.length} capítulo(s) selecionado(s).`,"Executar"))job(a,ch)}function goReview(ch){page="review";reviewCh=ch;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.page==="review"));render()}function goLevel2(ch){page="merge_level2";reviewCh=ch;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.page==="merge_level2"));render()}function review(r){
 let baseList=data.chapters.filter(x=>x.merge_state==="pendente_review"||x.review);
 let q=String(window._tableQuery||"").trim().toLowerCase();
 let list=baseList.filter(x=>String(x.chapter).toLowerCase().includes(q));
 if(tableStatus==="pending")list=list.filter(x=>!x.review);
 if(tableStatus==="reviewing")list=list.filter(x=>!!x.review);
 if(!list.length){r.innerHTML=head("Revisão Merge pendentes","Revise propostas alternativas antes de torná-las oficiais.")+reviewFilterBar()+`<div class="empty">Nenhum capítulo encontrado para o filtro atual.</div>`;return}
 let x=list.find(z=>String(z.chapter)===String(reviewCh))||list[0];
 reviewCh=x.chapter;
 if(window.reviewExpandedChapter===undefined)window.reviewExpandedChapter=x.chapter;
 let merges=x.review_merges||[],files=x.review_files||[];
 let proposedLimit=Number(x.review_max_source_images||window.reviewMaxSources||8);
 if(!Number.isFinite(proposedLimit)||proposedLimit<2)proposedLimit=8;
 window.reviewMaxSources=proposedLimit;
 let i=Math.min(Math.max(0,Number.isFinite(Number(window.reviewImageIndex))?Number(window.reviewImageIndex):0),Math.max(0,files.length-1));
 window.reviewImageIndex=i;if(!Number.isFinite(Number(window.reviewZoom)))window.reviewZoom=1;
 let current=merges[i]||{file:files[i]||"",index:i+1,sources:[]};
 let reviewUrl=f=>`/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=review&chapter=${encodeURIComponent(x.chapter)}&file=${encodeURIComponent(f)}`;
 let sourceUrl=f=>`/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=source&chapter=${encodeURIComponent(x.chapter)}&file=${encodeURIComponent(f)}`;
 let analysisSources=(current.analysis_sources&&current.analysis_sources.length)
   ? current.analysis_sources
   : (current.sources||[]).map((f,n)=>({file:f,included:true,source_index:n}));
 let firstContext=analysisSources.findIndex(src=>!src.included);
 let sourceThumbs=analysisSources.map((src,n)=>{
   let separator=(n===firstContext&&firstContext>=0)?`<div class="rv-thumb-cut"><span>CORTE</span></div>`:"";
   let state=src.included?"included":"context";
   return `${separator}<button class="rv-source ${state}" title="${esc(src.file)}" onclick="rvOpenSourcePreview('${sourceUrl(src.file)}','${esc(src.file)}',${src.included?'true':'false'})"><img src="${sourceUrl(src.file)}" alt="${esc(src.file)}" onerror="this.hidden=true;this.nextElementSibling.classList.add('show')"><span class="rv-source-err">!</span><small>${esc(src.file)}</small><em>${src.included?"ENTRA":"CONTEXTO"}</em></button>`;
 }).join("");
 let contextSources=analysisSources.filter(src=>!src.included);
 let contextPreview=contextSources.map(src=>`<div class="rv-context-piece" data-source-file="${esc(src.file)}"><div class="rv-context-name">${esc(src.file)} · fora deste merge</div><img class="rv-context-image" src="${sourceUrl(src.file)}" alt="${esc(src.file)}" onload="rvSyncSourceLabel()"></div>`).join("");
 let chapters=list.map(z=>{
   let open=String(z.chapter)===String(window.reviewExpandedChapter);
   let items=z.review_merges||[],count=items.length||z.review_images||0;
   let mergeButtons=items.map((m,n)=>`<button class="rv-merge-link ${String(z.chapter)===String(x.chapter)&&n===i?"active":""}" title="${esc(m.file||"")}" onclick="rvSelectMerge('${esc(z.chapter)}',${n})">${esc(segLabel(m))}</button>`).join("");
   return `<div class="rv-chapter-group ${open?"open":""}">
     <button class="rv-chapter-head" onclick="rvToggleChapter('${esc(z.chapter)}')"><span class="rv-chevron">${open?"▼":"▶"}</span><span><b>${esc(z.chapter)}</b><small>${count?count+" trecho(s) para revisar":"proposta ainda não gerada"}</small></span></button>
     ${open?`<div class="rv-merge-list">${mergeButtons||`<button class="rv-generate-inline" onclick="event.stopPropagation();reviewDecision('review','${esc(z.chapter)}')">Gerar proposta</button>`}</div>`:""}
   </div>`;
 }).join("");

 r.innerHTML=`<section class="rv">
 <header class="rv-head"><div><h1>Revisão Merge</h1></div></header>
  ${reviewFilterBar()}
 ${x.review?`
 <section class="rv-source-strip">
   <div class="rv-source-strip-head">
     <div><span class="eyebrow">IMAGENS DA PROPOSTA</span><b>${current.file||"merge"}</b></div>
     <span>${analysisSources.length} imagem(ns) analisada(s) · ${(current.sources||[]).length} entram no merge</span>
   </div>
   <div class="rv-source-thumbs">${sourceThumbs||`<div class="rv-source-empty">Mapeamento das imagens de origem indisponível.</div>`}</div>
 </section>
 <div class="rv-layout">
   <main class="rv-view"><div class="rv-canvas">
     
     <div class="rv-current-source-bar"><b id="rvSourceName">—</b></div><div class="rv-stage" id="rvStage" onscroll="rvSyncSourceLabel()"><div id="rvPreviewStack" class="rv-preview-stack" style="transform:scale(${window.reviewZoom||1})">${current.file?`<img id="rvMain" class="rv-merged-image" src="${reviewUrl(current.file)}" onload="rvSyncSourceLabel()" onerror="this.hidden=true;document.querySelector('#rvMainErr').classList.add('show')">`:""}<div id="rvMainErr" class="rv-mainerr ${current.file?"":"show"}">Falha ao carregar esta imagem</div>${contextSources.length?`<div class="rv-cut-marker"><span>FIM SUGERIDO DO MERGE</span><small>corte seguro encontrado aqui</small></div><div class="rv-context-zone">${contextPreview}<div class="rv-context-note">FORA DESTE MERGE<br><small>permanece para o próximo merge</small></div></div>`:""}</div></div>
     
     <span class="rv-count">${files.length?i+1:0} / ${files.length}</span>
     <div class="rv-zoom"><button onclick="rvZoom(-.10)">−</button><b id="rvPct">${Math.round((window.reviewZoom||1)*100)}%</b><button onclick="rvZoom(.10)">+</button><button class="rv-fit" onclick="rvFitWidth()">Ajustar à largura</button></div>
   </div></main>
   <aside class="rv-side">
     <section class="rv-control-panel rv-config-technical">
       <div class="rv-config-title"><span class="eyebrow">CONFIGURAÇÃO DA PROPOSTA</span><span class="rv-review-badge">Review</span></div>
       <div class="rv-config-row">
         <div class="rv-config-copy"><strong>Máximo de originais</strong><span>Limite usado ao regenerar a proposta</span></div>
         <div class="rv-stepper">
           <button type="button" onclick="rvChangeMaxSources(-1)" aria-label="Diminuir máximo">−</button>
           <div id="reviewMaxSourcesValue" class="rv-stepper-value">${proposedLimit}</div>
           <button type="button" onclick="rvChangeMaxSources(1)" aria-label="Aumentar máximo">+</button>
         </div>
         <input id="reviewMaxSources" type="hidden" value="${proposedLimit}">
       </div>
       <div class="rv-config-separator"></div>
       <div class="rv-actions rv-actions-pair">${x.review?`<button class="btn danger" onclick="reviewDecision('reject','${esc(x.chapter)}')">Rejeitar</button><button class="btn" onclick="reviewDecision('review','${esc(x.chapter)}')">Regenerar</button><button class="btn primary rv-approve-wide" onclick="reviewDecision('approve','${esc(x.chapter)}')">Aprovar merge</button>`:`<button class="btn primary rv-approve-wide" onclick="reviewDecision('review','${esc(x.chapter)}')">Gerar merge proposto</button>`}</div>
     </section>
     <section><span class="eyebrow">PRÓXIMOS PENDENTES</span><div class="rv-chapters">${chapters}</div></section>
   </aside>
 </div>`:`<div class="rv-empty rv-pending-empty">
    <h2>Capítulo ${esc(x.chapter)}</h2>
    <p>${reviewPendingSummary(x)}</p>
    <div class="rv-pending-config">
      <div class="rv-config-copy"><strong>Máximo de originais</strong><span>Limite usado para gerar a proposta</span></div>
      <div class="rv-stepper">
        <button type="button" onclick="rvChangeMaxSources(-1)" aria-label="Diminuir máximo">−</button>
        <div id="reviewMaxSourcesValue" class="rv-stepper-value">${proposedLimit}</div>
        <button type="button" onclick="rvChangeMaxSources(1)" aria-label="Aumentar máximo">+</button>
      </div>
      <input id="reviewMaxSources" type="hidden" value="${proposedLimit}">
    </div>
    <button class="btn primary rv-generate-pending" onclick="reviewDecision('review','${esc(x.chapter)}')">Gerar proposta</button>
    <aside class="rv-pending-list-empty">
      <span class="eyebrow">PENDENTES DE REVISÃO</span>
      <div class="rv-pending-caps">
        ${data.chapters.filter(c=>c.merge_state==="pendente_review"||c.review).map(c=>`
          <button class="rv-pending-cap ${String(c.chapter)===String(x.chapter)?"active":""}"
                  onclick="reviewCh='${esc(c.chapter)}';window.reviewImageIndex=0;render()">
            <span>Capítulo ${esc(c.chapter)}</span><b>›</b>
          </button>`).join("")}
      </div>
    </aside>
  </div>`}</section>`;
}

function rv2Num(v){let n=Number(v);return Number.isFinite(n)?n.toLocaleString("pt-BR"):"—"}
function rv2Interval(seg){if(!seg)return "—";let a=Number(seg.start??seg.global_start??seg.y_start),b=Number(seg.end??seg.global_end??seg.y_end);return Number.isFinite(a)&&Number.isFinite(b)?`${rv2Num(a)}–${rv2Num(b)} px`:"—"}
function rv2Intervals(items){return (items||[]).map(rv2Interval).join(" · ")||"—"}
function rv2Sources(seg){let a=seg?.sources||seg?.source_files||seg?.source_spans||[];return Array.isArray(a)?a:[]}
function rv2ReasonLabel(reason){let labels={connected_component_crossing:"Objeto atravessando o corte",strong_diagonal_crossing:"Borda diagonal forte",high_edge_density:"Alta densidade de bordas",closed_contour_crossing:"Contorno atravessando o corte",text_fx_near_cut:"Provável texto/onomatopeia",possible_text_fx:"Provável texto/onomatopeia",continuous_scene_too_long:"Cena contínua muito longa",structurally_clear:"Estruturalmente seguro",safe_local_alternative:"Alternativa segura encontrada",remaining_within_max_height:"Trecho restante dentro do limite"};return labels[String(reason||"")]||String(reason||"Diagnóstico estrutural")}
function rv2Json(v){try{return esc(JSON.stringify(v,null,2))}catch(_){return esc(String(v??""))}}
function rv2Diagnostics(detail){let ds=detail?.diagnostics||[],res=detail?.residual_pending_segments||[];let last=ds.length?ds[ds.length-1]:{};let rr=res.length?res[res.length-1]:{};let reason=rr.reason||last.reason||last.final_reason||"";let trigger=rr.trigger_reason||last.trigger_reason||"";let decision=rr.trigger_decision||last.trigger_decision||last.level3_decision||last.decision||"";let guard=rr.guard_metrics||last.guard_metrics||{};let local=last.local_search_metrics||last.local_metrics||last;return {reason,trigger,decision,guard,local,raw:ds}}
function rv2CurrentChapter(){return data?.chapters?.find(z=>String(z.chapter)===String(reviewCh))||null}
function rv2SelectChapter(c){reviewCh=c;window.reviewImageIndex=0;window.reviewZoom=1;render()}
function rv2SelectMerge(i){window.reviewImageIndex=i;window.reviewZoom=1;render()}
function reviewV2(r){
  let baseList=data.chapters.filter(x=>x.merge_state==="pendente_review"&&x.merge_level3_detail?.available&&x.merge_level3_detail?.valid&&(x.merge_level3_detail.residual_pending_segments_count||0)>0);
  let q=String(window._tableQuery||"").trim().toLowerCase();
  let list=baseList.filter(x=>String(x.chapter).toLowerCase().includes(q));
  if(tableStatus==="pending")list=list.filter(x=>!x.review);
  if(tableStatus==="reviewing")list=list.filter(x=>!!x.review);
  if(!list.length){r.innerHTML=head("Revisão Merge V2","Review assistido pelos diagnósticos estruturais do Auto-Merge Nível III.")+reviewFilterBar()+`<div class="empty">Nenhum capítulo encontrado para o filtro atual.</div>`;return}
  let x=list.find(z=>String(z.chapter)===String(reviewCh))||list[0];reviewCh=x.chapter;
  let d=x.merge_level3_detail||{},l2=(x.merge_partition?.pending_segments||[]),res=d.review_pending_segments||d.residual_pending_segments||[];
  let merges=x.review_merges||[],files=x.review_files||[];
  let idx=Math.min(Math.max(0,Number(window.reviewImageIndex)||0),Math.max(0,merges.length-1));window.reviewImageIndex=idx;
  let current=merges[idx]||null,diag=rv2Diagnostics(d);
  let proposedLimit=Number(x.review_max_source_images||window.reviewMaxSources||8);if(!Number.isFinite(proposedLimit)||proposedLimit<2)proposedLimit=8;window.reviewMaxSources=proposedLimit;
  let reviewUrl=f=>`/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=review&chapter=${encodeURIComponent(x.chapter)}&file=${encodeURIComponent(f)}`;
  let sourceUrl=f=>`/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=source&chapter=${encodeURIComponent(x.chapter)}&file=${encodeURIComponent(f)}`;
  let originalSources=[];for(let s of res){for(let src of rv2Sources(s)){let f=typeof src==="string"?src:(src.file||src.source||src.name||"");if(f&&!originalSources.includes(f))originalSources.push(f)}}
  if(!originalSources.length&&current){for(let src of (current.analysis_sources||current.sources||[])){let f=typeof src==="string"?src:(src.file||"");if(f&&!originalSources.includes(f))originalSources.push(f)}}
  let originalStack=originalSources.map(f=>`<div class="rv2-source-piece"><div>${esc(f)}</div><img src="${sourceUrl(f)}" alt="${esc(f)}"></div>`).join("")||`<div class="rv2-placeholder">Originais mapeados indisponíveis.</div>`;
  let proposalStack=merges.map((m,n)=>`<button class="rv2-proposal-piece ${n===idx?"active":""}" onclick="rv2SelectMerge(${n})"><span>${esc(m.file||`Saída ${n+1}`)}</span>${m.file?`<img src="${reviewUrl(m.file)}" alt="${esc(m.file)}">`:""}</button>`).join("")||`<div class="rv2-placeholder">A proposta ainda não foi gerada.</div>`;
  let sourceCount=originalSources.length;let cuts=Math.max(0,merges.length-1);
  let queue=list.map(z=>`<button class="rv2-queue-item ${String(z.chapter)===String(x.chapter)?"active":""}" onclick="rv2SelectChapter('${esc(z.chapter)}')"><b>Capítulo ${esc(z.chapter)}</b><span>${z.review?`${z.review_images||0} saída(s) proposta(s)`:"Proposta ainda não gerada"}</span></button>`).join("");
  let tech={algorithm:d.algorithm,total_height:d.total_height,level2_pending:l2,level3_residual:res,final_reason:diag.reason,trigger_reason:diag.trigger,trigger_decision:diag.decision,guard_metrics:diag.guard,local_decision_counts:diag.local?.local_decision_counts,local_reason_counts:diag.local?.local_reason_counts,local_metric_ranges:diag.local?.local_metric_ranges,safety:d.safety};
  r.innerHTML=`<section class="rv2"><header class="rv2-head"><div><span class="eyebrow">AUTO-MERGE NÍVEL III</span><h1>Revisão Merge V2</h1><p>Compare o residual estrutural com a proposta antes da composição final.</p></div><span class="rv2-status">Requer decisão</span></header>
  ${reviewFilterBar()}
  <div class="rv2-flow"><div class="rv2-node done"><i></i><span>Auto-Merge I</span></div><div class="rv2-node done"><i></i><span>Nível II</span></div><div class="rv2-node done"><i></i><span>Nível III</span></div><div class="rv2-node current"><i></i><span>Revisão Merge</span></div><div class="rv2-node"><i></i><span>Composição final</span></div></div>
  <div class="rv2-layout"><main class="rv2-main"><div class="rv2-summary"><div><b>Capítulo ${esc(x.chapter)}</b><span>Somente o residual não comprovado como seguro pelo Nível III.</span></div><div class="rv2-kpis"><div><b>${sourceCount}</b><span>originais</span></div><div><b>${merges.length}</b><span>saídas</span></div><div><b>${cuts}</b><span>cortes</span></div></div></div>
  <div class="rv2-compare"><section class="rv2-preview"><header><b>Região original pendente</b><span>${esc(rv2Intervals(res))}</span></header><div class="rv2-scroll">${originalStack}</div></section><section class="rv2-preview"><header><b>Proposta Review</b><span>${merges.length?`${merges.length} saída(s)`:"não gerada"}</span></header><div class="rv2-scroll">${proposalStack}</div></section></div></main>
  <aside class="rv2-side"><section class="rv2-card"><span class="eyebrow">TRECHO EM REVISÃO</span><h2>Capítulo ${esc(x.chapter)}</h2><div class="rv2-metric"><span>Pendente no Level II</span><b>${esc(rv2Intervals(l2))}</b></div><div class="rv2-metric"><span>Residual do Level III</span><b>${esc(rv2Intervals(res))}</b></div><div class="rv2-metric"><span>SAFE no Level III</span><b>${d.safe_artifacts_count||0}</b></div><div class="rv2-notice">Ao aprovar, o backend compõe a proposta somente com os segmentos já validados dos níveis anteriores.</div></section>
  <section class="rv2-card rv2-diagnosis"><span class="eyebrow">POR QUE CHEGOU AO REVIEW?</span><strong>${esc(rv2ReasonLabel(diag.reason))}</strong>${diag.trigger?`<p>Gatilho: ${esc(rv2ReasonLabel(diag.trigger))}${diag.decision?` · ${esc(diag.decision)}`:""}</p>`:""}<details><summary>Detalhes técnicos</summary><pre>${rv2Json(tech)}</pre></details></section>
  <section class="rv2-card"><div class="rv2-config"><span><b>Máximo de originais</b><small>Usado ao gerar/regenerar</small></span><div class="rv-stepper"><button onclick="rvChangeMaxSources(-1)">−</button><div id="reviewMaxSourcesValue" class="rv-stepper-value">${proposedLimit}</div><button onclick="rvChangeMaxSources(1)">+</button></div><input id="reviewMaxSources" type="hidden" value="${proposedLimit}"></div><div class="rv2-actions">${x.review?`<button class="btn danger" onclick="reviewDecision('reject','${esc(x.chapter)}')">Rejeitar</button><button class="btn" onclick="reviewDecision('review','${esc(x.chapter)}')">Regenerar</button><button class="btn primary" onclick="reviewDecision('approve','${esc(x.chapter)}')">Aprovar merge</button>`:`<button class="btn primary" onclick="reviewDecision('review','${esc(x.chapter)}')">Gerar proposta</button>`}</div></section>
  <section class="rv2-card"><span class="eyebrow">PRÓXIMOS PENDENTES</span><div class="rv2-queue">${queue}</div></section></aside></div></section>`;
}

function rvSet(i){window.reviewImageIndex=i;window.reviewZoom=1;render()}
function rvMove(d){let x=data.chapters.find(z=>String(z.chapter)===String(reviewCh)),n=x?.review_files?.length||0;window.reviewImageIndex=Math.min(Math.max(0,(window.reviewImageIndex||0)+d),Math.max(0,n-1));window.reviewZoom=1;render()}
function rvChapter(c){reviewCh=c;window.reviewExpandedChapter=c;window.reviewImageIndex=0;window.reviewZoom=1;render()}
function rvSelectMerge(c,i){reviewCh=c;window.reviewExpandedChapter=c;window.reviewImageIndex=i;window.reviewZoom=1;render()}
function rvToggleChapter(c){window.reviewExpandedChapter=String(window.reviewExpandedChapter)===String(c)?null:c;render()}
function rvOpenSourcePreview(url,file,included){
  let old=$("#rvSourceModal");if(old)old.remove();
  window.rvModalZoomLevel=1;
  let modal=document.createElement("div");
  modal.id="rvSourceModal";modal.className="rv-source-modal";
  modal.innerHTML=`<div class="rv-source-modal-card">
    <header>
      <div><b>${file}</b><span>${included?"Compõe o merge":"Contexto · fora deste merge"}</span></div>
      <button onclick="document.querySelector('#rvSourceModal')?.remove()">×</button>
    </header>
    <div class="rv-source-modal-body" id="rvSourceModalBody">
      <div class="rv-source-modal-stage" id="rvSourceModalStage">
        <img id="rvSourceModalImg" src="${url}" alt="${file}">
      </div>
    </div>
    <footer class="rv-source-modal-zoom">
      <button onclick="rvModalZoom(-.10)">−</button>
      <b id="rvModalPct">100%</b>
      <button onclick="rvModalZoom(.10)">+</button>
      <button class="rv-modal-fit" onclick="rvModalFit()">Ajustar</button>
    </footer>
  </div>`;
  modal.addEventListener("click",e=>{if(e.target===modal)modal.remove()});
  document.body.appendChild(modal);
}
function rvModalZoom(delta){
  let img=$("#rvSourceModalImg"),pct=$("#rvModalPct");
  if(!img)return;
  let z=Number(window.rvModalZoomLevel)||1;
  z=Math.min(3,Math.max(.1,z+delta));
  window.rvModalZoomLevel=z;
  img.style.transform=`scale(${z})`;
  if(pct)pct.textContent=Math.round(z*100)+"%";
}
function rvModalFit(){
  let body=$("#rvSourceModalBody"),img=$("#rvSourceModalImg"),pct=$("#rvModalPct");
  if(!body||!img||!img.naturalWidth)return;
  let z=Math.min(3,Math.max(.1,(body.clientWidth-32)/img.naturalWidth));
  window.rvModalZoomLevel=z;
  img.style.transform=`scale(${z})`;
  if(pct)pct.textContent=Math.round(z*100)+"%";
}

function rvChangeMaxSources(delta){
  let input=$("#reviewMaxSources"),value=$("#reviewMaxSourcesValue");
  let current=parseInt(input?.value||window.reviewMaxSources||8,10);
  if(!Number.isFinite(current))current=8;
  current=Math.max(2,Math.min(50,current+delta));
  window.reviewMaxSources=current;
  if(input)input.value=current;
  if(value)value.textContent=current;
}

function rvCurrentMerge(){let x=data.chapters.find(z=>String(z.chapter)===String(reviewCh));let i=Math.max(0,Number(window.reviewImageIndex)||0);return x?.review_merges?.[i]||null}
function rvFitWidth(){let stage=$("#rvStage"),img=$("#rvMain"),stack=$("#rvPreviewStack");if(!stage||!img||!stack||!img.naturalWidth)return;let z=Math.min(3,Math.max(.1,Math.max(1,stage.clientWidth-24)/img.naturalWidth));window.reviewZoom=z;stack.style.transform=`scale(${z})`;let p=$("#rvPct");if(p)p.textContent=Math.round(z*100)+"%";setTimeout(rvSyncSourceLabel,0)}
function rvHighlightCurrentSource(span){
  const stage=$("#rvStage"), img=$("#rvMain");
  if(!stage||!img||!span)return;
  let band=$("#rvCurrentSourceBand");
  if(!band){
    band=document.createElement("div");
    band.id="rvCurrentSourceBand";
    band.className="rv-current-source-band";
    stage.insertBefore(band,stage.firstChild);
  }
  const naturalH=Number(img.naturalHeight||0);
  const renderedH=Number(img.getBoundingClientRect().height||0);
  if(!naturalH||!renderedH){band.style.display="none";return;}
  const scale=renderedH/naturalH;
  const start=Number(span.merge_start ?? 0);
  const end=Number(span.merge_end ?? start);
  band.style.top=`${img.offsetTop + start*scale}px`;
  band.style.height=`${Math.max(1,(end-start)*scale)}px`;
  band.style.display="block";
}

function rvSyncSourceLabel(){
  let stage=$("#rvStage"),img=$("#rvMain"),name=$("#rvSourceName"),merge=rvCurrentMerge();
  if(!stage||!img||!name||!merge)return;

  let center=stage.getBoundingClientRect().top+stage.clientHeight/2;
  let contextEls=[...stage.querySelectorAll(".rv-context-piece")];
  let contextHit=contextEls.find(el=>{
    let r=el.getBoundingClientRect();
    return center>=r.top&&center<r.bottom;
  });
  if(contextHit){
    let file=contextHit.dataset.sourceFile||"";
    name.textContent=file;
    return;
  }

  let spans=merge.source_spans||[];
  if(!spans.length){name.textContent="—";return}
  let z=Number(window.reviewZoom)||1;
  let visibleY=(stage.scrollTop+stage.clientHeight/2)/z;
  let idx=spans.findIndex(sp=>visibleY>=sp.merge_start&&visibleY<sp.merge_end);
  if(idx<0)idx=visibleY<spans[0].merge_start?0:spans.length-1;
  let sp=spans[idx];
  name.textContent=sp.file;
  rvHighlightCurrentSource(sp);
}
function rvZoom(d){let z=Number(window.reviewZoom);if(!Number.isFinite(z))z=1;window.reviewZoom=Math.min(3,Math.max(.1,z+d));let m=$("#rvPreviewStack"),p=$("#rvPct");if(m)m.style.transform=`scale(${window.reviewZoom})`;if(p)p.textContent=Math.round(window.reviewZoom*100)+"%";setTimeout(rvSyncSourceLabel,0)}
function openReviewImage(src,index=0){
  reviewViewerIndex=index;reviewViewerScale=1;
  let v=document.createElement("div");v.id="reviewViewer";v.className="review-viewer";
  v.innerHTML=`<div class="review-viewer-bar"><button class="btn" onclick="closeReviewImage()">Fechar</button><div class="review-viewer-tools"><button class="btn" onclick="reviewZoom(-.25)">-</button><span id="reviewZoomLabel">100%</span><button class="btn" onclick="reviewZoom(.25)">+</button><button class="btn" onclick="reviewFit()">Ajustar</button><button class="btn" onclick="reviewPrev()">&lt;&lt;</button><button class="btn" onclick="reviewNext()">&gt;&gt;</button></div></div><div class="review-viewer-stage" onclick="if(event.target===this)closeReviewImage()"><img id="reviewViewerImg" src="${src}" ondblclick="reviewReset()"></div>`;
  document.body.appendChild(v);document.addEventListener("keydown",reviewViewerKey);
}
function closeReviewImage(){document.querySelector("#reviewViewer")?.remove();document.removeEventListener("keydown",reviewViewerKey)}
function reviewApply(){let im=$("#reviewViewerImg");if(!im)return;im.style.transform=`scale(${reviewViewerScale})`;$("#reviewZoomLabel").textContent=Math.round(reviewViewerScale*100)+"%"}
function reviewZoom(d){reviewViewerScale=Math.min(4,Math.max(.25,reviewViewerScale+d));reviewApply()}
function reviewReset(){reviewViewerScale=1;reviewApply()}
function reviewFit(){reviewViewerScale=.6;reviewApply()}
function reviewShow(i){let a=reviewViewerImages();if(!a.length)return;reviewViewerIndex=(i+a.length)%a.length;$("#reviewViewerImg").src=a[reviewViewerIndex];reviewReset()}
function reviewPrev(){reviewShow(reviewViewerIndex-1)}
function reviewNext(){reviewShow(reviewViewerIndex+1)}
function reviewViewerKey(e){if(e.key==="Escape")closeReviewImage();else if(e.key==="ArrowLeft")reviewPrev();else if(e.key==="ArrowRight")reviewNext();else if(e.key==="+")reviewZoom(.25);else if(e.key==="-")reviewZoom(-.25)}
async function reviewDecision(kind,ch){
  reviewCh=ch;
  if(kind==="approve"){
    if(!(await askAppModal("Aprovar merge","Você validou visualmente a proposta?","Aprovar")))return;
    return job("review_approve",[ch]);
  }
  if(kind==="reject"){
    if(!(await askAppModal("Rejeitar proposta","Remover somente MERGE_REVIEW?","Remover")))return;
    return job("review_reject",[ch]);
  }
  let input=$("#reviewMaxSources");
  let maxSources=Math.max(2,Math.min(50,parseInt(input?.value||window.reviewMaxSources||8,10)));
  window.reviewMaxSources=maxSources;
  return job("review_generate",[ch],{max_source_images:maxSources});
}
async function ract(a){if(a==="review_approve")return reviewDecision("approve",reviewCh);if(a==="review_reject")return reviewDecision("reject",reviewCh);if(a==="review_generate")return reviewDecision("review",reviewCh);return job(a,[reviewCh])}
const JOB_LABELS={
  merge:"Auto-Merge",
  pdf:"Gerar PDF",
  pdf_merge:"PDF do Merge",
  clean:"Texto Off — Original",
  clean_merged:"Texto Off — Merged",
  merge_level2:"Auto-Merge Nível II",
  merge_level3:"Auto-Merge Nível III",
  dimension_analyze:"Validar imagens",
  dimension_correct:"Efetuar correção",
  review_generate:"Gerar proposta de revisão",
  review_approve:"Aprovar revisão",
  review_reject:"Rejeitar revisão"
};
function beginJobProgress(action,total){
  const b=$("#job");
  const expected=Math.max(0,Number(total)||0);
  b.hidden=false;
  b.dataset.action=action||"";
  $("#jobtitle").textContent=JOB_LABELS[action]||"Processando";
  $("#jobcount").textContent=expected?`0 de ${expected} concluído(s) · 0%`:"Preparando...";
  $("#jobmsg").textContent=expected?`Aguardando início do processamento de ${expected} capítulo(s)...`:"Preparando processamento...";
  const p=$("#progress");
  p.max=Math.max(1,expected||1);
  p.value=0;
  p.setAttribute("aria-valuemin","0");
  p.setAttribute("aria-valuemax",String(Math.max(1,expected||1)));
  p.setAttribute("aria-valuenow","0");
}
async function job(a,ch,extra={}){
  const chapters=Array.isArray(ch)?ch:[];
  beginJobProgress(a,chapters.length);
  try{
    let j=await api("/api/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:a,provider:data.provider,manga:data.manga,chapters:chapters,...extra})});
    poll(j.job_id,a,chapters.length);
  }catch(e){
    $("#job").hidden=true;
    throw e;
  }
}
function jobSummary(j){
  let results=Array.isArray(j.result)?j.result:[];
  let ok=results.filter(x=>["ok","success","done","skipped"].includes(String(x.status||"").toLowerCase()));
  let errors=results.filter(x=>String(x.status||"").toLowerCase()==="error");
  let other=results.filter(x=>!ok.includes(x)&&!errors.includes(x));

  if(j.status==="error" && !errors.length){
    return {kind:"error",title:"Processamento interrompido",ok:0,errors:1,other:0,details:[j.error||"Falha no processamento."],results};
  }

  let kind=errors.length?(ok.length||other.length?"partial":"error"):"success";
  let title=kind==="success"?"Processamento concluído":kind==="partial"?"Processamento concluído com ressalvas":"Processamento finalizado com erros";
  let details=errors.map(x=>`Cap. ${x.chapter}: ${x.message||"Erro sem detalhe."}`);

  return {kind,title,ok:ok.length,errors:errors.length,other:other.length,details,results};
}

async function openMergeFolder(chapter){
  try{
    await api(`/api/open-folder?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(chapter)}`);
  }catch(e){
    toast(e.message||"Não foi possível abrir a pasta.");
  }
}

async function openAutoMergeFolder(chapter){
  try{
    await api(`/api/open-folder?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(chapter)}&kind=auto_merge`);
  }catch(e){
    toast(e.message||"Não foi possível abrir a pasta do Auto-Merge.");
  }
}
function pdfMergeFileNames(payload){
  const raw=payload?.pdf_merge_files ?? payload?.files ?? payload?.outputs ?? [];
  const list=Array.isArray(raw)?raw:[];
  return list.map(item=>{
    if(typeof item==="string") return item.split("/").pop();
    const value=item?.file ?? item?.name ?? item?.path ?? "";
    return String(value).split("/").pop();
  }).filter(Boolean);
}

async function fetchPdfMergeFiles(chapter){
  try{
    const r=await api(`/api/pdf-merge-files?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(chapter)}`);
    return Array.isArray(r?.files)?r.files:[];
  }catch(e){return [];}
}

async function openPdfMergeFolder(chapter){
  try{
    await api(`/api/open-folder?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(chapter)}&kind=pdf_merge`);
  }catch(e){
    toast(e.message||"Não foi possível abrir a pasta.");
  }
}

function pdfMergeResultModal(job,state){
  const action=String(job?.action||job?.request?.action||"").toLowerCase();
  if(!["pdf_merge","generate_pdf_merge","pdfmerge"].includes(action)) return false;
  const status=String(job?.status||"").toLowerCase();
  if(!["done","success","completed","error","failed"].includes(status)) return false;
  const payload=job?.result ?? job?.response ?? job;
  const rawItems=Array.isArray(payload)?payload:(Array.isArray(payload?.items)?payload.items:[payload]);
  const items=rawItems.filter(Boolean).map((raw,index)=>{
    const rawStatus=String(raw?.status||"").toLowerCase();
    const isError=["error","failed"].includes(rawStatus);
    const isSkipped=["skip","skipped"].includes(rawStatus);
    const path=String(raw?.path||"");
    const file=path?path.split("/").pop():"";
    return {...raw,_index:index,_error:isError,_statusLabel:isError?"Requer atenção":isSkipped?"Já existente":"Concluído",_file:file,_pdfCount:isError?0:1};
  });
  if(!items.length) return false;
  const concluded=items.filter(x=>!x._error).length;
  const errors=items.filter(x=>x._error).length;
  const chapterWord=items.length===1?"capítulo processado":"capítulos processados";
  const resultParts=[];
  if(concluded) resultParts.push(`${concluded} ${concluded===1?"concluído":"concluídos"}`);
  if(errors) resultParts.push(`${errors} ${errors===1?"pendente":"pendentes"}`);
  document.querySelector("#appModal")?.remove();
  let overlay=document.createElement("div");
  overlay.id="appModal"; overlay.className="app-modal-overlay";
  const chapterHtml=items.map(item=>`
    <section class="merge-chapter-item" data-pdf-chapter="${item._index}">
      <button class="merge-chapter-head" type="button" data-pdf-chapter-toggle="${item._index}" aria-expanded="false">
        <span class="merge-chapter-name">Cap. ${esc(item.chapter||"—")}</span>
        <strong class="merge-chapter-status ${item._error?"warning":""}">${esc(item._statusLabel)}</strong>
        <span class="merge-chapter-count">${item._pdfCount} ${item._pdfCount===1?"PDF":"PDFs"}</span>
        <span class="merge-chapter-chevron" aria-hidden="true">⌄</span>
      </button>
      <div class="merge-chapter-body" data-pdf-chapter-panel="${item._index}" hidden>
        <div class="merge-summary-row"><span class="merge-summary-label">Status</span><strong class="merge-summary-value ${item._error?"warning":""}">${esc(item._statusLabel)}</strong><span class="merge-summary-toggle-spacer"></span></div>
        <div class="merge-summary-row"><span class="merge-summary-label">${item._error?"Motivo":"PDF gerado"}</span><strong class="merge-summary-value">${esc(item._error?(item.message||"Falha na geração do PDF"):(item._file||`${item.chapter}.pdf`))}</strong><span class="merge-summary-toggle-spacer"></span></div>
        <div class="merge-chapter-actions">${item._error?"":`<button class="btn" type="button" data-open-pdf-folder="${item._index}">Abrir pasta</button>`}</div>
      </div>
    </section>`).join("");
  overlay.innerHTML=`<div class="app-modal merge-summary-modal" role="dialog" aria-modal="true" aria-label="Resumo da Operação">
    <div class="app-modal-head merge-summary-head"><div><div class="caption">PROCESSAMENTO</div><h2>Resumo da Operação</h2></div><button class="app-modal-x" aria-label="Fechar">&times;</button></div>
    <div class="merge-batch-summary"><strong>${items.length} ${chapterWord}</strong>${resultParts.length?`<span>${esc(resultParts.join(" · "))}</span>`:""}</div>
    <div class="merge-chapter-list">${chapterHtml}</div>
    <div class="app-modal-actions merge-summary-actions"><button class="btn primary" type="button" data-pdf-summary-close>Fechar</button></div>
  </div>`;
  const close=()=>{closeAppModal(false);};
  overlay.querySelector(".app-modal-x").onclick=close;
  overlay.querySelector("[data-pdf-summary-close]").onclick=close;
  overlay.onclick=e=>{if(e.target===overlay)close();};
  overlay.querySelectorAll("[data-pdf-chapter-toggle]").forEach(btn=>{btn.onclick=()=>{const key=btn.dataset.pdfChapterToggle;const panel=overlay.querySelector(`[data-pdf-chapter-panel="${key}"]`);const item=overlay.querySelector(`[data-pdf-chapter="${key}"]`);if(!panel||!item)return;const open=panel.hidden;panel.hidden=!open;item.classList.toggle("open",open);btn.setAttribute("aria-expanded",String(open));};});
  overlay.querySelectorAll("[data-open-pdf-folder]").forEach(btn=>{btn.onclick=async e=>{e.stopPropagation();const item=items[Number(btn.dataset.openPdfFolder)];if(!item)return;await openPdfMergeFolder(String(item.chapter||""));};});
  document.body.appendChild(overlay);
  document.addEventListener("keydown",appModalKey);
  return true;
}

async function formatReviewDiagnosticMessage(message){
  const text=String(message||"");
  if(!text.includes("Diagnóstico dos fins naturais:")) return text;
  const parts=text.split("Diagnóstico dos fins naturais:");
  const intro=(parts[0]||"").trim();
  const items=String(parts[1]||"").split("|").map(x=>x.trim()).filter(Boolean);
  return intro+"\n\nFins naturais avaliados:\n"+items.map(x=>"- "+x).join("\n");
}

function reviewStructuredDiagnosticText(d){
  if(!d) return "";
  const src=Array.isArray(d.failed_sources)?d.failed_sources:[];
  const cand=Array.isArray(d.evaluated_candidates)?d.evaluated_candidates:[];
  const lines=[
    `Trechos já resolvidos: ${Number(d.resolved_cuts_count||0)}`,
    "",
    "Falha encontrada no próximo trecho:",
    "Originais envolvidos:",
    src.length ? `${src[0]} → ${src[src.length-1]}` : "Não identificado",
    "",
    "Intervalo global:",
    `Y ${d.failed_start ?? "?"} → ${d.failed_end ?? "?"}`,
    "",
    "Candidatos avaliados:"
  ];
  cand.forEach(c=>lines.push(`${c.file||"?"} → ${c.accepted?"aceito":"rejeitado"}${c.reason?": "+c.reason:""}`));
  lines.push("");
  lines.push(`Nenhum fim natural, faixa branca segura ou faixa uniforme segura foi encontrado dentro do limite de ${d.max_source_images ?? "?"} originais para este trecho.`);
  return lines.join("\n");
}

function reviewResultModal(j,s){
  const structuredDiagnostic =
    j?.result?.diagnostic ? j.result :
    Array.isArray(j?.result) ? j.result.find(x=>x?.diagnostic) :
    Array.isArray(j?.result?.results) ? j.result.results.find(x=>x?.diagnostic) : null;

  if(structuredDiagnostic?.diagnostic){
    appModal({
      title:"Não foi possível gerar a proposta",
      message:(structuredDiagnostic.message||"A proposta não pôde ser concluída.")+"\n\n"+reviewStructuredDiagnosticText(structuredDiagnostic.diagnostic),
      kind:"error",
      confirmText:"Fechar"
    }).then(()=>load());
    return true;
  }
  if(pdfMergeResultModal(j,s)) return true;
  if(!["review_generate","review_approve","review_reject"].includes(j.action)) return false;

  let first=(s.results||[])[0]||{};
  let chapter=first.chapter||reviewCh||"";
  let status=String(first.status||"").toLowerCase();
  let success=["ok","success","done","skipped"].includes(status);
  let message=first.message||s.details?.[0]||"";

  if(j.action==="review_generate"){
    if(success){
      appModal({
        title:"Sugestão de merge gerada",
        message:chapter?`A sugestão do capítulo ${chapter} foi criada e está pronta para revisão visual.`:"A sugestão foi criada e está pronta para revisão visual.",
        kind:"success",
        chips:[{value:1,label:"sugestão gerada"}],
        details:message?[{title:chapter?`Cap. ${chapter}`:"Resultado",message}]:[],
        confirmText:"Revisar sugestão"
      }).then(()=>load());
    }else{
      appModal({
        title:"Não foi possível gerar uma sugestão de merge",
        message:"Nenhuma proposta foi criada porque não foi encontrada uma alternativa segura dentro das regras atuais.",
        kind:"error",
        chips:[{value:1,label:"sem sugestão"}],
        details:[{title:chapter?`Cap. ${chapter}`:"Ocorrência",message:message||"Nenhuma proposta segura foi encontrada."}],
        confirmText:"Fechar"
      });
    }
    return true;
  }

  if(j.action==="review_approve"){
    let modalPromise=appModal({
      title:success?"Merge aprovado":"Não foi possível aprovar o merge",
      message:success?"A sugestão foi promovida para o MERGE.":"A sugestão não pôde ser promovida para o MERGE oficial.",
      kind:success?"success":"error",
      chips:[],
      details:success
        ? [{title:chapter?`Cap. ${chapter}`:"Resultado",message:"Merge promovido e validado."}]
        : (message?[{title:chapter?`Cap. ${chapter}`:"Resultado",message}]:[]),
      confirmText:"Fechar"
    });

    if(success && chapter){
      let actions=document.querySelector("#appModal .app-modal-actions");
      let closeBtn=actions?.querySelector("[data-modal-ok]");
      if(actions && closeBtn){
        let openBtn=document.createElement("button");
        openBtn.className="btn";
        openBtn.textContent="Abrir pasta";
        openBtn.onclick=()=>openMergeFolder(chapter);
        actions.insertBefore(openBtn,closeBtn);
      }
    }

    modalPromise.then(()=>load());
    return true;
  }

  appModal({
    title:success?"Sugestão removida":"Não foi possível remover a sugestão",
    message:success?"A proposta de review foi removida. As imagens originais e o MERGE oficial foram preservados.":"A proposta não pôde ser removida.",
    kind:success?"success":"error",
    details:message?[{title:chapter?`Cap. ${chapter}`:"Resultado",message}]:[],
    confirmText:"Fechar"
  }).then(()=>load());
  return true;
}


function mergeReasonLabel(item){
  const codes=Array.isArray(item?.reason_codes)?item.reason_codes:[];
  const map={
    auto_merge_oversized_chunk:"Faixa branca não encontrada"
  };
  if(codes.length) return codes.map(x=>map[String(x)]||String(x).replaceAll("_"," ")).join("; ");
  const status=String(item?.status||"").toLowerCase();
  if(status==="partial") return "Faixa branca não encontrada";
  if(status==="error") return item?.message||"Falha no processamento";
  return "—";
}
function mergeResidualLabel(item){
  const residuals=Array.isArray(item?.residuals)?item.residuals:[];
  if(!residuals.length) return "—";
  const fmt=n=>Number(n).toLocaleString("pt-BR");
  return residuals.map(x=>`${fmt(x.global_start)} – ${fmt(x.global_end)} px`).join("; ");
}
function mergeStatusLabel(item){
  const status=String(item?.status||"").toLowerCase();
  if(status==="partial") return "Concluído parcialmente";
  if(status==="error") return "Requer atenção";
  if(status==="skipped") return "Já concluído";
  return "Concluído";
}
function mergeExpandableRow(label,value,files,key){
  const names=Array.isArray(files)?files.filter(Boolean):[];
  const enabled=names.length>0;
  return `<div class="merge-summary-row ${enabled?"is-expandable":""}" data-expand-row="${esc(key)}">
    <span class="merge-summary-label">${esc(label)}</span>
    <strong class="merge-summary-value">${esc(value)}</strong>
    ${enabled?`<button class="merge-summary-toggle" type="button" aria-expanded="false" aria-label="Expandir ${esc(label)}" data-expand="${esc(key)}">⌄</button>`:`<span class="merge-summary-toggle-spacer"></span>`}
    ${enabled?`<div class="merge-summary-files" data-expand-panel="${esc(key)}" hidden>${names.map(name=>`<span>${esc(name)}</span>`).join("")}</div>`:""}
  </div>`;
}
function openMergeStageFolder(action,chapter){
  const kind={
    merge:"auto_merge",
    merge_level2:"merge_level2",
    merge_level3:"merge_level3"
  }[String(action||"")];
  if(!kind) return Promise.reject(new Error("Etapa de merge inválida."));
  return api(`/api/open-folder?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(chapter)}&kind=${encodeURIComponent(kind)}`);
}
function mergeOperationResultModal(j,s){
  const action=String(j?.action||"").toLowerCase();
  if(!["merge","merge_level2","merge_level3"].includes(action)) return false;
  const payload=j?.result ?? j?.response ?? j;
  const rawItems=Array.isArray(payload)?payload:(Array.isArray(payload?.items)?payload.items:[]);
  if(!rawItems.length) return false;

  const items=rawItems.map((raw,index)=>{
    const saved=action==="merge"
      ? (Array.isArray(raw.auto_merge_files)?raw.auto_merge_files:[])
      : (Array.isArray(raw.stage_files)?raw.stage_files:[]);
    const pending=Array.isArray(raw.pending_files)?raw.pending_files:[];
    const pendingSegments=action==="merge"
      ? Number(raw.pending_segments_count||0)
      : action==="merge_level2"
        ? Number(raw.pending_segments||0)
        : Number(raw.residual_pending_segments||0);
    const next=raw.next_stage || (
      pendingSegments
        ? (action==="merge"?"Auto-Merge Nível II":action==="merge_level2"?"Auto-Merge Nível III":"Revisão Merge V2")
        : "—"
    );
    const statusRaw=String(raw.status||"").toLowerCase();
    const isError=["error","failed"].includes(statusRaw);
    const isPartial=!isError && pendingSegments>0;
    const statusLabel=isError
      ? "Requer atenção"
      : isPartial
        ? "Concluído parcialmente"
        : statusRaw==="skip"||statusRaw==="skipped"
          ? "Já concluído"
          : "Concluído";
    const savedCount=action==="merge"
      ? Number(raw.auto_merge_saved||saved.length||0)
      : action==="merge_level2"
        ? Number(raw.resolved_segments||saved.length||0)
        : Number(raw.safe_segments||saved.length||0);
    const pendingValue=pending.length
      ? `${pending.length} ${pending.length===1?"imagem":"imagens"}`
      : (pendingSegments?`${pendingSegments} ${pendingSegments===1?"segmento residual":"segmentos residuais"}`:"0");
    const friendlyReason=x=>{
      const rawReason=String(x||"").trim();
      const normalized=rawReason.toLowerCase().replaceAll("_"," ").replaceAll("-"," ");
      if(normalized==="auto merge oversized chunk") return "Faixa branca não encontrada";
      return typeof l3ReasonLabel==="function" ? l3ReasonLabel(x) : rawReason.replaceAll("_"," ");
    };
    const reason=raw.reason_codes?.length
      ? raw.reason_codes.map(friendlyReason).join("; ")
      : (isPartial
          ? (action==="merge"?"Faixa branca não encontrada":raw.message||"Não foi encontrada solução automática segura")
          : isError
            ? raw.message||"Falha no processamento"
            : "—");
    return {
      ...raw,
      _index:index,
      _saved:saved,
      _pending:pending,
      _pendingSegments:pendingSegments,
      _next:next,
      _statusLabel:statusLabel,
      _savedCount:savedCount,
      _pendingValue:pendingValue,
      _reason:reason,
      _residual:mergeResidualLabel(raw),
      _needsAttention:isError||isPartial
    };
  });

  const partialCount=items.filter(x=>x._statusLabel==="Concluído parcialmente").length;
  const attentionCount=items.filter(x=>x._needsAttention && x._statusLabel!=="Concluído parcialmente").length;
  const concludedCount=items.length-partialCount-attentionCount;
  const chapterWord=items.length===1?"capítulo processado":"capítulos processados";
  const resultParts=[];
  if(concludedCount) resultParts.push(`${concludedCount} ${concludedCount===1?"concluído":"concluídos"}`);
  if(partialCount) resultParts.push(`${partialCount} ${partialCount===1?"parcial":"parciais"}`);
  if(attentionCount) resultParts.push(`${attentionCount} ${attentionCount===1?"pendente":"pendentes"}`);

  document.querySelector("#appModal")?.remove();
  let overlay=document.createElement("div");
  overlay.id="appModal";
  overlay.className="app-modal-overlay";

  const chapterHtml=items.map(item=>`
    <section class="merge-chapter-item" data-merge-chapter="${item._index}">
      <button class="merge-chapter-head" type="button" data-chapter-toggle="${item._index}" aria-expanded="false">
        <span class="merge-chapter-name">Cap. ${esc(item.chapter)}</span>
        <strong class="merge-chapter-status ${item._needsAttention?"warning":""}">${esc(item._statusLabel)}</strong>
        <span class="merge-chapter-count">${esc(item._savedCount)} ${item._savedCount===1?"merge":"merges"}</span>
        <span class="merge-chapter-chevron" aria-hidden="true">⌄</span>
      </button>
      <div class="merge-chapter-body" data-chapter-panel="${item._index}" hidden>
        <div class="merge-summary-row">
          <span class="merge-summary-label">Status</span>
          <strong class="merge-summary-value ${item._needsAttention?"warning":""}">${esc(item._statusLabel)}</strong>
          <span class="merge-summary-toggle-spacer"></span>
        </div>
        ${mergeExpandableRow("Merges salvos",String(item._savedCount),item._saved,`saved-${item._index}`)}
        ${mergeExpandableRow("Pendente",item._pendingValue,item._pending,`pending-${item._index}`)}
        <div class="merge-summary-row">
          <span class="merge-summary-label">Motivo</span>
          <strong class="merge-summary-value">${esc(item._reason)}</strong>
          <span class="merge-summary-toggle-spacer"></span>
        </div>
        <div class="merge-summary-row">
          <span class="merge-summary-label">Residual</span>
          <strong class="merge-summary-value">${esc(item._residual)}</strong>
          <span class="merge-summary-toggle-spacer"></span>
        </div>
        <div class="merge-summary-row">
          <span class="merge-summary-label">Próxima etapa</span>
          <strong class="merge-summary-value">${esc(item._next||"—")}</strong>
          <span class="merge-summary-toggle-spacer"></span>
        </div>
        <div class="merge-chapter-actions">
          <button class="btn" type="button" data-open-merge-folder="${item._index}">Abrir pasta</button>
        </div>
      </div>
    </section>
  `).join("");

  overlay.innerHTML=`<div class="app-modal merge-summary-modal" role="dialog" aria-modal="true" aria-label="Resumo da Operação">
    <div class="app-modal-head merge-summary-head">
      <div><div class="caption">PROCESSAMENTO</div><h2>Resumo da Operação</h2></div>
      <button class="app-modal-x" aria-label="Fechar">&times;</button>
    </div>
    <div class="merge-batch-summary">
      <strong>${items.length} ${chapterWord}</strong>
      ${resultParts.length?`<span>${esc(resultParts.join(" · "))}</span>`:""}
    </div>
    <div class="merge-chapter-list">${chapterHtml}</div>
    <div class="app-modal-actions merge-summary-actions">
      <button class="btn primary" type="button" data-summary-close>Fechar</button>
    </div>
  </div>`;

  const close=()=>{closeAppModal(false);};
  overlay.querySelector(".app-modal-x").onclick=close;
  overlay.querySelector("[data-summary-close]").onclick=close;
  overlay.onclick=e=>{if(e.target===overlay)close();};

  overlay.querySelectorAll("[data-chapter-toggle]").forEach(btn=>{
    btn.onclick=()=>{
      const key=btn.dataset.chapterToggle;
      const panel=overlay.querySelector(`[data-chapter-panel="${key}"]`);
      const item=overlay.querySelector(`[data-merge-chapter="${key}"]`);
      if(!panel||!item)return;
      const open=panel.hidden;
      panel.hidden=!open;
      item.classList.toggle("open",open);
      btn.setAttribute("aria-expanded",String(open));
    };
  });

  overlay.querySelectorAll("[data-expand]").forEach(btn=>{
    btn.onclick=e=>{
      e.stopPropagation();
      const key=btn.dataset.expand;
      const panel=overlay.querySelector(`[data-expand-panel="${key}"]`);
      if(!panel)return;
      const open=panel.hidden;
      panel.hidden=!open;
      btn.classList.toggle("open",open);
      btn.setAttribute("aria-expanded",String(open));
    };
  });

  overlay.querySelectorAll("[data-open-merge-folder]").forEach(btn=>{
    btn.onclick=async e=>{
      e.stopPropagation();
      const item=items[Number(btn.dataset.openMergeFolder)];
      if(!item)return;
      try{
        await openMergeStageFolder(action,item.chapter);
      }catch(err){
        toast(err.message||"Não foi possível abrir a pasta.");
      }
    };
  });

  document.body.appendChild(overlay);
  document.addEventListener("keydown",appModalKey);
  return true;
}

function showJobResult(j){
  let s=jobSummary(j);
  toast(s.title);

  if(mergeOperationResultModal(j,s)) return;
  if(level2ResultModal(j,s)) return;
  if(reviewResultModal(j,s)) return;
  if(s.kind==="error"||s.kind==="partial"){
    let occurrences=(s.details||[]).map(line=>{
      let m=String(line).match(/^Cap\.\s*([^:]+):\s*(.*)$/s);
      return m?{title:`Cap. ${m[1]} · Ocorrência`,message:m[2]}:{title:"Ocorrência",message:String(line)};
    });
    appModal({
      title:s.kind==="partial"?"Processamento concluído com ressalvas":"Processamento requer atenção",
      message:"O processamento terminou com ocorrências que precisam de atenção.",
      kind:s.kind,
      chips:[
        {value:s.ok,label:"concluído(s)"},
        {value:s.errors,label:"com ocorrência"},
        ...(s.other?[{value:s.other,label:"outro(s)"}]:[])
      ],
      details:occurrences,
      confirmText:"Fechar"
    });
  }

  if(page==="merge" && s.errors){
    let level2Btn=document.querySelector('nav button[data-page="merge_level2"]');
    if(level2Btn){
      level2Btn.classList.add("attention");
      level2Btn.title=`${s.errors} capítulo(s) precisam de tratamento no Nível II`;
    }
  }
}
function poll(id,action="",expectedTotal=0){
  let b=$("#job");
  b.hidden=false;
  let busy=false;
  let lastStateRefresh=0;
  const updateProgress=j=>{
    const total=Math.max(0,Number(j.total)||Number(expectedTotal)||0);
    const completed=Math.max(0,Math.min(total||Number.MAX_SAFE_INTEGER,Number(j.progress)||0));
    const granularMax=Math.max(0,Number(j.progress_max)||0);
    const granularValue=Math.max(0,Math.min(granularMax||Number.MAX_SAFE_INTEGER,Number(j.progress_value)||0));
    const hasGranular=granularMax>0;
    const percent=hasGranular
      ? Math.max(0,Math.min(100,Math.round((granularValue/granularMax)*100)))
      : (total?Math.max(0,Math.min(100,Math.round((completed/total)*100))):0);
    $("#jobtitle").textContent=JOB_LABELS[action]||$("#jobtitle").textContent||"Processando";
    $("#jobcount").textContent=total
      ? `${completed} de ${total} concluído(s) · ${percent}%`
      : "Preparando...";
    $("#jobmsg").textContent=j.progress_detail||j.message||(
      total
        ? `${completed} de ${total} capítulo(s) concluído(s).`
        : "Preparando processamento..."
    );
    const p=$("#progress");
    p.max=hasGranular?granularMax:Math.max(1,total||1);
    p.value=hasGranular?granularValue:completed;
    p.setAttribute("aria-valuemax",String(hasGranular?granularMax:Math.max(1,total||1)));
    p.setAttribute("aria-valuenow",String(hasGranular?granularValue:completed));
    p.setAttribute("aria-valuetext",total?`${completed} de ${total} concluídos, ${percent}%`:"Preparando");
    b.dataset.percent=String(percent);
  };
  let t=setInterval(async()=>{
    if(busy)return;
    busy=true;
    try{
      let j=await api("/api/job/"+id);
      updateProgress(j);

      let now=Date.now();
      if(!["done","error"].includes(j.status) && now-lastStateRefresh>=1200){
        try{ await load(); }
        catch(e){ console.warn("Falha ao atualizar status parcial:",e); }
        lastStateRefresh=now;
      }
      if(["done","error"].includes(j.status)){
        clearInterval(t);
        if(j.status==="done" && Number(j.total)>0){
          j.progress=Number(j.total);
          updateProgress(j);
        }
        await load();
        setTimeout(()=>b.hidden=true,1200);
        showJobResult(j);
      }
    }catch(e){
      console.warn("Falha no polling do job:",e);
    }finally{
      busy=false;
    }
  },500);
}init().catch(e=>toast(e.message));
async function shutdownServer(){
  if(!(await askAppModal("Finalizar servidor","Finalizar a Central de Processamento e voltar ao menu do terminal?","Finalizar"))) return;
  try{
    await api("/api/shutdown");
    document.body.innerHTML='<div style="min-height:100vh;display:grid;place-items:center;background:#0d1118;color:#eef2f7;font:14px system-ui"><div style="text-align:center"><h2>Central de Processamento finalizada</h2><p style="color:#94a0b4">Fechando esta aba…</p></div></div>';
    setTimeout(()=>{try{window.open("","_self");window.close()}catch(_){}},180);
  }catch(e){
    toast("Servidor finalizado.");
  }
}


if(document.readyState==="loading"){
  document.addEventListener("DOMContentLoaded",installPdfMergeUiNormalizer,{once:true});
}else{
  installPdfMergeUiNormalizer();
}
