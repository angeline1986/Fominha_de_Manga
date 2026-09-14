(() => {
  let state=null,sourceFilter="all",query="",pageIndex=1,selectedKey=null,selectedPage=-1,chapterOpen=false,compareOpen=false,zoom=100,flagging=false,level3State=null,level3SelectedKey=null,level3Loading=false,level3Zoom=100,level3Analysis=null,level3Analyzing=false,level3Syncing=false;
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
  function filteredRows(){
    let rows=Array.isArray(state?.rows)?state.rows:[];
    if(sourceFilter!=="all")rows=rows.filter(x=>String(x.source_stage).toLowerCase()===sourceFilter);
    const q=String(query||"").trim().toLowerCase();
    if(q)rows=rows.filter(x=>String(x.chapter).toLowerCase().includes(q));
    return rows;
  }
  function tableSection(){
    const all=filteredRows();
    const pages=Math.max(1,Math.ceil(all.length/PAGE_SIZE));
    pageIndex=Math.min(Math.max(1,pageIndex),pages);
    const visible=all.slice((pageIndex-1)*PAGE_SIZE,pageIndex*PAGE_SIZE);
    const rows=visible.map(x=>`<tr class="${String(x.key)===String(selectedKey)?"toc-row-active":""}" onclick="TextOffCompareUI.selectChapter('${escLocal(x.key)}')">
      <td><button class="toc-chapter-link" type="button">${escLocal(x.chapter)}</button></td><td>${escLocal(x.source)}</td><td>${Number(x.pages||0)}</td><td>${escLocal(formatDate(x.processed_at))}</td><td><span class="toc-status">Concluído</span></td>
    </tr>`).join("");
    const pager=`<div class="table-pager"><span>${all.length?((pageIndex-1)*PAGE_SIZE+1):0}–${Math.min(pageIndex*PAGE_SIZE,all.length)} de ${all.length}</span><div><button class="btn" ${pageIndex<=1?"disabled":""} onclick="TextOffCompareUI.changePage(-1)">&lt;&lt;</button><span class="page-indicator">${pageIndex} / ${pages}</span><button class="btn" ${pageIndex>=pages?"disabled":""} onclick="TextOffCompareUI.changePage(1)">&gt;&gt;</button></div></div>`;
    return `<div class="toolbar standard-filterbar toc-filterbar"><input class="search" placeholder="Buscar capítulo..." value="${escLocal(query)}" oninput="TextOffCompareUI.setQuery(this.value)"><div class="status-filter" role="group" aria-label="Filtrar fonte"><button class="tab ${sourceFilter==="all"?"active":""}" onclick="TextOffCompareUI.setSource('all')">Todas</button><button class="tab ${sourceFilter==="original"?"active":""}" onclick="TextOffCompareUI.setSource('original')">Original</button><button class="tab ${sourceFilter==="merged"?"active":""}" onclick="TextOffCompareUI.setSource('merged')">Merged</button></div></div><div class="panel toc-table-panel"><table class="toc-table"><thead><tr><th>CAP.</th><th>FONTE</th><th>PÁGINAS</th><th>PROCESSADO EM</th><th>STATUS</th></tr></thead><tbody>${rows||'<tr><td colspan="5" class="toc-empty">Nenhum resultado do Cleaner V2 encontrado.</td></tr>'}</tbody></table>${pager}</div>`;
  }
  function chapterSection(){
    const row=currentRow();
    if(!row)return `<section class="bal-section toc-section disabled"><div class="bal-section-head"><span>Selecione um capítulo</span><span class="bal-section-head-right"><small>—</small><i class="bal-chevron">▶</i></span></div></section>`;
    const items=Array.isArray(row.items)?row.items:[];
    const buttons=items.map((x,i)=>`<button type="button" class="toc-page-btn ${i===selectedPage?"active":""}" onclick="TextOffCompareUI.selectImage(${i})">${escLocal(x.source_file)}</button>`).join("");
    return `<section class="bal-section toc-section"><button class="bal-section-head" type="button" onclick="TextOffCompareUI.toggleChapter()" aria-expanded="${chapterOpen}"><span>Cap. ${escLocal(row.chapter)}</span><span class="bal-section-head-right"><small>${escLocal(row.source)} · ${items.length} página(s)</small><i class="bal-chevron">${chapterOpen?"▼":"▶"}</i></span></button>${chapterOpen?`<div class="bal-section-body"><div class="toc-picker-label">Selecione a página que deseja comparar</div><div class="toc-page-grid">${buttons}</div></div>`:""}</section>`;
  }
  function comparisonSection(){
    const row=currentRow();
    const items=Array.isArray(row?.items)?row.items:[];
    const item=selectedPage>=0?items[selectedPage]:null;
    const zoomControls=item?`<div class="bal-zoom-row toc-zoom-row"><span class="bal-zoom-control" aria-label="Controle de zoom sincronizado"><button type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeZoom(-10)" ${zoom<=30?"disabled":""} aria-label="Diminuir zoom">−</button><b class="bal-zoom-value">${zoom}%</b><button type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeZoom(10)" ${zoom>=200?"disabled":""} aria-label="Aumentar zoom">+</button><button type="button" class="bal-zoom-reset" onclick="TextOffCompareUI.resetZoom()" ${zoom===100?"disabled":""}>100%</button></span></div>`:"";
    const flagged=item?.level3_status==="PENDENTE_NIVEL3";
    const correctionAction=item?`<div class="toc-correction-row"><button class="btn toc-correction-btn ${flagged?"is-flagged":""}" type="button" onclick="TextOffCompareUI.flagCorrection()" ${flagged||flagging?"disabled":""}>${flagged?"✓ Correção sinalizada":(flagging?"Sinalizando…":"Sinalizar correção")}</button></div>`:"";
    const body=item?`<div class="bal-section-body">${zoomControls}<div class="toc-compare-caption">Cap. ${escLocal(row.chapter)} · ${escLocal(item.source_file)}</div>${correctionAction}<div class="toc-compare-grid"><article class="toc-preview-card"><div class="toc-preview-head"><strong>ORIGINAL</strong><span>${escLocal(row.source==="Merged"?"Fonte: MERGE":"Fonte: IMG")}</span></div><div class="toc-preview-stage"><img src="${mediaUrl("textoff_source",row,item.source_file)}" alt="Original · ${escLocal(item.source_file)}" style="width:${zoom}%;max-width:none;height:auto"></div></article><article class="toc-preview-card"><div class="toc-preview-head"><strong>TEXTO OFF</strong><span>Cleaner V2</span></div><div class="toc-preview-stage"><img src="${mediaUrl("textoff_clean",row,item.clean_file)}" alt="Texto Off · ${escLocal(item.clean_file)}" style="width:${zoom}%;max-width:none;height:auto"></div></article></div><div class="toc-pager"><button class="btn" type="button" onclick="TextOffCompareUI.moveImage(-1)" ${selectedPage<=0?"disabled":""}>‹ Página anterior</button><span>${selectedPage+1} de ${items.length}</span><button class="btn" type="button" onclick="TextOffCompareUI.moveImage(1)" ${selectedPage>=items.length-1?"disabled":""}>Próxima página ›</button></div></div>`:"";
    return `<section class="bal-section toc-section ${!row?"disabled":""}"><button class="bal-section-head" type="button" onclick="TextOffCompareUI.toggleCompare()" aria-expanded="${compareOpen}" ${!row?"disabled":""}><span>Comparação das imagens</span><span class="bal-section-head-right"><small>${item?"1 selecionada":"Nenhuma selecionada"}</small><i class="bal-chevron">${compareOpen?"▼":"▶"}</i></span></button>${compareOpen?body:""}</section>`;
  }
  function bindSynchronizedScroll(){
    const stages=[...document.querySelectorAll(".toc-compare-grid .toc-preview-stage")];
    if(stages.length!==2)return;
    let syncing=false;
    const sync=(source,target)=>{
      if(syncing)return;
      syncing=true;
      const sourceMaxY=Math.max(0,source.scrollHeight-source.clientHeight);
      const targetMaxY=Math.max(0,target.scrollHeight-target.clientHeight);
      const sourceMaxX=Math.max(0,source.scrollWidth-source.clientWidth);
      const targetMaxX=Math.max(0,target.scrollWidth-target.clientWidth);
      const ratioY=sourceMaxY?source.scrollTop/sourceMaxY:0;
      const ratioX=sourceMaxX?source.scrollLeft/sourceMaxX:0;
      target.scrollTop=ratioY*targetMaxY;
      target.scrollLeft=ratioX*targetMaxX;
      requestAnimationFrame(()=>{syncing=false});
    };
    stages[0].addEventListener("scroll",()=>sync(stages[0],stages[1]),{passive:true});
    stages[1].addEventListener("scroll",()=>sync(stages[1],stages[0]),{passive:true});
  }
  function renderBody(){const host=document.querySelector("#textOffCompareBody");if(host){host.innerHTML=tableSection()+`<div class="toc-detail-stack">${chapterSection()}${comparisonSection()}</div>`;bindSynchronizedScroll()}}
  async function load(){try{state=await api(`/api/textoff-compare?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&_=${Date.now()}`);renderBody()}catch(e){toast(e.message||"Não foi possível carregar os resultados do Texto Off.")}}
  function render(root){root.innerHTML=head("Comparar resultados","Compare as imagens antes e depois da limpeza realizada pelo Cleaner V2.")+`<div id="textOffCompareBody"><div class="muted">Carregando resultados do Texto Off…</div></div>`;state=null;sourceFilter="all";query="";pageIndex=1;selectedKey=null;selectedPage=-1;chapterOpen=false;compareOpen=false;zoom=100;load()}
  function selectChapter(key){selectedKey=String(key);selectedPage=-1;chapterOpen=true;compareOpen=false;zoom=100;renderBody()}
  function selectImage(index){const items=Array.isArray(currentRow()?.items)?currentRow().items:[];selectedPage=Math.max(0,Math.min(Number(index)||0,items.length-1));compareOpen=true;renderBody();requestAnimationFrame(()=>document.querySelector(".toc-detail-stack .toc-section:last-child")?.scrollIntoView({behavior:"smooth",block:"start"}))}
  function moveImage(delta){const items=Array.isArray(currentRow()?.items)?currentRow().items:[];if(!items.length)return;selectedPage=Math.max(0,Math.min(items.length-1,selectedPage+Number(delta||0)));renderBody()}
  function toggleChapter(){if(currentRow()){chapterOpen=!chapterOpen;renderBody()}}
  function toggleCompare(){if(currentRow()&&selectedPage>=0){compareOpen=!compareOpen;renderBody()}}
  function changeZoom(delta){zoom=Math.max(30,Math.min(200,zoom+Number(delta||0)));renderBody()}
  function resetZoom(){zoom=100;renderBody()}
  function setQuery(value){query=String(value||"");pageIndex=1;renderBody()}
  function setSource(value){sourceFilter=String(value||"all");pageIndex=1;renderBody()}
  function changePage(delta){pageIndex=Math.max(1,pageIndex+Number(delta||0));renderBody()}
  const level3Current=()=>level3State?.rows?.find(x=>String(x.key)===String(level3SelectedKey))||null;
  function level3MediaUrl(kind,row,file){return `/media?provider=${encodeURIComponent(data.provider)}&manga=${encodeURIComponent(data.manga)}&kind=${encodeURIComponent(kind)}&source=${encodeURIComponent(row.source_stage)}&chapter=${encodeURIComponent(row.chapter)}&file=${encodeURIComponent(file)}`;}
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
    return `<section class="panel toc-level3-detail"><div class="toc-level3-detail-head"><div><span class="caption">PENDÊNCIA SELECIONADA</span><h2>Cap. ${escLocal(row.chapter)} · ${escLocal(row.source_file)}</h2></div><span class="toc-status toc-status-pending">Pendente</span></div><div class="toc-level3-toolbar"><div class="toc-level3-zoom"><button type="button" onclick="TextOffCompareUI.setLevel3Zoom(${level3Zoom-10})">−</button><span>${level3Zoom}%</span><button type="button" onclick="TextOffCompareUI.setLevel3Zoom(${level3Zoom+10})">+</button><button type="button" onclick="TextOffCompareUI.setLevel3Zoom(100)">100%</button></div></div><div class="toc-compare-grid toc-level3-grid"><article class="toc-preview-card"><div class="toc-preview-head"><strong>ORIGINAL</strong><span>${row.source_stage==="MERGE"?"Fonte: MERGE":"Fonte: IMG"}</span></div><div class="toc-preview-stage toc-level3-scroll"><div class="toc-level3-image-wrap" style="width:${level3Zoom}%"><img src="${level3MediaUrl("textoff_source",row,row.source_file)}" alt="Original"></div></div></article><article class="toc-preview-card"><div class="toc-preview-head"><strong>RESULTADO ATUAL</strong><span>Texto Off</span></div><div class="toc-preview-stage toc-level3-scroll"><div class="toc-level3-image-wrap" style="width:${level3Zoom}%"><img src="${level3MediaUrl("textoff_clean",row,row.clean_file)}" alt="Resultado atual">${level3Boxes()}</div></div></article></div><div class="toc-level3-actions"><div><strong>Próxima etapa</strong><span>Análise conservadora de resíduos em balões uniformes.</span>${note?`<span class="toc-level3-analysis-note">${note}</span>`:""}</div><button class="btn primary" type="button" ${level3Analyzing?"disabled":""} onclick="TextOffCompareUI.analyzeLevel3()">${level3Analyzing?"Analisando…":"Analisar resíduos"}</button></div></section>`;
  }
  function renderLevel3Body(){
    const host=document.querySelector("#textoffLevel3Body");if(!host)return;
    if(level3Loading){host.innerHTML='<div class="muted">Carregando correções sinalizadas…</div>';return}
    const rows=Array.isArray(level3State?.rows)?level3State.rows:[];
    host.innerHTML=`<div class="toc-level3-summary"><div><b>${rows.length}</b><span>${rows.length===1?"imagem pendente":"imagens pendentes"}</span></div></div>${level3Table(rows)}${level3Detail(level3Current())}`;
    requestAnimationFrame(bindLevel3Scroll);
  }
  function renderCorrection(root){
    root.innerHTML=`<div class="head"><div><div class="caption">TEXTO OFF · NÍVEL III</div><div class="page-title-wrap" tabindex="0"><h1>Correção assistida</h1><span class="page-title-tooltip" role="tooltip">Revise as páginas sinalizadas antes de qualquer correção.</span></div></div></div><div id="textoffLevel3Body"></div>`;
    level3State=null;level3SelectedKey=null;loadLevel3();
  }
  function selectLevel3(key){level3SelectedKey=key;level3Analysis=null;renderLevel3Body()}
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
    renderLevel3Body();
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
      toast(result.count?`${result.count} região(ões) suspeita(s) encontrada(s).`:"Nenhum resíduo seguro foi identificado automaticamente.");
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
          toast("Página sinalizada para correção assistida no Nível III.");
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
  window.TextOffCompareUI={render,renderCorrection,selectChapter,selectImage,moveImage,toggleChapter,toggleCompare,changeZoom,resetZoom,setQuery,setSource,changePage,flagCorrection,selectLevel3,setLevel3Zoom,analyzeLevel3};
})();