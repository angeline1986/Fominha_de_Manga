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
async function init(){applySidebarState();cat=await api("/api/catalog");$("#provider").innerHTML=Object.keys(cat).map(x=>`<option>${x}</option>`).join("");$("#provider").onchange=fill;$("#manga").onchange=load;document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{page=b.dataset.page;tablePage=1;tableStatus="all";window._tableQuery="";document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x===b));render()});fill()}function fill(){let p=$("#provider").value;$("#manga").innerHTML=(cat[p]||[]).map(x=>`<option>${esc(x)}</option>`).join("");load()}async function load(){let p=$("#provider").value,m=$("#manga").value;if(!m){data=null;return render()}data=await api(`/api/state?provider=${encodeURIComponent(p)}&manga=${encodeURIComponent(m)}&_=${Date.now()}`);lastUpdated=new Date().toLocaleTimeString("pt-BR");$("#badge").textContent=data.summary.review_pending??data.summary.pending??0;let b2=$("#badgeLevel2");if(b2)b2.textContent=data.summary.partial||0;render()}async function refreshStatus(){let p=$("#provider").value,m=$("#manga").value;cat=await api(`/api/catalog?_=${Date.now()}`);let providers=Object.keys(cat);$("#provider").innerHTML=providers.map(x=>`<option>${x}</option>`).join("");$("#provider").value=providers.includes(p)?p:(providers[0]||"");let works=cat[$("#provider").value]||[];$("#manga").innerHTML=works.map(x=>`<option>${esc(x)}</option>`).join("");$("#manga").value=works.includes(m)?m:(works[0]||"");await load()}function head(t,d){return `<div class="head"><div><h1>${esc(t)}</h1><div class="muted">${esc(d)}</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div>`}
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

