(() => {
  const PATCHES = {
    degrade: {
      title: "Patch Degradê",
      badge: "ESPECIAL",
      description: "Indicado para balões ou regiões com variação gradual de cor, onde a limpeza simples pode deixar marcas.",
      pipeline: "Cleaner → Balloon Authorization → Surface Gate → Local Heal",
      exampleClass: "degrade"
    },
    estilizado: {
      title: "Patch Balão Estilizado",
      badge: "ESPECIAL",
      description: "Indicado para balões coloridos ou decorados, preservando elementos gráficos enquanto o texto é reconstruído.",
      pipeline: "Cleaner → Classificação automática → Surface Gate → Local Heal",
      exampleClass: "styled"
    },
    transparente: {
      title: "Patch Balão Transparente",
      badge: "ESPECIAL",
      description: "Indicado para balões transparentes ou semitransparentes, quando roupas, cabelos ou cenário continuam visíveis atrás do texto.",
      pipeline: "Cleaner → Máscara 3×3 → Autorização 9×9 → LaMa",
      exampleClass: "transparent"
    },
    gradiente_suave: {
      title: "Gradiente Suave",
      badge: "EXPERIMENTAL",
      description: "Reconstrói gradientes suaves usando o contexto acima e abaixo da seleção.",
      pipeline: "Seleção manual → Expansão 35% → LAB → Mediana → Suavização → Interpolação vertical",
      exampleClass: "degrade"
    }
  };

  let selectedFile = null;
  let selectedSourcePath = "";
  let currentRunId = "";
  let sourceUrl = "";
  let resultUrl = "";
  let busy = false;
  let previewZoom = 100;
  let compareZoom = 100;
  let smoothSelections = [];
  let smoothSelectionSeq = 0;
  let smoothDrag = null;

  const e = s => String(s ?? "").replace(/[&<>"']/g, m => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[m]));

  function currentPatch() {
    return document.querySelector("#specialPatch")?.value || "degrade";
  }

  function revoke(url) {
    if (url && url.startsWith("blob:")) URL.revokeObjectURL(url);
  }

  function resetResult() {
    revoke(resultUrl);
    resultUrl = "";
    currentRunId = "";
    const box = document.querySelector("#specialResult");
    if (box) box.innerHTML = "";
  }

  function exampleHtml(key) {
    const p = PATCHES[key];
    return `
      <div class="special-example-card">
        <div class="special-example-top">
          <div>
            <span class="special-kicker">${e(p.title)}</span>
            <h2>${e(p.title)}</h2>
          </div>
          <span class="special-badge">${e(p.badge)}</span>
        </div>
        <div class="special-example-grid">
          <div class="special-example-visual ${e(p.exampleClass)}">
            <div class="special-mini">
              <span class="special-mini-label">ANTES</span>
              <div class="special-mini-scene"><i></i><b>TEXT</b></div>
            </div>
            <span class="special-arrow">→</span>
            <div class="special-mini">
              <span class="special-mini-label">DEPOIS</span>
              <div class="special-mini-scene clean"><i></i></div>
            </div>
          </div>
          <div class="special-example-copy">
            <b>Quando usar</b>
            <p>${e(p.description)}</p>
            <small>${e(p.pipeline)}</small>
          </div>
        </div>
      </div>`;
  }

  function updatePatch() {
    const host = document.querySelector("#specialExample");
    if (host) host.innerHTML = exampleHtml(currentPatch());
    resetResult();
    smoothSelections=[]; smoothDrag=null; updateSmoothSelectionMode();
  }

  function updateFile() {
    previewZoom = 100;
    const label = document.querySelector("#specialFileName");
    const preview = document.querySelector("#specialPreview");
    const apply = document.querySelector("#specialApply");
    resetResult();
    smoothSelections=[]; smoothDrag=null;
    revoke(sourceUrl);
    sourceUrl = "";

    if (!selectedFile) {
      if (label) label.value = "";
      if (preview) preview.innerHTML = `<div class="special-empty">Nenhuma imagem selecionada</div>`;
      if (apply) apply.disabled = true;
      return;
    }

    sourceUrl = URL.createObjectURL(selectedFile);
    if (label) label.value = selectedFile.name;
    if (preview) preview.innerHTML = `
      <div class="special-preview-head"><div><b>PRÉ-VISUALIZAÇÃO</b><span>${e(selectedFile.name)}</span></div><div class="special-zoom"><button data-z="preview-out">−</button><button data-z="preview-reset"><span id="specialPreviewZoom">100%</span></button><button data-z="preview-in">+</button></div></div>
      <div id="specialPreviewStage" class="special-preview-stage"><div id="specialImageWrap" class="special-image-wrap"><img id="specialPreviewImage" src="${sourceUrl}" alt="Imagem selecionada"></div></div>`;
    wirePreview();
    updateSmoothSelectionMode();
    if (apply) apply.disabled = ["gradiente_suave","degrade"].includes(currentPatch());
  }

  async function choose() {
    try {
      const provider = encodeURIComponent(data?.provider || "");
      const manga = encodeURIComponent(data?.manga || "");
      const r = await api(`/api/textoff-special/select-image?provider=${provider}&manga=${manga}`);
      if (r.cancelled) return;
      const binary = atob(r.content_base64 || "");
      const bytes = new Uint8Array(binary.length);
      for (let i=0; i<binary.length; i++) bytes[i] = binary.charCodeAt(i);
      selectedFile = new File([bytes], r.filename || "imagem.png", {type:r.mime || "image/png"});
      selectedSourcePath = r.path || "";
      updateFile();
    } catch (err) {
      toast(err.message || "Não foi possível escolher a imagem.");
    }
  }

  function fileChanged(input) {
    selectedFile = input.files?.[0] || null;
    selectedSourcePath = "";
    updateFile();
  }

  function toBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("Não foi possível ler a imagem."));
      reader.onload = () => resolve(String(reader.result || ""));
      reader.readAsDataURL(file);
    });
  }

  async function apply() {
    if (!selectedFile || busy) return;
    if(["gradiente_suave","degrade"].includes(currentPatch())&&!smoothSelections.length){toast("Selecione uma ou mais regiões do texto na pré-visualização.");return;}
    busy = true;
    const btn = document.querySelector("#specialApply");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Processando…";
    }

    try {
      const content = await toBase64(selectedFile);
      const response = await api("/api/textoff-special/process", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          patch: currentPatch(),
          provider: data?.provider || "",
          manga: data?.manga || "",
          filename: selectedFile.name,
          source_path: selectedSourcePath,
          content_base64: content,
          selections: smoothSelections.map(({x,y,width,height})=>({x,y,width,height}))
        })
      });

      currentRunId = response.run_id || "";
      const binary = atob(response.content_base64);
      const bytes = new Uint8Array(binary.length);
      for (let i=0; i<binary.length; i++) bytes[i] = binary.charCodeAt(i);
      revoke(resultUrl);
      resultUrl = URL.createObjectURL(new Blob([bytes], {type: response.mime || "image/png"}));

      const p = PATCHES[currentPatch()];
      document.querySelector("#specialResult").innerHTML = `
        <div class="special-result-head">
          <div><span class="special-kicker">RESULTADO</span><h2>Comparação</h2></div>
          <span class="special-success">✓ Processamento concluído</span>
        </div>
        <div class="special-compare-toolbar"><span>Zoom sincronizado</span><div class="special-zoom"><button data-z="compare-out">−</button><button data-z="compare-reset"><span id="specialCompareZoom">100%</span></button><button data-z="compare-in">+</button></div></div>
        <div class="special-result-grid">
          <article><b>ORIGINAL</b><div id="specialOriginalStage" class="special-result-stage special-sync-stage"><img id="specialOriginalImage" src="${sourceUrl}" alt="Original"></div></article>
          <article><b>RESULTADO</b><div id="specialResultStage" class="special-result-stage special-sync-stage"><img id="specialResultImage" src="${resultUrl}" alt="Resultado"></div></article>
        </div>
        <div class="special-result-footer">
          <span>O arquivo original não foi alterado.</span>
          <div>
            <button class="btn" type="button" onclick="TextOffSpecialUI.clearFile()">Escolher outra imagem</button>
            <button class="btn primary" type="button" onclick="TextOffSpecialUI.saveResult('${e(response.result_name)}')">Salvar resultado</button>
          </div>
        </div>`;
      wireCompare();
      toast(`${p.title} concluído.`);
    } catch (err) {
      toast(err.message || "Não foi possível aplicar o tratamento.");
    } finally {
      busy = false;
      if (btn) {
        btn.disabled = !selectedFile;
        btn.textContent = "Aplicar tratamento";
      }
    }
  }

  function setPreviewZoom(v){
    previewZoom=FominhaViewer.setZoom(v,{
      images:"#specialPreviewImage",
      label:"#specialPreviewZoom"
    });
    requestAnimationFrame(renderSmoothSelections);
  }

  function setCompareZoom(v){
    compareZoom=FominhaViewer.setZoom(v,{
      images:["#specialOriginalImage","#specialResultImage"],
      label:"#specialCompareZoom"
    });
  }

  function clearSmoothSelections(){
    smoothSelections=[];
    document.querySelector("#specialImageWrap")?.querySelectorAll(".special-roi-box,.special-roi-remove,.special-roi-draft").forEach(el=>el.remove());
    updateSmoothSelectionMode();
  }
  function removeSmoothSelection(id){smoothSelections=smoothSelections.filter(item=>item.id!==id);renderSmoothSelections();updateSmoothSelectionMode();}
  function renderSmoothSelections(){
    const img=document.querySelector("#specialPreviewImage"),wrap=document.querySelector("#specialImageWrap");
    if(!img||!wrap||!img.naturalWidth||!img.naturalHeight)return;
    wrap.querySelectorAll(".special-roi-box,.special-roi-remove").forEach(el=>el.remove());
    const ir=img.getBoundingClientRect(),wr=wrap.getBoundingClientRect(),sx=ir.width/img.naturalWidth,sy=ir.height/img.naturalHeight,ox=ir.left-wr.left,oy=ir.top-wr.top;
    smoothSelections.forEach((item,index)=>{
      const box=document.createElement("div");box.className="special-roi-box";
      box.style.left=`${ox+item.x*sx}px`;box.style.top=`${oy+item.y*sy}px`;box.style.width=`${item.width*sx}px`;box.style.height=`${item.height*sy}px`;box.innerHTML=`<span>${index+1}</span>`;wrap.appendChild(box);
      const remove=document.createElement("button");remove.type="button";remove.className="special-roi-remove";remove.textContent="×";remove.title=`Remover seleção ${index+1}`;remove.setAttribute("aria-label",remove.title);
      remove.style.left=`${ox+(item.x+item.width)*sx}px`;remove.style.top=`${oy+item.y*sy}px`;remove.onclick=ev=>{ev.preventDefault();ev.stopPropagation();removeSmoothSelection(item.id);};wrap.appendChild(remove);
    });
  }
  function updateSmoothSelectionMode(){
    const wrap=document.querySelector("#specialImageWrap"),apply=document.querySelector("#specialApply");if(!wrap)return;
    const active=["gradiente_suave","degrade"].includes(currentPatch());wrap.classList.toggle("is-selectable",active);
    let help=document.querySelector("#specialRoiHelp");if(!help){help=document.createElement("div");help.id="specialRoiHelp";help.className="special-roi-help";wrap.parentElement?.before(help);}
    if(active){const count=smoothSelections.length;help.innerHTML=`<div><b>Selecione uma ou mais áreas com texto.</b> Clique e arraste o mouse sobre cada texto que deseja remover. Use × para excluir apenas uma seleção.</div><div class="special-roi-summary"><span>${count} ${count===1?"área selecionada":"áreas selecionadas"}</span>${count?'<button id="specialRoiClear" type="button">Limpar todas</button>':""}</div>`;document.querySelector("#specialRoiClear")?.addEventListener("click",clearSmoothSelections);renderSmoothSelections();}
    else{help.textContent="";wrap.querySelectorAll(".special-roi-box,.special-roi-remove,.special-roi-draft").forEach(el=>el.remove());}
    if(apply)apply.disabled=!selectedFile||(active&&!smoothSelections.length);
  }
  function wireSmoothSelection(){
    const img=document.querySelector("#specialPreviewImage"),wrap=document.querySelector("#specialImageWrap");if(!img||!wrap)return;
    const point=ev=>{const r=img.getBoundingClientRect();return{x:Math.max(0,Math.min(r.width,ev.clientX-r.left)),y:Math.max(0,Math.min(r.height,ev.clientY-r.top)),r};};
    const draw=(a,b)=>{let box=wrap.querySelector(".special-roi-draft");if(!box){box=document.createElement("div");box.className="special-roi-box special-roi-draft";wrap.appendChild(box);}const wr=wrap.getBoundingClientRect(),ir=img.getBoundingClientRect(),ox=ir.left-wr.left,oy=ir.top-wr.top;box.style.left=`${ox+Math.min(a.x,b.x)}px`;box.style.top=`${oy+Math.min(a.y,b.y)}px`;box.style.width=`${Math.abs(b.x-a.x)}px`;box.style.height=`${Math.abs(b.y-a.y)}px`;};
    img.onpointerdown=ev=>{if(!["gradiente_suave","degrade"].includes(currentPatch()))return;ev.preventDefault();smoothDrag=point(ev);img.setPointerCapture?.(ev.pointerId);draw(smoothDrag,smoothDrag);};
    img.onpointermove=ev=>{if(smoothDrag&&["gradiente_suave","degrade"].includes(currentPatch()))draw(smoothDrag,point(ev));};
    img.onpointerup=ev=>{if(!smoothDrag||!["gradiente_suave","degrade"].includes(currentPatch()))return;const end=point(ev),start=smoothDrag;smoothDrag=null;img.releasePointerCapture?.(ev.pointerId);wrap.querySelector(".special-roi-draft")?.remove();const l=Math.min(start.x,end.x),t=Math.min(start.y,end.y),width=Math.abs(end.x-start.x),height=Math.abs(end.y-start.y);if(width<3||height<3){updateSmoothSelectionMode();return;}smoothSelections.push({id:++smoothSelectionSeq,x:Math.round(l*img.naturalWidth/end.r.width),y:Math.round(t*img.naturalHeight/end.r.height),width:Math.round(width*img.naturalWidth/end.r.width),height:Math.round(height*img.naturalHeight/end.r.height)});updateSmoothSelectionMode();};
  }

  function wirePreview(){
    const img=document.querySelector("#specialPreviewImage");
    if(!img)return;

    FominhaViewer.bindZoomControls({
      selector:"[data-z^='preview']",
      getZoom:()=>previewZoom,
      setZoom:setPreviewZoom
    });

    img.onload=()=>{setPreviewZoom(previewZoom);wireSmoothSelection();updateSmoothSelectionMode();};
    setPreviewZoom(previewZoom);
    wireSmoothSelection();
  }

  function wireCompare(){
    FominhaViewer.bindZoomControls({
      selector:"[data-z^='compare']",
      getZoom:()=>compareZoom,
      setZoom:setCompareZoom
    });

    setCompareZoom(compareZoom);

    const a=document.querySelector("#specialOriginalStage");
    const b=document.querySelector("#specialResultStage");
    if(!a||!b)return;

    FominhaViewer.syncScroll(a,b);
  }

  async function saveResult(name) {
    if (!resultUrl || !currentRunId || busy) return;
    if (!selectedSourcePath) {
      toast("Para salvar no Texto Off, selecione a imagem pelo botão Escolher para preservar o caminho original.");
      return;
    }
    busy = true;
    try {
      const response = await api("/api/textoff-special/promote", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          provider: data?.provider || "",
          manga: data?.manga || "",
          run_id: currentRunId
        })
      });
      toast(response.message || `Resultado salvo: ${response.output_name || name || "Texto Off"}.`);
    } catch (err) {
      toast(err.message || "Não foi possível salvar o resultado no Texto Off.");
    } finally {
      busy = false;
    }
  }

  function clearFile() {
    selectedFile = null;
    selectedSourcePath = "";
    currentRunId = "";
    const input = document.querySelector("#specialFileInput");
    if (input) input.value = "";
    updateFile();
  }

  function render(root) {
    selectedFile = null;
    selectedSourcePath = "";
    currentRunId = "";
    revoke(sourceUrl); sourceUrl = "";
    revoke(resultUrl); resultUrl = "";
    root.innerHTML = `
      ${head("Tratamentos especiais","Aplique tratamentos específicos quando o Texto Off convencional não produzir o resultado esperado.")}
      <section class="special-card">
        <div class="special-field">
          <label for="specialPatch">Tipo de tratamento</label>
          <select id="specialPatch">
            <option value="degrade">Patch Degradê</option>
            <option value="estilizado">Patch Balão Estilizado</option>
            <option value="transparente">Patch Balão Transparente</option>
            <option value="gradiente_suave">Gradiente Suave</option>
          </select>
        </div>

        <div id="specialExample">${exampleHtml("degrade")}</div>

        <div class="special-field">
          <label>Imagem</label>
          <div class="special-file-row">
            <input id="specialFileName" placeholder="Nenhuma imagem selecionada" readonly>
            <button id="specialChoose" class="btn" type="button">Escolher</button>
            <input id="specialFileInput" type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" hidden>
          </div>
          <small>Selecione uma imagem PNG, JPG, JPEG ou WEBP diretamente do computador.</small>
        </div>

        <div id="specialPreview" class="special-preview">
          <div class="special-empty">Nenhuma imagem selecionada</div>
        </div>

        <div class="special-actions">
          <button id="specialApply" class="btn primary" type="button" disabled>Aplicar tratamento</button>
        </div>

        <section id="specialResult" class="special-result"></section>
      </section>`;

    document.querySelector("#specialPatch").onchange = updatePatch;
    document.querySelector("#specialChoose").onclick = choose;
    document.querySelector("#specialFileInput").onchange = ev => fileChanged(ev.target);
    document.querySelector("#specialApply").onclick = apply;
  }

  window.TextOffSpecialUI = {render, apply, saveResult, clearFile};
})();
