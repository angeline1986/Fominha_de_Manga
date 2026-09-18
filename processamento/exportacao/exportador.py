from __future__ import annotations
import hashlib, os, shutil, subprocess, tempfile, threading, uuid
from pathlib import Path

_PLAN_LOCK=threading.Lock()
_PLANS={}
CONTENT={
 "textoff_merged":{"label":"Texto Off — MERGED","source":("FLUXO_SECUNDARIO","04_TEXTO_OFF","MERGED"),"dest":"raws_semi-clean"},
 "pdf_merge":{"label":"PDF_MERGE","source":("FLUXO_SECUNDARIO","03_PDF_MERGE"),"dest":"Traducoes"},
}

def _excluded(p):
    return p.name==".DS_Store" or p.suffix.lower()==".json" or p.name.lower().endswith("_mask.png")

def _sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def _destination(raw):
    v=os.path.expandvars(os.path.expanduser(str(raw or "").strip()))
    if not v: raise ValueError("Selecione uma pasta de destino.")
    p=Path(v).resolve()
    if not p.is_dir(): raise ValueError("A pasta de destino não existe ou não está acessível.")
    if not os.access(p,os.W_OK): raise ValueError("A pasta de destino não permite gravação.")
    return p

def _work_destination(parent, manga):
    name=Path(manga).name
    if not name or name in {".",".."}: raise ValueError("Nome da obra inválido.")
    return (parent/name).resolve()

def display_path(path):
    p=str(Path(path))
    marker="/Meu Drive/"
    if marker in p: return "Meu Drive/"+p.split(marker,1)[1]
    home=str(Path.home())
    if p==home: return "~"
    if p.startswith(home+"/"): return "~/"+p[len(home)+1:]
    return p

def _keys(selected):
    out=[]
    for raw in selected or []:
        k=str(raw)
        if k not in CONTENT: raise ValueError(f"Conteúdo de exportação inválido: {k}")
        if k not in out: out.append(k)
    if not out: raise ValueError("Selecione pelo menos um conteúdo para exportar.")
    return out

def _discover(manga,selected,work_dest):
    files=[]; summary={}
    for key in selected:
        cfg=CONTENT[key]; base=manga.joinpath(*cfg["source"]).resolve()
        counts={"new":0,"identical":0,"conflict":0}; size=0
        if base.is_dir():
            for src in sorted(base.rglob("*")):
                if not src.is_file() or _excluded(src): continue
                rel=Path(cfg["dest"])/src.relative_to(base)
                target=(work_dest/rel).resolve()
                st=src.stat(); src_hash=_sha256(src)
                status="new"
                if target.is_file():
                    status="identical" if target.stat().st_size==st.st_size and _sha256(target)==src_hash else "conflict"
                item={"kind":key,"source":str(src),"relative":str(rel),"size":int(st.st_size),
                      "mtime_ns":int(st.st_mtime_ns),"sha256":src_hash,"status":status}
                files.append(item); counts[status]+=1; size+=item["size"]
        summary[key]={"label":cfg["label"],"files":sum(counts.values()),"bytes":size,"available":base.is_dir(),**counts}
    return files,summary

def simulate_export(manga,destination,selected):
    manga=Path(manga).resolve(); parent=_destination(destination); work_dest=_work_destination(parent,manga.name); keys=_keys(selected)
    files,summary=_discover(manga,keys,work_dest)
    if not files: raise ValueError("Nenhum arquivo elegível foi encontrado para os conteúdos selecionados.")
    pid=uuid.uuid4().hex
    plan={"id":pid,"manga":str(manga),"destination_parent":str(parent),"destination":str(work_dest),
          "selected":keys,"files":files,"summary":summary}
    with _PLAN_LOCK: _PLANS[pid]=plan
    new=sum(x["status"]=="new" for x in files); identical=sum(x["status"]=="identical" for x in files); conflicts=sum(x["status"]=="conflict" for x in files)
    return {"ok":True,"plan_id":pid,"destination_parent":str(parent),"destination":str(work_dest),
            "destination_display":display_path(work_dest),"selected":keys,"summary":summary,
            "total_files":len(files),"total_bytes":sum(x["size"] for x in files),
            "new_files":new,"identical_files":identical,"conflicts":conflicts,
            "already_exported":new==0 and conflicts==0 and identical>0,
            "can_export":new>0 and conflicts==0,
            "exclusions":["*_mask.png","*.json",".DS_Store"]}

def _copy_atomic(src,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp_name=tempfile.mkstemp(prefix=f".{target.name}.",suffix=".tmp",dir=str(target.parent)); os.close(fd)
    tmp=Path(tmp_name)
    try:
        shutil.copy2(src,tmp); os.replace(tmp,target)
    finally:
        if tmp.exists(): tmp.unlink()

def execute_plan(manga,plan_id):
    with _PLAN_LOCK: plan=_PLANS.get(str(plan_id))
    if not plan: raise ValueError("A simulação não é mais válida. Simule novamente.")
    manga=Path(manga).resolve()
    if str(manga)!=plan["manga"]: raise ValueError("A obra mudou desde a simulação. Simule novamente.")
    parent=_destination(plan["destination_parent"]); work_dest=_work_destination(parent,manga.name)
    if str(work_dest)!=plan["destination"]: raise ValueError("O destino mudou desde a simulação. Simule novamente.")
    current,_=_discover(manga,plan["selected"],work_dest)
    sig=lambda xs:{(x["kind"],x["relative"]):(x["size"],x["mtime_ns"],x["sha256"],x["status"]) for x in xs}
    if sig(current)!=sig(plan["files"]): raise ValueError("A origem ou o destino mudou desde a simulação. Simule novamente.")
    conflicts=[x for x in current if x["status"]=="conflict"]
    if conflicts: raise ValueError(f"Existem {len(conflicts)} conflito(s). Nenhum arquivo foi sobrescrito.")
    new=[x for x in current if x["status"]=="new"]
    if not new: raise ValueError("Esta obra já está exportada e atualizada neste destino.")
    copied=0; copied_bytes=0
    work_dest.mkdir(parents=True,exist_ok=True)
    for item in new:
        src=Path(item["source"]).resolve(); rel=Path(item["relative"])
        if rel.is_absolute() or ".." in rel.parts or _excluded(src): raise ValueError("Plano contém caminho inválido.")
        target=(work_dest/rel).resolve()
        if not target.is_relative_to(work_dest): raise ValueError("Destino calculado fora da pasta da obra.")
        _copy_atomic(src,target); copied+=1; copied_bytes+=item["size"]
    with _PLAN_LOCK: _PLANS.pop(str(plan_id),None)
    return {"ok":True,"destination":str(work_dest),"destination_display":display_path(work_dest),
            "copied":copied,"unchanged":len(current)-copied,"total_files":len(current),
            "copied_bytes":copied_bytes,"preserved_destination_files":True}

def select_directory():
    proc=subprocess.run(["osascript","-e",'POSIX path of (choose folder with prompt "Escolha a pasta-pai de destino da exportação")'],
                        capture_output=True,text=True,check=False)
    if proc.returncode:
        msg=(proc.stderr or "").strip()
        if "User canceled" in msg or "-128" in msg: return {"ok":True,"cancelled":True}
        raise RuntimeError(msg or "Não foi possível abrir o seletor de pasta.")
    path=str(_destination(proc.stdout.strip()))
    return {"ok":True,"cancelled":False,"path":path,"display":display_path(path)}
