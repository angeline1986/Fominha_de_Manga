// Check-only Reset: optimistic version guard, explicit confirmation, reload callback.
import { invalidateCleanerOverview } from "/_app/state/cleaner_revision.js";

export function bindRestoreMergePreview(root,getSelection,onRestored) {
  const button=document.createElement('button');
  button.type='button';button.className='btn comparison-restore-merge';
  button.textContent='Reset';button.disabled=true;root.append(button);
  const dialog=document.createElement('dialog');dialog.className='comparison-restore-preview';
  dialog.setAttribute('aria-labelledby','restore-merge-title');
  dialog.innerHTML=`<div class="restore-preview-header"><div>
    <span class="restore-preview-eyebrow">PROCESSAMENTO</span>
    <h2 id="restore-merge-title">Restaurar página?</h2></div>
    <button type="button" class="restore-preview-close" data-cancel aria-label="Fechar">&times;</button></div>
    <p>A página selecionada será substituída pela versão original do MERGE no Auto-Cleaner Check.</p>
    <p class="restore-preview-status" data-reset-status role="status" aria-live="polite"></p>
    <div class="restore-preview-actions"><button type="button" data-cancel>Cancelar</button>
    <button type="button" data-confirm disabled>Confirmar</button></div>`;
  root.closest('.comparison-screen')?.append(dialog);
  const status=dialog.querySelector('[data-reset-status]');
  const confirm=dialog.querySelector('[data-confirm]');
  const cancels=[...dialog.querySelectorAll('[data-cancel]')];
  let controller=null,revision=0,pending=null,disposed=false,busy=false;
  function abort(){revision++;controller?.abort();controller=null;pending=null;confirm.disabled=true;}
  function close(){if(busy)return;abort();if(dialog.open)dialog.close();}
  cancels.forEach(el=>el.addEventListener('click',close));
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();else abort();});
  dialog.addEventListener('close',()=>{if(!busy)abort();});
  async function open(){
    const selection=getSelection(),page=selection?.page?.name,ctx=selection?.context;
    if(!page||!ctx?.provider||!ctx?.manga||!ctx?.chapter||busy)return;
    abort();const token=revision;controller=new AbortController();
    const payload={provider:ctx.provider,manga:ctx.manga,chapter:String(ctx.chapter),page};
    status.textContent='Verificando a página…';dialog.showModal();
    try {
      const res=await fetch(`/api/textoff/check/reset-merge/preflight?${new URLSearchParams(payload)}`,
        {signal:controller.signal,cache:'no-store'});
      const data=await res.json();
      if(token!==revision||disposed||!dialog.open)return;
      if(!res.ok||!data.can_apply)throw new Error(data.error||'Reset indisponível.');
      if(data.page!==page||String(data.chapter)!==payload.chapter)throw new Error('Página divergente.');
      if(data.already_restored){status.textContent='Esta página já corresponde ao MERGE.';return;}
      pending={...payload,version:data.version,confirmed:true};
      status.textContent='A substituição afetará somente o Check. Outras etapas serão preservadas.';
      confirm.disabled=false;
    }catch(err){if(err.name!=='AbortError'&&token===revision)status.textContent=err.message;}
  }
  async function apply(){
    if(!pending||busy)return;
    const payload=pending;
    busy=true;confirm.disabled=true;
    cancels.forEach(el=>el.disabled=true);
    status.textContent='Restaurando página no Check…';
    try{
      const res=await fetch('/api/textoff/check/reset-merge',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data=await res.json();
      if(!res.ok||!['restored','already_restored'].includes(data.status))throw new Error(data.error||'Reset não concluído.');
      status.textContent='Página restaurada. Atualizando comparação…';
      await onRestored?.();
      busy=false;close();
    }catch(err){status.textContent=`Não foi possível concluir: ${err.message}`;}
    finally{invalidateCleanerOverview(payload.provider,payload.manga);
      busy=false;cancels.forEach(el=>el.disabled=false);}
  }
  button.addEventListener('click',open);confirm.addEventListener('click',apply);
  return {setReady(value){button.disabled=!value;if(!value)close();},
    dispose(){disposed=true;controller?.abort();button.remove();dialog.remove();}};
}
