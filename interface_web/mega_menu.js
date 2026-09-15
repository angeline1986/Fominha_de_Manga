(() => {
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const icons={
    overview:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h7v6H4zM13 5h7v6h-7zM4 13h7v6H4zM13 13h7v6h-7z"/>',
    list:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h10"/>',
    eye:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.5 12C4 8 7.5 5 12 5s8 3 9.5 7c-1.5 4-5 7-9.5 7S4 16 2.5 12z"/><circle cx="12" cy="12" r="3" stroke-width="2"/>',
    merge:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/>',
    check:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12l4 4L19 6"/>',
    edit:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 20h4L19 9l-4-4L4 16v4z"/>',
    scissors:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 14l5 5M14 10l5-5M4 7a3 3 0 106 0 3 3 0 00-6 0zm0 10a3 3 0 106 0 3 3 0 00-6 0zM9 9l5 5M9 15l5-5"/>',
    pdf:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 3h7l5 5v13H7zM14 3v6h5"/>',
    text:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"/>',
    scale:'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5 5 0 006 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5 5 0 006 0M18 7l3 9m-3-9l-6-2m0-2v18"/>'
  };
  const sw=p=>`<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">${p}</svg>`;
  const legacy=$('#legacyNavSource'), mega=$('#fominhaMegaMenu'), inner=$('#fominhaMegaInner'), overlay=$('#fominhaMegaOverlay'), content=$('#fominhaMegaContent');
  const title=$('#fominhaMegaTitle'), subtitle=$('#fominhaMegaSubtitle'), titleIcon=$('#fominhaMegaTitleIcon'), closeBtn=$('#fominhaMegaClose');
  const side=$$('.fm-sidebar-item[data-panel]');
  if(!legacy||!mega||!inner||!overlay||!content)return;
  let openKey=null,lastAnchor=null,swapTimer=null,hoverCloseTimer=null;
  const HOVER_CLOSE_DELAY=600;

  function cancelHoverClose(){
    clearTimeout(hoverCloseTimer);
    hoverCloseTimer=null;
  }

  function scheduleHoverClose(){
    cancelHoverClose();
    hoverCloseTimer=setTimeout(()=>{
      hoverCloseTimer=null;
      if(mega.matches(':hover') || side.some(x=>x.matches(':hover')))return;
      closePanel();
    },HOVER_CLOSE_DELAY);
  }

  const legacyButtons=()=>$$('button[data-page]',legacy);
  const legacyButton=page=>legacy.querySelector(`button[data-page="${CSS.escape(page)}"]`);
  const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
  const pageByText=(...terms)=>{const ts=terms.map(norm);for(const b of legacyButtons()){const t=norm(b.textContent);if(ts.some(x=>t.includes(x)))return b.dataset.page}return null};
  function clickPage(page){const b=legacyButton(page);if(!b)return false;b.click();closePanel();return true}

  function moveGlobalActions(){
    const host=$('#fmGlobalActionsHost'), oldAside=$('aside',legacy); if(!host||!oldAside)return;
    const actions=$('.sidebar-actions',oldAside), stop=$('.server-stop-wrap',oldAside);
    if(actions)host.appendChild(actions); if(stop)host.appendChild(stop);
  }
  function contextParking(){
    let parking=$('#fmWorkContextParking');
    if(!parking){
      parking=document.createElement('div');
      parking.id='fmWorkContextParking';
      parking.hidden=true;
      document.body.appendChild(parking);
    }
    return parking;
  }
  function parkContext(){
    const provider=$('#provider'), manga=$('#manga');
    if(!provider||!manga)return;
    const pl=provider.closest('label'), ml=manga.closest('label');
    if(!pl||!ml)return;
    contextParking().append(pl,ml);
  }
  function moveContext(){
    const host=$('#fmWorkContextHost'), provider=$('#provider'), manga=$('#manga'); if(!host||!provider||!manga)return;
    const pl=provider.closest('label'), ml=manga.closest('label'); if(!pl||!ml)return;
    pl.classList.add('fm-context-field');ml.classList.add('fm-context-field');host.append(pl,ml);
    const hc=$('.header-context'); if(hc && !hc.children.length)hc.remove();
  }

  function manualRoutes(){
    const cfg=window.FOMINHA_MEGA_MANUAL_ROUTES||{}, pages=legacyButtons().map(b=>b.dataset.page).filter(Boolean), exists=p=>p&&pages.includes(p), first=a=>a.find(exists)||null;
    const validate=cfg.validate||first(['merge_manual','manual_merge','merge_manual_validate','manual_merge_validate'])||pageByText('validar merge manual','validar');
    const cuts=cfg.cuts||first(['merge_manual_cuts','manual_merge_cuts','merge_manual_new_cuts','merge_manual_newcuts'])||pageByText('novos cortes','merge manual');
    return {validate,cuts};
  }

  function manualCutsReady(){
    try{
      const raw=localStorage.getItem('fominha.mergeManual.selection.v1');
      if(!raw)return false;
      const selection=JSON.parse(raw);
      const provider=$('#provider')?.value||'';
      const manga=$('#manga')?.value||'';
      return !!selection
        && selection.provider===provider
        && selection.manga===manga
        && !!selection.chapter
        && !!selection.blockId
        && !!selection.start
        && !!selection.end;
    }catch(_){
      return false;
    }
  }
  function badge(page){
    const map={validate_images:'badgeDimensions',merge_level2:'badgeLevel2',merge_level3:'badgeLevel3',merge_level4:'badgeLevel4',merge_level5:'badgeLevel5',review:'badge',balance:'badgeBalance'};
    const el=document.getElementById(map[page]); if(!el)return''; const n=Number(String(el.textContent||'').replace(/\D+/g,''));
    return Number.isFinite(n)&&n>0?`<span class="fm-mega-badge">${n}</span>`:'';
  }
  function item(page,name,desc,icon,enabled=true){const off=!enabled||!page;return `<button class="fm-mega-item${off?' disabled':''}" ${page?`data-page="${page}"`:''} ${off?'disabled':''}><span class="fm-mega-item-icon">${sw(icon)}</span><span class="fm-mega-item-copy"><span class="fm-mega-item-name">${name}</span><span class="fm-mega-item-desc">${desc}</span></span>${page?badge(page):''}</button>`}
  const col=(name,icon,body)=>`<section class="fm-mega-col"><div class="fm-mega-col-title">${sw(icon)}<span>${name}</span></div>${body}</section>`;

  function buildOverview(){return `<div class="fm-work-context"><div class="fm-work-context-title">Contexto de trabalho</div><div id="fmWorkContextHost" style="display:contents"></div></div><div class="fm-mega-grid">${col('Resumo',icons.overview,item('overview','Visão Geral','Resumo da operação',icons.overview))}${col('Validação',icons.eye,item('validate_images','Validar imagens','Verificar qualidade e dimensões',icons.eye))}${col('Contexto',icons.overview,'<div class="fm-mega-note">Provider e obra definidos aqui permanecem ativos em toda a Central.</div>')}</div>`}
  function buildProcess(){const m=manualRoutes(),cutsReady=manualCutsReady();return `<div class="fm-mega-grid">${col('Auto Merge',icons.merge,[item('merge','Auto Merge','Processamento inicial',icons.merge),item('merge_level2','AM Nível II','Resultados parciais',icons.merge),item('merge_level3','AM Nível III','Tentativa residual',icons.merge),item('merge_level4','AM Nível IV','Processamento dirigido',icons.merge),item('merge_level5','AM Nível V','Classificação residual',icons.merge)].join(''))}${col('Revisão',icons.check,item('review','Revisão Merge','Tratar casos pendentes',icons.check)+item('review_v2','Revisão Merge V2','Fluxo alternativo',icons.edit))}${col('Merge Manual',icons.scissors,item(m.validate,'Validar','Selecionar faixa pendente',icons.eye,!!m.validate)+item(m.cuts,'Novos Cortes','Definir novos pontos de corte e efetivar o MERGE',icons.scissors,!!m.cuts&&cutsReady)+((!m.validate||!m.cuts)?'<div class="fm-mega-note">Rotas do Merge Manual não foram detectadas integralmente. Nenhuma rota foi inventada.</div>':''))}</div>`}
  function buildBalance(){return `<div class="fm-mega-grid">${col('Validação',icons.check,item('balance','Validar','Verificar estado dos merges',icons.eye))}${col('Ajustes',icons.scissors,item('balance_execute','Novos Cortes','Criar novos cortes',icons.scissors))}${col('Contexto',icons.scale,'<div class="fm-mega-note">Somente a navegação foi reorganizada; a lógica de Balanceamento permanece intacta.</div>')}</div>`}
  function buildPdf(){return `<div class="fm-mega-grid">${col('Opções',icons.pdf,item('pdf','Original','Imagens originais',icons.pdf)+item('pdf_merge','Merge','Imagens mescladas',icons.merge))}${col('Contexto',icons.pdf,'<div class="fm-mega-note">A obra ativa é definida em Visão Geral.</div>')}${col('Acesso',icons.pdf,'<div class="fm-mega-note">As rotas atuais de geração de PDF foram preservadas.</div>')}</div>`}
  function buildText(){return `<div class="fm-mega-grid">${col('Fonte',icons.text,item('clean','Original','Imagens originais',icons.text)+item('clean_merged','Merged','Imagens mescladas',icons.merge))}${col('Resultados',icons.eye,item('textoff_compare','Comparar resultados','Original × imagem limpa',icons.eye)+item('textoff_level3','Correção assistida','Tratar imagens sinalizadas',icons.edit))}${col('Acesso',icons.text,'<div class="fm-mega-note">A lógica do Texto Off não foi alterada.</div>')}</div>`}
  const panels={overview:{title:'Visão Geral',sub:'Contexto de trabalho, resumo e validação inicial',icon:icons.overview,build:buildOverview},processamento:{title:'Processamento',sub:'Auto Merge, revisão e Merge Manual',icon:icons.list,build:buildProcess},balanceamento:{title:'Balanceamento',sub:'Validação e novos cortes',icon:icons.scale,build:buildBalance},pdf:{title:'Gerar PDF',sub:'Geração por origem',icon:icons.pdf,build:buildPdf},textooff:{title:'Texto Off',sub:'Limpeza por fonte de imagem',icon:icons.text,build:buildText}};

  const wantedTop=a=>Math.round(a.getBoundingClientRect().top), naturalH=()=>Math.ceil(inner.scrollHeight), fit=(t,h)=>Math.max(12,Math.min(t,Math.max(12,innerHeight-h-14)));
  function geometry(a){requestAnimationFrame(()=>{const h=naturalH();mega.style.top=fit(wantedTop(a),h)+'px';mega.style.height=h+'px'})}
  function render(key){const p=panels[key];title.textContent=p.title;subtitle.textContent=p.sub;titleIcon.innerHTML=sw(p.icon);parkContext();content.innerHTML=p.build();if(key==='overview')moveContext()}
  function openPanel(key,a){if(!panels[key])return;if(openKey===key&&mega.classList.contains('open'))return closePanel();lastAnchor=a;side.forEach(x=>x.classList.toggle('active',x===a));if(!mega.classList.contains('open')){openKey=key;render(key);mega.style.top=wantedTop(a)+'px';mega.style.height='0px';mega.classList.add('open');overlay.classList.add('active');requestAnimationFrame(()=>geometry(a));return}openKey=key;clearTimeout(swapTimer);mega.classList.add('swapping');mega.style.top=wantedTop(a)+'px';swapTimer=setTimeout(()=>{render(key);geometry(a);requestAnimationFrame(()=>requestAnimationFrame(()=>mega.classList.remove('swapping')))},160)}
  function closePanel(){clearTimeout(swapTimer);mega.classList.add('swapping');mega.style.height='0px';setTimeout(()=>{mega.classList.remove('open','swapping');overlay.classList.remove('active');side.forEach(x=>x.classList.remove('active'));openKey=null;lastAnchor=null},300)}
  side.forEach(b=>{
    b.addEventListener('click',()=>openPanel(b.dataset.panel,b));
    b.addEventListener('mouseenter',()=>{
      cancelHoverClose();
      const key=b.dataset.panel;
      if(openKey===key && mega.classList.contains('open'))return;
      openPanel(key,b);
    });
    b.addEventListener('mouseleave',scheduleHoverClose);
  });
  mega.addEventListener('mouseenter',cancelHoverClose);
  mega.addEventListener('mouseleave',scheduleHoverClose);
  closeBtn?.addEventListener('click',closePanel);
  overlay.addEventListener('click',closePanel);
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closePanel()});
  content.addEventListener('click',e=>{const b=e.target.closest('.fm-mega-item[data-page]');if(b&&!b.disabled)clickPage(b.dataset.page)});
  window.addEventListener('resize',()=>{if(openKey&&lastAnchor&&mega.classList.contains('open'))geometry(lastAnchor)});
  moveGlobalActions();
})();
