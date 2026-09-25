(() => {
  "use strict";

  let thumbTimer = null;
  let keyboardBound = false;
  let activeModel = null;
  let activeCallbacks = null;
  let sideScrollCleanup = null;
  let sliderScrollCleanup = null;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));

  function zoomControls(model){
    return `<span class="bal-zoom-control toc-qc-zoom" aria-label="Controle de zoom"><button type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeZoom(-10)" ${model.zoom<=30?"disabled":""}>−</button><b id="tocCompareZoomValue" class="bal-zoom-value">${model.zoom}%</b><button type="button" class="bal-zoom-action" onclick="TextOffCompareUI.changeZoom(10)" ${model.zoom>=200?"disabled":""}>+</button><button type="button" class="bal-zoom-reset" onclick="TextOffCompareUI.resetZoom()" ${model.zoom===100?"disabled":""}>↺</button></span>`;
  }

  function imageShell(url, alt, id=""){
    return `<div class="toc-qc-image-shell is-loading"><span class="toc-qc-image-state">Carregando imagem…</span><img ${id?`id="${id}"`:""} class="toc-qc-scale-img" src="${esc(url)}" alt="${esc(alt)}" draggable="false"></div>`;
  }

  function canvas(model){
    if(model.studioMode === "side"){
      return `<div class="toc-qc-side"><figure><figcaption>ORIGINAL</figcaption><div class="toc-qc-image-scroll toc-qc-scroll-left">${imageShell(model.originalUrl,`Original · ${model.sourceFile}`)}</div></figure><figure><figcaption>TEXTO OFF</figcaption><div class="toc-qc-image-scroll toc-qc-scroll-right">${imageShell(model.cleanUrl,`Texto Off · ${model.cleanFile}`)}</div></figure></div>`;
    }
    return `<div id="tocQcSlider" class="toc-qc-slider"><div class="toc-qc-slider-stage"><div class="toc-qc-compare-board" style="--toc-slider:${model.sliderPos}%"><span class="toc-qc-tag original">ORIGINAL</span><span class="toc-qc-tag result">TEXTO OFF</span>${imageShell(model.cleanUrl,`Texto Off · ${model.cleanFile}`,"tocQcClean")}<div class="toc-qc-slider-overlay">${imageShell(model.originalUrl,`Original · ${model.sourceFile}`,"tocQcOriginal")}</div><div class="toc-qc-slider-divider"><span id="tocQcSliderHandle">⇄</span></div></div></div></div>`;
  }

  function render(model){
    if(!model || model.empty){
      return `<section class="toc-qc-studio"><header class="toc-qc-studio-toolbar"><div class="toc-qc-zone toc-qc-zone-left"><button class="btn" type="button" onclick="TextOffCompareUI.backToHub()">← Capítulos</button></div></header><div class="toc-empty">Este capítulo não possui páginas para comparar.</div></section>`;
    }
    const item=model.items[model.selectedPage];
    const pages=model.items.map((x,i)=>`<button type="button" class="toc-qc-page ${i===model.selectedPage?"active":""}" data-page-name="${esc(String(x.source_file).toLowerCase())}" onclick="TextOffCompareUI.selectImage(${i})" onmouseenter="TextOffCompareUI.showThumb(event,${i})" onmouseleave="TextOffCompareUI.hideThumb()"><span>${esc(x.source_file)}</span><b>${i+1}</b></button>`).join("");
    return `<section class="toc-qc-studio"><header class="toc-qc-studio-toolbar"><div class="toc-qc-zone toc-qc-zone-left"><button class="btn" type="button" onclick="TextOffCompareUI.backToHub()">← Capítulos</button><div class="toc-qc-breadcrumb">${esc(model.manga)} › ${esc(model.chapter)} › ${esc(item.source_file)}</div></div><div class="toc-qc-zone toc-qc-zone-center"><div class="toc-qc-mode"><button class="tab ${model.studioMode==="single"?"active":""}" onclick="TextOffCompareUI.setStudioMode('single')">◐ Visão única</button><button class="tab ${model.studioMode==="side"?"active":""}" onclick="TextOffCompareUI.setStudioMode('side')">◫ Lado a lado</button></div>${zoomControls(model)}</div><div class="toc-qc-zone toc-qc-zone-right"><button class="btn toc-correction-btn ${model.flagged?"is-flagged":""}" type="button" onclick="TextOffCompareUI.flagCorrection()" ${model.flagged||model.flagging?"disabled":""}>${model.flagged?"✓ Correção sinalizada":(model.flagging?"Sinalizando…":"🚩 Sinalizar correção")}</button></div></header><div class="toc-qc-workspace"><aside id="tocQcSidebar" class="toc-qc-sidebar"><div class="toc-qc-sidebar-head"><strong>${esc(model.chapter)}</strong><span>${model.items.length} páginas</span></div><div class="toc-qc-sidebar-search"><input class="search" placeholder="Buscar página..." value="${esc(model.pageQuery)}" oninput="TextOffCompareUI.filterStudioPages(this.value)"></div><div class="toc-qc-pages">${pages}</div></aside><main class="toc-qc-canvas">${canvas(model)}</main></div><footer class="toc-qc-pager"><button class="btn" onclick="TextOffCompareUI.moveImage(-1)" ${model.selectedPage<=0?"disabled":""}>◀ Anterior</button><strong>${model.selectedPage+1} / ${model.items.length}</strong><button class="btn" onclick="TextOffCompareUI.moveImage(1)" ${model.selectedPage>=model.items.length-1?"disabled":""}>Próxima ▶</button></footer><div id="compareThumbPopover" class="toc-qc-thumb" hidden><strong id="compareThumbTitle"></strong><span class="toc-qc-thumb-count"></span><div class="toc-qc-thumb-state">Carregando prévia…</div><img alt="Prévia da página" hidden></div></section>`;
  }

  function setImageState(img, stateName){
    if(!img)return;
    const shell=img.closest(".toc-qc-image-shell")||img.parentElement;
    shell?.classList.remove("is-loading","is-ready","is-error"); shell?.classList.add(`is-${stateName}`);
    const msg=shell?.querySelector(".toc-qc-image-state");
    if(msg)msg.textContent=stateName==="error"?"Não foi possível carregar esta imagem.":stateName==="loading"?"Carregando imagem…":"";
  }

  function scaleImage(img, zoom){
    if(!img)return;
    const apply=()=>{if(img.naturalWidth){img.style.width=`${Math.round(img.naturalWidth*zoom/100)}px`;img.style.maxWidth="none";img.style.height="auto";}setImageState(img,"ready")};
    const fail=()=>setImageState(img,"error");
    setImageState(img,"loading"); img.addEventListener("load",apply,{once:true}); img.addEventListener("error",fail,{once:true});
    if(img.complete){if(img.naturalWidth)apply();else fail();}
  }

  function applyZoom(zoom){document.querySelectorAll("#textOffCompareBody .toc-qc-scale-img").forEach(img=>scaleImage(img,zoom));}
  function filterPages(query){const q=String(query||"").trim().toLowerCase();document.querySelectorAll("#textOffCompareBody .toc-qc-page").forEach(btn=>{btn.hidden=!!q&&!String(btn.dataset.pageName||"").includes(q)})}

  function sliderFromPointer(ev){
    const board=document.querySelector("#textOffCompareBody .toc-qc-compare-board"); if(!board)return;
    const r=board.getBoundingClientRect(); const value=Math.max(0,Math.min(100,(ev.clientX-r.left)/Math.max(1,r.width)*100));
    const owned=activeCallbacks?.onSliderPosition?.(value) ?? value; board.style.setProperty("--toc-slider",`${owned}%`);
  }

  function cleanupBindings(){
    if(typeof sideScrollCleanup === "function") sideScrollCleanup();
    if(typeof sliderScrollCleanup === "function") sliderScrollCleanup();
    sideScrollCleanup=null; sliderScrollCleanup=null;
  }

  function bind(model, callbacks={}){
    cleanupBindings();
    activeModel=model; activeCallbacks=callbacks; hideThumb();
    applyZoom(model?.zoom||100); filterPages(model?.pageQuery||"");

    const sliderStage=document.querySelector("#textOffCompareBody #tocQcSlider");
    const handle=document.querySelector("#textOffCompareBody #tocQcSliderHandle");
    const board=document.querySelector("#textOffCompareBody .toc-qc-compare-board");
    const positionHandle=()=>{
      if(!sliderStage||!handle||!board)return;
      const bRect=board.getBoundingClientRect();
      const sRect=sliderStage.getBoundingClientRect();
      const visibleTop=Math.max(bRect.top,sRect.top);
      const visibleBottom=Math.min(bRect.bottom,sRect.bottom);
      if(visibleBottom<=visibleTop)return;
      handle.style.top=`${visibleTop+(visibleBottom-visibleTop)/2-bRect.top}px`;
    };
    if(sliderStage){
      sliderStage.addEventListener("scroll",positionHandle,{passive:true});
      sliderScrollCleanup=()=>sliderStage.removeEventListener("scroll",positionHandle);
      requestAnimationFrame(positionHandle);
    }
    if(sliderStage){
      sliderStage.addEventListener("dragstart",e=>e.preventDefault());
    }

    if(sliderStage&&board){
      let dragging=false;
      let pointerId=null;
      sliderStage.addEventListener("pointerdown",e=>{
        dragging=true;
        pointerId=e.pointerId;
        sliderStage.setPointerCapture?.(e.pointerId);
        sliderFromPointer(e);
      });
      sliderStage.addEventListener("pointermove",e=>{
        if(!dragging||e.pointerId!==pointerId)return;
        sliderFromPointer(e);
        positionHandle();
      });
      const stopSliderDrag=e=>{
        if(!dragging||e.pointerId!==pointerId)return;
        dragging=false;
        if(sliderStage.hasPointerCapture?.(e.pointerId)) sliderStage.releasePointerCapture?.(e.pointerId);
        pointerId=null;
      };
      sliderStage.addEventListener("pointerup",stopSliderDrag);
      sliderStage.addEventListener("pointercancel",stopSliderDrag);
    }

    if(model?.studioMode === "side"){
      const leftScroll=document.querySelector("#textOffCompareBody .toc-qc-scroll-left");
      const rightScroll=document.querySelector("#textOffCompareBody .toc-qc-scroll-right");
      if(leftScroll&&rightScroll&&window.FominhaViewer?.syncScroll){
        sideScrollCleanup=window.FominhaViewer.syncScroll(leftScroll,rightScroll);
      }
    }

    if(!keyboardBound){keyboardBound=true;document.addEventListener("keydown",e=>{if(!document.querySelector("#textOffCompareBody .toc-qc-studio")||e.metaKey||e.ctrlKey||e.altKey)return;const tag=document.activeElement?.tagName;if(tag==="INPUT"||tag==="TEXTAREA")return;if(e.key==="ArrowLeft"){e.preventDefault();hideThumb();window.TextOffCompareUI?.moveImage?.(-1)}else if(e.key==="ArrowRight"){e.preventDefault();hideThumb();window.TextOffCompareUI?.moveImage?.(1)}})}
  }

  function showThumb(ev,index,model=activeModel){
    hideThumb(); const btn=ev?.currentTarget;
    thumbTimer=setTimeout(()=>{const item=model?.items?.[index],pop=document.querySelector("#compareThumbPopover"),sidebar=document.querySelector("#tocQcSidebar");if(!item||!pop||!sidebar||!btn?.isConnected)return;
      const br=btn.getBoundingClientRect(),sr=sidebar.getBoundingClientRect(); pop.querySelector("strong").textContent=item.source_file; pop.querySelector(".toc-qc-thumb-count").textContent=`${index+1}/${model.items.length}`;
      const img=pop.querySelector("img"),state=pop.querySelector(".toc-qc-thumb-state"); img.onload=null;img.onerror=null;img.removeAttribute("src");img.hidden=true;state.hidden=false;state.textContent="Carregando prévia…";
      pop.style.left=`${sr.right+12}px`; pop.hidden=false;
      const cardHeight=pop.offsetHeight||470;
      const maxTop=Math.max(12,window.innerHeight-cardHeight-12);
      pop.style.top=`${Math.max(12,Math.min(br.top-20,maxTop))}px`;
      img.onload=()=>{state.hidden=true;img.hidden=false};img.onerror=()=>{img.hidden=true;state.hidden=false;state.textContent="Prévia indisponível."};img.src=model.thumbUrl(index);
    },100);
  }

  function hideThumb(){clearTimeout(thumbTimer);thumbTimer=null;const pop=document.querySelector("#compareThumbPopover");if(pop){pop.hidden=true;const img=pop.querySelector("img");if(img){img.onload=null;img.onerror=null;img.removeAttribute("src")}}}

  window.TextOffQcStudio={render,bind,applyZoom,filterPages,showThumb,hideThumb};
})();