function render(){let b3=$("#badgeLevel3");if(b3&&data)b3.textContent=data.chapters.filter(x=>x.merge_level3_pending).length;let root=$("#page");if(!data){root.innerHTML='<div class="muted">Nenhuma obra encontrada.</div>';return}if(page==="overview")return overview(root);if(page==="merge_level2")return mergeLevel2(root);if(page==="merge_level3")return mergeLevel3(root);if(page==="review")return review(root);if(page==="review_v2")return reviewV2(root);table(root,page)}function overview(r){let s=data.summary,p=data.chapters.filter(x=>x.merge_state==="pendente_review"||(x.merge_state==="parcial"&&!x.merge_level2_validated)).slice(0,4);r.innerHTML=`<div class="head"><div><div class="caption">VISÃO GERAL</div><h1>${esc(data.manga)}</h1><div class="muted">${esc(data.provider)} · pós-processamento</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div><div class="kpis"><div class="kpi"><b>${s.chapters}</b><span>CAPÍTULOS</span></div><div class="kpi"><b>${s.merges}</b><span>MERGES</span></div><div class="kpi"><b>${s.pending}</b><span>PENDENTES DE REVISÃO</span></div><div class="kpi"><b>${s.partial??0}</b><span>NÍVEL II</span></div><div class="kpi"><b>${s.review}</b><span>EM REVISÃO</span></div><div class="kpi"><b>${s.pdfs}</b><span>PDFs ORIGINAIS</span></div></div><h3>Atividade da obra</h3><div class="activity">${p.map(x=>`<div class="card"><div><b>Capítulo ${esc(x.chapter)} <span class="warn">· ${x.merge_state==="parcial"?"NÍVEL II":"PENDENTE DE REVISÃO"}</span></b><div class="muted">${mergePartialText(x)}</div></div><button class="btn primary" onclick="${x.merge_state==="parcial"?`goLevel2('${esc(x.chapter)}')`:`goReview('${esc(x.chapter)}')`}">Tratar agora</button></div>`).join("")||'<div class="card ok">Todos os merges concluídos.</div>'}</div>`}function mergeLabel(x){
  if(x.merge)return {cls:"ok",text:`✓ ${x.merged_images}`};
  if(x.merge_error)return {cls:"warn",text:"⚠ Inválido"};
  if(x.merge_state==="parcial")return {cls:"warn",text:"Parcial"};
  if(x.merge_state==="pendente_review"||x.merge_state==="pendente"||x.merge_failed)return {cls:"warn",text:"Pendente"};
  return {cls:"muted",text:"Novo"};
}
function tableFilteredRows(k){
  let q=String(window._tableQuery||"").trim().toLowerCase();
  let rows=data.chapters.filter(x=>String(x.chapter).toLowerCase().includes(q));
  if(k==="merge"&&tableStatus!=="all"){
    rows=rows.filter(x=>(x.merge_state||(!x.merge&&!x.merge_failed?"novo":x.merge_failed?"pendente_review":"concluido"))===tableStatus);
  }
  return rows;
}
function table(r,k){
  let cfg={pdf:["Gerar PDF","Gerar PDFs a partir das imagens originais validadas.","pdf"],merge:["Auto-Merge","Aplicar o Merge V3 preservando IMG.","merge"],clean:["Limpar balões","Executar Bubble Cleaner V3.5.","clean"],pdf_merge:["PDF do Merge","Gerar PDF com as imagens oficialmente unificadas.","pdf_merge"]}[k];
  let all=tableFilteredRows(k),pages=Math.max(1,Math.ceil(all.length/PAGE_SIZE));tablePage=Math.min(Math.max(1,tablePage),pages);
  let rows=all.slice((tablePage-1)*PAGE_SIZE,tablePage*PAGE_SIZE);
  let statusFilter=k==="merge"?`<div class="status-filter"><button class="tab ${tableStatus==="all"?"active":""}" onclick="setTableStatus('all')">Todos</button><button class="tab ${tableStatus==="novo"?"active":""}" onclick="setTableStatus('novo')">Novos</button><button class="tab ${tableStatus==="pendente_review"?"active":""}" onclick="setTableStatus('pendente_review')">Pendentes</button><button class="tab ${tableStatus==="parcial"?"active":""}" onclick="setTableStatus('parcial')">Parciais</button></div>`:"";
  let pager=`<div class="table-pager"><span>${all.length?((tablePage-1)*PAGE_SIZE+1):0}–${Math.min(tablePage*PAGE_SIZE,all.length)} de ${all.length}</span><div><button class="btn" ${tablePage<=1?"disabled":""} onclick="changeTablePage(-1)">&lt;&lt;</button><span class="page-indicator">${tablePage} / ${pages}</span><button class="btn" ${tablePage>=pages?"disabled":""} onclick="changeTablePage(1)">&gt;&gt;</button></div></div>`;
  r.innerHTML=head(cfg[0],cfg[1])+`<div class="toolbar"><input id="q" class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;tablePage=1;render()">${statusFilter}<button class="btn" onclick="allv()">Selecionar visíveis</button><button class="btn primary" onclick="runSelected('${cfg[2]}')">Executar</button></div><div class="panel"><table><thead><tr><th></th><th>CAP.</th><th>MERGE</th><th>CLEAN</th><th>PDF MERGE</th></tr></thead><tbody>${rows.map(x=>{let ml=mergeLabel(x);return `<tr data-n="${esc(x.chapter).toLowerCase()}"><td><input class="ck" type="checkbox" value="${esc(x.chapter)}"></td><td>${esc(x.chapter)}</td><td>${x.pages}</td><td class="${ml.cls}">${ml.text}</td><td class="${x.clean?'ok':'muted'}">${x.clean?'✓':'—'}</td><td class="${x.pdf?'ok':'warn'}">${x.pdf?'✓':'Pendente'}</td><td class="${x.pdf_merge?'ok':'muted'}">${x.pdf_merge?'✓':'—'}</td></tr>`}).join("")}</tbody></table>${pager}</div>`;
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
        ? `${resolved} merge(s) automáticos preservados em MERGE_LEVEL2. ${pending} região(ões) seguem para o Auto-Merge Nível III: ${region}.`
        : `${resolved} merge(s) automáticos validados. Nenhuma região permaneceu pendente para o Auto-Merge Nível III.`;
    return {title:`Cap. ${x.chapter}`,message};
  });
  appModal({
    title:errors.length?"Nível II concluído com ocorrências":"Nível II validado",
    message:errors.length
      ?"Alguns capítulos ainda precisam de atenção."
      :results.some(x=>Number(x.pending_segments||0)>0)
        ?"Os trechos automáticos foram preservados e somente as regiões pendentes foram encaminhadas para o Auto-Merge Nível III."
        :"O Nível II foi concluído sem regiões pendentes para o Auto-Merge Nível III.",
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
 r.innerHTML=head("Auto-Merge Nível II","Validar trechos automáticos e encaminhar somente regiões com falha.")+`<div class="toolbar"><input id="q" class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;tablePage=1;render()"><button class="btn" onclick="allv()">Selecionar visíveis</button><button class="btn primary" onclick="runSelected('merge_level2')">Validar Nível II</button></div><div class="panel"><table><thead><tr><th></th><th>CAP.</th><th>MERGE NÍVEL II</th><th>REGIÃO PARA REVISÃO</th></tr></thead><tbody>${rows.map(x=>{let p=x.merge_partition||{},resolved=Number(p.resolved_segments_count||0);return `<tr data-n="${esc(x.chapter).toLowerCase()}"><td><input class="ck" type="checkbox" value="${esc(x.chapter)}"></td><td>${esc(x.chapter)}</td><td class="ok">✓ ${resolved}</td><td>${esc(level2RegionLabel(x))}</td></tr>`}).join("")}</tbody></table>${pager}</div>`;
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
      <td>${pending?`<input class="ck" type="checkbox" value="${esc(x.chapter)}">`:""}</td>
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
    `<div class="toolbar"><input id="q" class="search" placeholder="Buscar capítulo..." value="${esc(window._tableQuery||"")}" oninput="window._tableQuery=this.value;tablePage=1;render()"><button class="btn" onclick="allv()">Selecionar visíveis</button><button class="btn primary" onclick="runSelected('merge_level3')">Analisar Nível III</button></div>
     <div class="panel"><table class="l3-table"><thead><tr><th></th><th>CAP.</th><th>NÍVEL III</th><th>SAFE</th><th>RESIDUAL</th><th>RESULTADO</th><th></th></tr></thead><tbody>${body||`<tr><td colspan="7" class="muted">Nenhum capítulo encontrado.</td></tr>`}</tbody></table>${pager}</div>`;
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

function chosen(){return [...document.querySelectorAll(".ck:checked")].map(x=>x.value)}async function runSelected(a){let ch=chosen();if(!ch.length)return toast("Selecione ao menos um capítulo.");if(await askAppModal("Confirmar",`${ch.length} capítulo(s) selecionado(s).`,"Executar"))job(a,ch)}function goReview(ch){page="review";reviewCh=ch;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.page==="review"));render()}function goLevel2(ch){page="merge_level2";reviewCh=ch;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.page==="merge_level2"));render()}function review(r){
 let list=data.chapters.filter(x=>x.merge_state==="pendente_review"||x.review);
 if(!list.length){r.innerHTML=head("Revisão Merge pendentes","Revise propostas alternativas antes de torná-las oficiais.")+`<div class="empty">Nenhum capítulo aguardando tratamento.</div>`;return}
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
  let list=data.chapters.filter(x=>x.merge_state==="pendente_review"&&x.merge_level3_detail?.available&&x.merge_level3_detail?.valid&&(x.merge_level3_detail.residual_pending_segments_count||0)>0);
  if(!list.length){r.innerHTML=head("Revisão Merge V2","Review assistido pelos diagnósticos estruturais do Auto-Merge Nível III.")+`<div class="empty">Nenhum residual válido do Nível III aguardando revisão.</div>`;return}
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
  const success=["done","success","completed"].includes(status) && payload?.ok!==false;
  const chapter=String(payload?.chapter ?? job?.chapter ?? job?.request?.chapter ?? "");
  let files=pdfMergeFileNames(payload);

  const modalPromise=appModal({
    title:success?"PDF do Merge gerado":"Não foi possível gerar o PDF do Merge",
    message:success?"O PDF do Merge foi gerado com sucesso.":(payload?.message||payload?.error||"A geração não foi concluída."),
    kind:success?"success":"error",
    chips:[],
    details:success
      ? [{title:chapter?`Cap. ${chapter}`:"Resultado",message:files.length?files.join("\n"):"Consultando arquivo gerado..."}]
      : [{title:chapter?`Cap. ${chapter}`:"Erro",message:payload?.message||payload?.error||"Erro não detalhado pelo processamento."}],
    confirmText:"Fechar"
  });

  const finalizeSuccessUi=(resolvedFiles)=>{
    const modal=document.querySelector("#appModal");
    if(!modal) return;
    const detail=modal.querySelector(".app-modal-detail");
    if(detail && resolvedFiles.length){
      detail.innerHTML=`<strong>${chapter?`Cap. ${esc(chapter)}`:"Resultado"}</strong>`+
        resolvedFiles.map(f=>`<span>${esc(f)}</span>`).join("");
    }
    const actions=modal.querySelector(".app-modal-actions");
    const closeBtn=actions?.querySelector("[data-modal-ok]") || actions?.querySelector("button:last-child");
    if(actions && closeBtn && !actions.querySelector(".pdf-merge-open-folder")){
      const openBtn=document.createElement("button");
      openBtn.className="btn pdf-merge-open-folder";
      openBtn.textContent="Abrir pasta";
      openBtn.onclick=()=>openPdfMergeFolder(chapter);
      actions.insertBefore(openBtn,closeBtn);
    }
  };

  if(success){
    if(files.length){
      requestAnimationFrame(()=>finalizeSuccessUi(files));
    }else if(chapter){
      fetchPdfMergeFiles(chapter).then(resolved=>{
        files=resolved||[];
        finalizeSuccessUi(files);
      });
    }
  }

  modalPromise.then(()=>load());
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

function showJobResult(j){
  let s=jobSummary(j);
  toast(s.title);

  if(level2ResultModal(j,s)) return;
  if(reviewResultModal(j,s)) return;
  if(page==="merge"){
    const payload=j?.result ?? j?.response ?? j;
    const items=Array.isArray(payload)
      ? payload
      : (Array.isArray(payload?.items) ? payload.items : []);
    const savedItems=items.filter(x=>Number(x?.auto_merge_saved||0)>0);

    if(savedItems.length){
      const totalSaved=savedItems.reduce(
        (acc,x)=>acc+Number(x.auto_merge_saved||0),
        0
      );
      const residualCount=savedItems.filter(x=>x?.status==="partial").length;
      const hasResidual=residualCount>0;

      const modalPromise=appModal({
        title:hasResidual?"Auto-Merge concluído parcialmente":"Auto-Merge concluído",
        message:hasResidual
          ? "Os trechos resolvidos pelo Auto-Merge foram salvos. Somente o residual seguirá para o Nível II."
          : "Todos os trechos resolvidos pelo Auto-Merge foram salvos em AUTO_MERGE e consolidados no MERGE final.",
        kind:"partial",
        chips:[
          {value:totalSaved,label:"merge(s) salvo(s)"},
          {value:residualCount,label:"capítulo(s) com residual"}
        ],
        details:savedItems.map(x=>({
          title:`Cap. ${x.chapter} · Auto-Merge`,
          message:`${Number(x.auto_merge_saved||0)} merge(s) seguro(s) foram gerados e salvos em AUTO_MERGE. ${x.message||""}`.trim()
        })),
        confirmText:"Fechar"
      });

      requestAnimationFrame(()=>{
        const actions=document.querySelector("#appModal .app-modal-actions");
        const closeBtn=actions?.querySelector("[data-modal-ok]");
        if(actions && closeBtn && savedItems.length===1){
          const openBtn=document.createElement("button");
          openBtn.className="btn";
          openBtn.textContent="Abrir pasta";
          openBtn.onclick=()=>openAutoMergeFolder(savedItems[0].chapter);
          actions.insertBefore(openBtn,closeBtn);
        }
      });

      modalPromise.then(()=>load());
      return;
    }
  }



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


if(document.readyState==="loading"){
  document.addEventListener("DOMContentLoaded",installPdfMergeUiNormalizer,{once:true});
}else{
  installPdfMergeUiNormalizer();
}
