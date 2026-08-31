const $=s=>document.querySelector(s);let cat={},data=null,page="overview",reviewCh=null,lastUpdated="";const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));async function api(u,o){let r=await fetch(u,o),j=await r.json();if(!r.ok)throw Error(j.error||"Erro");return j}function toast(m){let t=$("#toast");t.textContent=m;t.style.display="block";setTimeout(()=>t.style.display="none",4000)}async function init(){cat=await api("/api/catalog");$("#provider").innerHTML=Object.keys(cat).map(x=>`<option>${x}</option>`).join("");$("#provider").onchange=fill;$("#manga").onchange=load;document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{page=b.dataset.page;document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x===b));render()});fill()}function fill(){let p=$("#provider").value;$("#manga").innerHTML=(cat[p]||[]).map(x=>`<option>${esc(x)}</option>`).join("");load()}async function load(){let p=$("#provider").value,m=$("#manga").value;if(!m){data=null;return render()}data=await api(`/api/state?provider=${encodeURIComponent(p)}&manga=${encodeURIComponent(m)}&_=${Date.now()}`);lastUpdated=new Date().toLocaleTimeString("pt-BR");$("#badge").textContent=data.summary.pending;render()}async function refreshStatus(){let p=$("#provider").value,m=$("#manga").value;cat=await api(`/api/catalog?_=${Date.now()}`);let providers=Object.keys(cat);$("#provider").innerHTML=providers.map(x=>`<option>${x}</option>`).join("");$("#provider").value=providers.includes(p)?p:(providers[0]||"");let works=cat[$("#provider").value]||[];$("#manga").innerHTML=works.map(x=>`<option>${esc(x)}</option>`).join("");$("#manga").value=works.includes(m)?m:(works[0]||"");await load()}function head(t,d){return `<div class="head"><div><div class="caption">PROCESSAMENTO</div><h1>${esc(t)}</h1><div class="muted">${esc(d)}</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div>`}function render(){let root=$("#page");if(!data){root.innerHTML='<div class="muted">Nenhuma obra encontrada.</div>';return}if(page==="overview")return overview(root);if(page==="review")return review(root);table(root,page)}function overview(r){let s=data.summary,p=data.chapters.filter(x=>!x.merge).slice(0,4);r.innerHTML=`<div class="head"><div><div class="caption">VISÃO GERAL</div><h1>${esc(data.manga)}</h1><div class="muted">${esc(data.provider)} · pós-processamento</div><div class="updated-at">${lastUpdated?`Atualizado às ${lastUpdated}`:""}</div></div><button class="btn" onclick="refreshStatus()">Atualizar status</button></div><div class="kpis"><div class="kpi"><b>${s.chapters}</b><span>CAPÍTULOS</span></div><div class="kpi"><b>${s.merges}</b><span>MERGES</span></div><div class="kpi"><b>${s.pending}</b><span>PENDENTES</span></div><div class="kpi"><b>${s.review}</b><span>EM REVISÃO</span></div><div class="kpi"><b>${s.pdfs}</b><span>PDFs ORIGINAIS</span></div></div><h3>Atividade da obra</h3><div class="activity">${p.map(x=>`<div class="card"><div><b>Capítulo ${esc(x.chapter)} <span class="warn">· PENDENTE</span></b><div class="muted">Merge V3 ainda não concluído.</div></div><button class="btn primary" onclick="goReview('${esc(x.chapter)}')">Tratar agora</button></div>`).join("")||'<div class="card ok">Todos os merges concluídos.</div>'}</div>`}function table(r,k){let cfg={pdf:["Gerar PDF","Gerar PDFs a partir das imagens originais validadas.","pdf"],merge:["Unificar imagens","Aplicar o Merge V3 preservando IMG.","merge"],clean:["Limpar balões","Executar Bubble Cleaner V3.5.","clean"],pdf_merge:["PDF do Merge","Gerar PDF com as imagens oficialmente unificadas.","pdf_merge"]}[k];r.innerHTML=head(cfg[0],cfg[1])+`<div class="toolbar"><input id="q" class="search" placeholder="Buscar capítulo..." oninput="filter()"><button class="btn" onclick="allv()">Selecionar visíveis</button><button class="btn primary" onclick="runSelected('${cfg[2]}')">Executar</button></div><div class="panel"><table><thead><tr><th></th><th>CAP.</th><th>IMAGENS</th><th>MERGE</th><th>CLEAN</th><th>PDF</th><th>PDF MERGE</th></tr></thead><tbody>${data.chapters.map(x=>`<tr data-n="${esc(x.chapter).toLowerCase()}"><td><input class="ck" type="checkbox" value="${esc(x.chapter)}"></td><td>${esc(x.chapter)}</td><td>${x.pages}</td><td class="${x.merge?'ok':'warn'}">${x.merge?'✓ '+x.merged_images:(x.merge_error?'⚠ Inválido':'Pendente')}</td><td class="${x.clean?'ok':'muted'}">${x.clean?'✓':'—'}</td><td class="${x.pdf?'ok':'warn'}">${x.pdf?'✓':'Pendente'}</td><td class="${x.pdf_merge?'ok':'muted'}">${x.pdf_merge?'✓':'—'}</td></tr>`).join("")}</tbody></table></div>`}function filter(){let q=$("#q").value.toLowerCase();document.querySelectorAll("tbody tr").forEach(x=>x.style.display=x.dataset.n.includes(q)?"":"none")}function allv(){document.querySelectorAll("tbody tr").forEach(x=>{if(x.style.display!=="none")x.querySelector(".ck").checked=true})}function chosen(){return [...document.querySelectorAll(".ck:checked")].map(x=>x.value)}function runSelected(a){let ch=chosen();if(!ch.length)return toast("Selecione ao menos um capítulo.");if(confirm(`Executar em ${ch.length} capítulo(s)?`))job(a,ch)}function goReview(ch){page="review";reviewCh=ch;document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.page==="review"));render()}function review(r){let rows=data.chapters.filter(x=>!x.merge||x.review);if(!reviewCh||!rows.find(x=>x.chapter===reviewCh))reviewCh=rows[0]?.chapter;let cur=rows.find(x=>x.chapter===reviewCh);r.innerHTML=head("Tratar merges pendentes","Propor e revisar exceções sem alterar o Merge V3.")+`<div class="split"><div class="work">${rows.map(x=>`<div class="item ${x.chapter===reviewCh?'active':''}" onclick="reviewCh='${esc(x.chapter)}';render()"><b>${esc(x.chapter)}</b><span class="${x.review?'ok':'warn'}">${x.review?'REVISÃO':'PENDENTE'}</span></div>`).join("")}</div><div class="detail">${cur?detail(cur):'<div class="muted">Nenhum pendente.</div>'}</div></div>`}function detail(x){let imgs=x.review?Array.from({length:Math.min(x.review_images,12)},(_,i)=>`<img src="/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&chapter=${encodeURIComponent(x.chapter)}&file=merged-${String(i+1).padStart(3,'0')}.png">`).join(""):"";return `<div class="caption">CAPÍTULO</div><h1>${esc(x.chapter)}</h1><div class="notice"><b class="${x.merge?'ok':'warn'}">${x.merge?'✓ MERGE oficial':'⚠ Merge V3 não concluído'}</b><div class="muted">${x.review?'Proposta disponível em MERGE_REVIEW.':'Nenhuma proposta gerada.'}</div></div>${x.review?`<div class="metrics"><div class="metric"><b>${x.pages}</b><span class="muted">originais</span></div><div>→</div><div class="metric"><b>${x.review_images}</b><span class="muted">proposta</span></div></div><div class="preview">${imgs}</div><div class="actions"><button class="btn danger" onclick="ract('review_reject')">Rejeitar</button><button class="btn" onclick="ract('review_generate')">Regenerar</button>${!x.merge?'<button class="btn primary" onclick="ract(\'review_approve\')">Aprovar merge</button>':''}</div>`:`<div class="actions"><button class="btn primary" onclick="ract('review_generate')">Gerar merge proposto</button></div>`}`}function ract(a){if(a==="review_approve"&&!confirm("Você validou visualmente a proposta?"))return;if(a==="review_reject"&&!confirm("Remover somente MERGE_REVIEW?"))return;job(a,[reviewCh])}async function job(a,ch){let j=await api("/api/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:a,provider:data.provider,manga:data.manga,chapters:ch})});poll(j.job_id)}function jobSummary(j){
  let results=Array.isArray(j.result)?j.result:[];
  let ok=results.filter(x=>["ok","success","done","skipped"].includes(String(x.status||"").toLowerCase()));
  let errors=results.filter(x=>String(x.status||"").toLowerCase()==="error");
  let other=results.filter(x=>!ok.includes(x)&&!errors.includes(x));

  if(j.status==="error" && !errors.length){
    return {kind:"error",title:"Processamento interrompido",ok:0,errors:1,other:0,details:[j.error||"Falha no processamento."]};
  }

  let kind=errors.length?(ok.length||other.length?"partial":"error"):"success";
  let title=kind==="success"?"Processamento concluído":kind==="partial"?"Processamento concluído com ressalvas":"Processamento finalizado com erros";
  let details=errors.map(x=>`Cap. ${x.chapter}: ${x.message||"Erro sem detalhe."}`);

  return {kind,title,ok:ok.length,errors:errors.length,other:other.length,details};
}

function showJobResult(j){
  let s=jobSummary(j);
  let detail=s.details.length?`\n\n${s.details.join("\n")}`:"";
  let summary=`${s.title}\n\n${s.ok} concluído(s)\n${s.errors} com erro${s.other?`\n${s.other} outro(s)`:''}${detail}`;

  toast(s.title);

  if(s.kind==="error"||s.kind==="partial"){
    alert(summary);
  }

  if(page==="merge" && s.errors){
    let reviewBtn=document.querySelector('nav button[data-page="review"]');
    if(reviewBtn){
      reviewBtn.classList.add("attention");
      reviewBtn.title=`${s.errors} capítulo(s) precisam de tratamento`;
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
  if(!confirm("Finalizar a Central de Processamento e voltar ao menu do terminal?")) return;
  try{
    await api("/api/shutdown");
    document.body.innerHTML='<div style="min-height:100vh;display:grid;place-items:center;background:#0d1118;color:#eef2f7;font:14px system-ui"><div style="text-align:center"><h2>Central de Processamento finalizada</h2><p style="color:#94a0b4">Você pode fechar esta aba. O menu do terminal será retomado.</p></div></div>';
  }catch(e){
    toast("Servidor finalizado.");
  }
}
