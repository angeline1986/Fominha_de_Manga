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
async function init(){applySidebarState();cat=await api("/api/catalog");$("#provider").innerHTML=Object.keys(cat).map(x=>`<option>${x}</option>`).join("");$("#provider").onchange=fill;$("#manga").onchange=load;document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{page=b.dataset.page;tablePage=1;tableStatus="all";window._tableQuery="";document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x===b));render()});fill()}function fill(){let p=$("#provider").value;$("#manga").innerHTML=(cat[p]||[]).map(x=>`<option>${esc(x)}</option>`).join("");load()}async function load(){let p=$("#provider").value,m=$("#manga").value;if(!m){data=null;return render()}data=await api(`/api/state?provider=${encodeURIComponent(p)}&manga=${encodeURIComponent(m)}&_=${Date.now()}`);lastUpdated=new Date().toLocaleTimeString("pt-BR");$("#badge").textContent=data.summary.merge_failed||0;render()}async function refreshStatus(){let p=$("#provider").value,m=$("#manga").value;cat=await api(`/api/catalog?_=${Date.now()}`);let providers=Object.keys(cat);$("#provider").innerHTML=providers.map(x=>`<option>${x}</option>`).join("");$("#provider").value=providers.includes(p)?p:(providers[0]||"");let works=cat[$("#provider").value]||[];$("#manga").innerHTML=works.map(x=>`<option>${esc(x)}</option>`).join("");$("#manga").value=works.includes(m)?m:(works[0]||"");await load()}function head(t,d){return `<div class="head"><div><div class="caption">PROCESSAMENTO</div><h1>${esc(t)}</h1><div class="muted">${esc(d)}</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div>`}function render(){let root=$("#page");if(!data){root.innerHTML='<div class="muted">Nenhuma obra encontrada.</div>';return}if(page==="overview")return overview(root);if(page==="review")return review(root);table(root,page)}function overview(r){let s=data.summary,p=data.chapters.filter(x=>x.merge_state==="pendente").slice(0,4);r.innerHTML=`<div class="head"><div><div class="caption">VISÃO GERAL</div><h1>${esc(data.manga)}</h1><div class="muted">${esc(data.provider)} · pós-processamento</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div><div class="kpis"><div class="kpi"><b>${s.chapters}</b><span>CAPÍTULOS</span></div><div class="kpi"><b>${s.merges}</b><span>MERGES</span></div><div class="kpi"><b>${s.pending}</b><span>PENDENTES</span></div><div class="kpi"><b>${s.new??0}</b><span>NOVOS</span></div><div class="kpi"><b>${s.review}</b><span>EM REVISÃO</span></div><div class="kpi"><b>${s.pdfs}</b><span>PDFs ORIGINAIS</span></div></div><h3>Atividade da obra</h3><div class="activity">${p.map(x=>`<div class="card"><div><b>Capítulo ${esc(x.chapter)} <span class="warn">· PENDENTE</span></b><div class="muted">Merge V3 ainda não concluído.</div></div><button class="btn primary" onclick="goReview('${esc(x.chapter)}')">Tratar agora</button></div>`).join("")||'<div class="card ok">Todos os merges concluídos.</div>'}</div>`}function mergeLabel(x){
  if(x.merge)return {cls:"ok",text:`✓ ${x.merged_images}`};
  if(x.merge_error)return {cls:"warn",text:"⚠ Inválido"};
  if(x.merge_state==="pendente"||x.merge_failed)return {cls:"warn",text:"Pendente"};
  return {cls:"muted",text:"Novo"};
}
function tableFilteredRows(k){
  let q=String(window._tableQuery||"").trim().toLowerCase();
  let rows=data.chapters.filter(x=>String(x.chapter).toLowerCase().includes(q));
  if(k==="merge"&&tableStatus!=="all"){
    rows=rows.filter(x=>(x.merge_state||(!x.merge&&!x.merge_failed?"novo":x.merge_failed?"pendente":"concluido"))===tableStatus);
  }
  return rows;
}
function table(r,k){
  let cfg={pdf:["Gerar PDF","Gerar PDFs a partir das imagens originais validadas.","pdf"],merge:["Unificar imagens","Aplicar o Merge V3 preservando IMG.","merge"],clean:["Limpar balões","Executar Bubble Cleaner V3.5.","clean"],pdf_merge:["PDF do Merge","Gerar PDF com as imagens oficialmente unificadas.","pdf_merge"]}[k];
  let all=tableFilteredRows(k),pages=Math.max(1,Math.ceil(all.length/PAGE_SIZE));tablePage=Math.min(Math.max(1,tablePage),pages);
  let rows=all.slice((tablePage-1)*PAGE_SIZE,tablePage*PAGE_SIZE);
  let statusFilter=k==="merge"?`<div class="status-filter"><button class="tab ${tableStatus==="all"?"active":""}" onclick="setTableStatus('all')">Todos</button><button class="tab ${tableStatus==="novo"?"active":""}" onclick="setTableStatus('novo')">Novos</button><button class="tab ${tableStatus==="pendente"?"active":""}" onclick="setTableStatus('pendente')">Pendentes</button></div>`:"";
  let pager=`<div class="table-pager"><span>${all.length?((tablePage-1)*PAGE_SIZE+1):0}–${Math.min(tablePage*PAGE_SIZE,all.length)} de ${all.length}</span><div><button class="btn" ${tablePage<=1?"disabled":""} onclick="changeTablePage(-1)">&lt;&lt;</button><span class="page-indicator">${tablePage} / ${pages}</span><button class="btn" ${tablePage>=pages?"disabled":""} onclick="changeTablePage(1)">&gt;&gt;</button></div></div>`;
  r.innerHTML=head(cfg[0],cfg[1])+`<div class="toolbar"><input id="q" class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;tablePage=1;render()">${statusFilter}<button class="btn" onclick="allv()">Selecionar visíveis</button><button class="btn primary" onclick="runSelected('${cfg[2]}')">Executar</button></div><div class="panel"><table><thead><tr><th></th><th>CAP.</th><th>IMAGENS</th><th>MERGE</th><th>CLEAN</th><th>PDF</th><th>PDF MERGE</th></tr></thead><tbody>${rows.map(x=>{let ml=mergeLabel(x);return `<tr data-n="${esc(x.chapter).toLowerCase()}"><td><input class="ck" type="checkbox" value="${esc(x.chapter)}"></td><td>${esc(x.chapter)}</td><td>${x.pages}</td><td class="${ml.cls}">${ml.text}</td><td class="${x.clean?'ok':'muted'}">${x.clean?'✓':'—'}</td><td class="${x.pdf?'ok':'warn'}">${x.pdf?'✓':'Pendente'}</td><td class="${x.pdf_merge?'ok':'muted'}">${x.pdf_merge?'✓':'—'}</td></tr>`}).join("")}</tbody></table>${pager}</div>`;
}
function setTableStatus(v){tableStatus=v;tablePage=1;render()}
function changeTablePage(d){tablePage+=d;render()}
function filter(){tablePage=1;render()}
function allv(){document.querySelectorAll("tbody .ck").forEach(x=>x.checked=true)}
function chosen(){return [...document.querySelectorAll(".ck:checked")].map(x=>x.value)}async function runSelected(a){let ch=chosen();if(!ch.length)return toast("Selecione ao menos um capítulo.");if(await askAppModal("Confirmar",`${ch.length} capítulo(s) selecionado(s).`,"Executar"))job(a,ch)}function goReview(ch){page="review";reviewCh=ch;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.page==="review"));render()}function review(r){
 let list=data.chapters.filter(x=>x.merge_failed||x.review);
 if(!list.length){r.innerHTML=head("Tratar merges pendentes","Revise propostas alternativas antes de torná-las oficiais.")+`<div class="empty">Nenhum capítulo aguardando tratamento.</div>`;return}
 let x=list.find(z=>String(z.chapter)===String(reviewCh))||list[0];reviewCh=x.chapter;
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
   let mergeButtons=items.map((m,n)=>`<button class="rv-merge-link ${String(z.chapter)===String(x.chapter)&&n===i?"active":""}" onclick="rvSelectMerge('${esc(z.chapter)}',${n})">merge-${String(n+1).padStart(3,"0")}</button>`).join("");
   return `<div class="rv-chapter-group ${open?"open":""}">
     <button class="rv-chapter-head" onclick="rvToggleChapter('${esc(z.chapter)}')"><span class="rv-chevron">${open?"▼":"▶"}</span><span><b>${esc(z.chapter)}</b><small>${count?count+" merges estimados":"proposta ainda não gerada"}</small></span></button>
     ${open?`<div class="rv-merge-list">${mergeButtons||`<button class="rv-generate-inline" onclick="event.stopPropagation();reviewDecision('review','${esc(z.chapter)}')">Gerar proposta</button>`}</div>`:""}
   </div>`;
 }).join("");

 r.innerHTML=`<section class="rv">
 <header class="rv-head"><div><span class="eyebrow">REVISÃO VISUAL</span><h1>${esc(data.manga)} · cap ${esc(x.chapter)}</h1></div></header>
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
 </div>`:`<div class="rv-empty"><h2>Capítulo ${esc(x.chapter)}</h2><p>Gere uma proposta alternativa para iniciar a revisão visual.</p></div>`}</section>`;
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
async function job(a,ch,extra={}){let j=await api("/api/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:a,provider:data.provider,manga:data.manga,chapters:ch,...extra})});poll(j.job_id)}function jobSummary(j){
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

function reviewResultModal(j,s){
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
    appModal({
      title:success?"Merge aprovado":"Não foi possível aprovar o merge",
      message:success?"A sugestão validada foi promovida para o MERGE oficial.":"A sugestão não pôde ser promovida para o MERGE oficial.",
      kind:success?"success":"error",
      chips:[{value:success?1:0,label:"aprovado"}],
      details:message?[{title:chapter?`Cap. ${chapter}`:"Resultado",message}]:[],
      confirmText:"Fechar"
    }).then(()=>load());
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

function showJobResult(j){
  let s=jobSummary(j);
  toast(s.title);

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
    let reviewBtn=document.querySelector('nav button[data-page="review"]');
    if(reviewBtn){
      reviewBtn.classList.add("attention");
      reviewBtn.title=`${s.errors} capítulo(s) precisam de revisão`;
    }
  }
}
function poll(id){
  let b=$("#job");
  b.hidden=false;
  let busy=false;
  let lastStateRefresh=0;

  let t=setInterval(async()=>{
    if(busy)return;
    busy=true;
    try{
      let j=await api("/api/job/"+id);
      $("#jobmsg").textContent=j.message||"";
      $("#progress").max=Math.max(1,j.total||1);
      $("#progress").value=j.progress||0;

      let now=Date.now();
      if(!["done","error"].includes(j.status) && now-lastStateRefresh>=1200){
        try{ await load(); }
        catch(e){ console.warn("Falha ao atualizar status parcial:",e); }
        lastStateRefresh=now;
      }

      if(["done","error"].includes(j.status)){
        clearInterval(t);
        await load();
        setTimeout(()=>b.hidden=true,800);
        showJobResult(j);
      }
    }catch(e){
      console.warn("Falha no polling do job:",e);
    }finally{
      busy=false;
    }
  },700);
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
