const $=s=>document.querySelector(s);let cat={},data=null,page="overview",reviewCh=null,lastUpdated="";const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));async function api(u,o){let r=await fetch(u,o),j=await r.json();if(!r.ok)throw Error(j.error||"Erro");return j}function toast(m){let t=$("#toast");t.textContent=m;t.style.display="block";setTimeout(()=>t.style.display="none",4000)}
let appModalResolve=null;
function closeAppModal(value=false){document.querySelector("#appModal")?.remove();document.removeEventListener("keydown",appModalKey);if(appModalResolve){let r=appModalResolve;appModalResolve=null;r(value)}}
function appModalKey(e){if(e.key==="Escape")closeAppModal(false)}
function appModal({title,message="",chips=[],details=[],confirm=false,confirmText="OK",cancelText="Cancelar",kind="info"}){
  document.querySelector("#appModal")?.remove();
  return new Promise(resolve=>{
    appModalResolve=resolve;let overlay=document.createElement("div");overlay.id="appModal";overlay.className="app-modal-overlay";
    let chipHtml=chips.length?`<div class="app-modal-chips">${chips.map(x=>`<span class="app-modal-chip"><b>${esc(x.value)}</b> ${esc(x.label)}</span>`).join("")}</div>`:"";
    let detailHtml=details.length?`<div class="app-modal-details">${details.map(x=>`<div class="app-modal-detail"><b>${esc(x.title||"Ocorrência")}</b><span>${esc(x.message||"")}</span></div>`).join("")}</div>`:"";
    overlay.innerHTML=`<div class="app-modal app-modal-${esc(kind)}" role="dialog" aria-modal="true"><div class="app-modal-head"><div><div class="caption">PROCESSAMENTO</div><h2>${esc(title)}</h2></div><button class="app-modal-x" aria-label="Fechar">&times;</button></div>${message?`<p class="app-modal-message">${esc(message)}</p>`:""}${chipHtml}${detailHtml}<div class="app-modal-actions">${confirm?`<button class="btn" data-modal-cancel>${esc(cancelText)}</button>`:""}<button class="btn primary" data-modal-ok>${esc(confirmText)}</button></div></div>`;
    overlay.onclick=e=>{if(e.target===overlay)closeAppModal(false)};overlay.querySelector(".app-modal-x").onclick=()=>closeAppModal(false);
    overlay.querySelector("[data-modal-cancel]")?.addEventListener("click",()=>closeAppModal(false));overlay.querySelector("[data-modal-ok]").onclick=()=>closeAppModal(true);
    document.body.appendChild(overlay);document.addEventListener("keydown",appModalKey);
  });
}
async function askAppModal(title,message,confirmText="Confirmar"){return appModal({title,message,confirm:true,confirmText})}
async function init(){cat=await api("/api/catalog");$("#provider").innerHTML=Object.keys(cat).map(x=>`<option>${x}</option>`).join("");$("#provider").onchange=fill;$("#manga").onchange=load;document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{page=b.dataset.page;document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x===b));render()});fill()}function fill(){let p=$("#provider").value;$("#manga").innerHTML=(cat[p]||[]).map(x=>`<option>${esc(x)}</option>`).join("");load()}async function load(){let p=$("#provider").value,m=$("#manga").value;if(!m){data=null;return render()}data=await api(`/api/state?provider=${encodeURIComponent(p)}&manga=${encodeURIComponent(m)}&_=${Date.now()}`);lastUpdated=new Date().toLocaleTimeString("pt-BR");$("#badge").textContent=data.summary.merge_failed||0;render()}async function refreshStatus(){let p=$("#provider").value,m=$("#manga").value;cat=await api(`/api/catalog?_=${Date.now()}`);let providers=Object.keys(cat);$("#provider").innerHTML=providers.map(x=>`<option>${x}</option>`).join("");$("#provider").value=providers.includes(p)?p:(providers[0]||"");let works=cat[$("#provider").value]||[];$("#manga").innerHTML=works.map(x=>`<option>${esc(x)}</option>`).join("");$("#manga").value=works.includes(m)?m:(works[0]||"");await load()}function head(t,d){return `<div class="head"><div><div class="caption">PROCESSAMENTO</div><h1>${esc(t)}</h1><div class="muted">${esc(d)}</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div>`}function render(){let root=$("#page");if(!data){root.innerHTML='<div class="muted">Nenhuma obra encontrada.</div>';return}if(page==="overview")return overview(root);if(page==="review")return review(root);table(root,page)}function overview(r){let s=data.summary,p=data.chapters.filter(x=>!x.merge).slice(0,4);r.innerHTML=`<div class="head"><div><div class="caption">VISÃO GERAL</div><h1>${esc(data.manga)}</h1><div class="muted">${esc(data.provider)} · pós-processamento</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div><div class="kpis"><div class="kpi"><b>${s.chapters}</b><span>CAPÍTULOS</span></div><div class="kpi"><b>${s.merges}</b><span>MERGES</span></div><div class="kpi"><b>${s.pending}</b><span>PENDENTES</span></div><div class="kpi"><b>${s.review}</b><span>EM REVISÃO</span></div><div class="kpi"><b>${s.pdfs}</b><span>PDFs ORIGINAIS</span></div></div><h3>Atividade da obra</h3><div class="activity">${p.map(x=>`<div class="card"><div><b>Capítulo ${esc(x.chapter)} <span class="warn">· PENDENTE</span></b><div class="muted">Merge V3 ainda não concluído.</div></div><button class="btn primary" onclick="goReview('${esc(x.chapter)}')">Tratar agora</button></div>`).join("")||'<div class="card ok">Todos os merges concluídos.</div>'}</div>`}function table(r,k){let cfg={pdf:["Gerar PDF","Gerar PDFs a partir das imagens originais validadas.","pdf"],merge:["Unificar imagens","Aplicar o Merge V3 preservando IMG.","merge"],clean:["Limpar balões","Executar Bubble Cleaner V3.5.","clean"],pdf_merge:["PDF do Merge","Gerar PDF com as imagens oficialmente unificadas.","pdf_merge"]}[k];r.innerHTML=head(cfg[0],cfg[1])+`<div class="toolbar"><input id="q" class="search" placeholder="Buscar capítulo..." oninput="filter()"><button class="btn" onclick="allv()">Selecionar visíveis</button><button class="btn primary" onclick="runSelected('${cfg[2]}')">Executar</button></div><div class="panel"><table><thead><tr><th></th><th>CAP.</th><th>IMAGENS</th><th>MERGE</th><th>CLEAN</th><th>PDF</th><th>PDF MERGE</th></tr></thead><tbody>${data.chapters.map(x=>`<tr data-n="${esc(x.chapter).toLowerCase()}"><td><input class="ck" type="checkbox" value="${esc(x.chapter)}"></td><td>${esc(x.chapter)}</td><td>${x.pages}</td><td class="${x.merge?'ok':'warn'}">${x.merge?'✓ '+x.merged_images:(x.merge_error?'⚠ Inválido':'Pendente')}</td><td class="${x.clean?'ok':'muted'}">${x.clean?'✓':'—'}</td><td class="${x.pdf?'ok':'warn'}">${x.pdf?'✓':'Pendente'}</td><td class="${x.pdf_merge?'ok':'muted'}">${x.pdf_merge?'✓':'—'}</td></tr>`).join("")}</tbody></table></div>`}function filter(){let q=$("#q").value.toLowerCase();document.querySelectorAll("tbody tr").forEach(x=>x.style.display=x.dataset.n.includes(q)?"":"none")}function allv(){document.querySelectorAll("tbody tr").forEach(x=>{if(x.style.display!=="none")x.querySelector(".ck").checked=true})}function chosen(){return [...document.querySelectorAll(".ck:checked")].map(x=>x.value)}async function runSelected(a){let ch=chosen();if(!ch.length)return toast("Selecione ao menos um capítulo.");if(await askAppModal("Confirmar processamento",`Executar em ${ch.length} capítulo(s)?`,"Executar"))job(a,ch)}function goReview(ch){page="review";reviewCh=ch;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.page==="review"));render()}function review(r){let rows=data.chapters.filter(x=>x.merge_failed||x.review);if(!reviewCh||!rows.find(x=>x.chapter===reviewCh))reviewCh=rows[0]?.chapter;let cur=rows.find(x=>x.chapter===reviewCh);r.innerHTML=head("Tratar merges pendentes","Propor e revisar exceções sem alterar o Merge V3.")+`<div class="split"><div class="work">${rows.map(x=>`<div class="item ${x.chapter===reviewCh?'active':''}" onclick="reviewCh='${esc(x.chapter)}';render()"><b>${esc(x.chapter)}</b><span class="${x.review?'ok':'warn'}">${x.review?'REVISÃO':'PENDENTE'}</span></div>`).join("")}</div><div class="detail">${cur?detail(cur):'<div class="muted">Nenhum pendente.</div>'}</div></div>`}function detail(x){let imgs=x.review?(x.review_files||[]).map(file=>
    `<img loading="lazy" src="/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(x.chapter)}&file=${encodeURIComponent(file)}">`
  ).join(""):"";return `<div class="caption">CAPÍTULO</div><h1>${esc(x.chapter)}</h1><div class="notice"><b class="${x.merge?'ok':'warn'}">${x.merge?'✓ MERGE oficial':'⚠ Merge V3 não concluído'}</b><div class="muted">${x.review?'Proposta disponível em MERGE_REVIEW.':'Nenhuma proposta gerada.'}</div></div>${x.review?`<div class="metrics"><div class="metric"><b>${x.pages}</b><span class="muted">originais</span></div><div>→</div><div class="metric"><b>${x.review_images}</b><span class="muted">proposta</span></div></div><div class="preview">${imgs}</div><div class="actions"><button class="btn danger" onclick="ract('review_reject')">Rejeitar</button><button class="btn" onclick="ract('review_generate')">Regenerar</button>${!x.merge?'<button class="btn primary" onclick="ract(\'review_approve\')">Aprovar merge</button>':''}</div>`:`<div class="actions"><button class="btn primary" onclick="ract('review_generate')">Gerar merge proposto</button></div>`}`}let reviewViewerIndex=0,reviewViewerScale=1;
