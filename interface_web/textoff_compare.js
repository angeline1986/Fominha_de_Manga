(() => {
  let state=null,sourceFilter="all",query="",pageIndex=1,selectedKey=null,selectedPage=-1,chapterOpen=false,compareOpen=false,zoom=100;
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
    const body=item?`<div class="bal-section-body">${zoomControls}<div class="toc-compare-caption">Cap. ${escLocal(row.chapter)} · ${escLocal(item.source_file)}</div><div class="toc-compare-grid"><article class="toc-preview-card"><div class="toc-preview-head"><strong>ORIGINAL</strong><span>${escLocal(row.source==="Merged"?"Fonte: MERGE":"Fonte: IMG")}</span></div><div class="toc-preview-stage"><img src="${mediaUrl("textoff_source",row,item.source_file)}" alt="Original · ${escLocal(item.source_file)}" style="width:${zoom}%;max-width:none;height:auto"></div></article><article class="toc-preview-card"><div class="toc-preview-head"><strong>TEXTO OFF</strong><span>Cleaner V2</span></div><div class="toc-preview-stage"><img src="${mediaUrl("textoff_clean",row,item.clean_file)}" alt="Texto Off · ${escLocal(item.clean_file)}" style="width:${zoom}%;max-width:none;height:auto"></div></article></div><div class="toc-pager"><button class="btn" type="button" onclick="TextOffCompareUI.moveImage(-1)" ${selectedPage<=0?"disabled":""}>‹ Página anterior</button><span>${selectedPage+1} de ${items.length}</span><button class="btn" type="button" onclick="TextOffCompareUI.moveImage(1)" ${selectedPage>=items.length-1?"disabled":""}>Próxima página ›</button></div></div>`:"";
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
  window.TextOffCompareUI={render,selectChapter,selectImage,moveImage,toggleChapter,toggleCompare,changeZoom,resetZoom,setQuery,setSource,changePage};
})();