function reviewViewerImages(){return [...document.querySelectorAll(".review-thumb")].map(x=>x.src)}
function openReviewImage(src,index=0){
  reviewViewerIndex=index;reviewViewerScale=1;
  let v=document.createElement("div");v.id="reviewViewer";v.className="review-viewer";
  v.innerHTML=`<div class="review-viewer-bar"><button class="btn" onclick="closeReviewImage()">Fechar</button><div class="review-viewer-tools"><button class="btn" onclick="reviewZoom(-.25)">-</button><span id="reviewZoomLabel">100%</span><button class="btn" onclick="reviewZoom(.25)">+</button><button class="btn" onclick="reviewFit()">Ajustar</button><button class="btn" onclick="reviewPrev()">Anterior</button><button class="btn" onclick="reviewNext()">Proxima</button></div></div><div class="review-viewer-stage" onclick="if(event.target===this)closeReviewImage()"><img id="reviewViewerImg" src="${src}" ondblclick="reviewReset()"></div>`;
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
async function ract(a){if(a==="review_approve"&&!(await askAppModal("Aprovar merge","Você validou visualmente a proposta?","Aprovar")))return;if(a==="review_reject"&&!(await askAppModal("Rejeitar proposta","Remover somente MERGE_REVIEW?","Remover")))return;job(a,[reviewCh])}async function job(a,ch){let j=await api("/api/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:a,provider:data.provider,manga:data.manga,chapters:ch})});poll(j.job_id)}function jobSummary(j){
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
    document.body.innerHTML='<div style="min-height:100vh;display:grid;place-items:center;background:#0d1118;color:#eef2f7;font:14px system-ui"><div style="text-align:center"><h2>Central de Processamento finalizada</h2><p style="color:#94a0b4">Você pode fechar esta aba. O menu do terminal será retomado.</p></div></div>';
  }catch(e){
    toast("Servidor finalizado.");
  }
}
