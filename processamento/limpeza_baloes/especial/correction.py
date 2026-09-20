"""Texto Off Especial — proposta regional assistida para cor/gradiente/textura.

O preview é isolado. A aprovação explícita promove somente o resultado _clean;
Cleaner V2, Níveis I/II/III, IMG e 02_MERGE não são alterados.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse, hashlib, json, math, os, shutil, subprocess, tempfile, uuid
from PIL import Image, ImageChops

from processamento.limpeza_baloes.especial.state import (
    STATUS_PENDING, _case_dir, _chapter, _clean_dir, _image_name,
    _normalize_stage, _sha256, _source_dir,
)

SCHEMA = "textoff_special_proposal_v1"
STATUS_PROPOSAL = "PROPOSTA_GERADA"
STATUS_APPROVED = "APROVADA"
STATUS_CORRECTED = "CORRIGIDO_ESPECIAL"
SUPPORTED_TYPE = "COLORIDO_GRADIENTE_TEXTURA"
ROOT = Path(__file__).resolve().parents[3]
CLEANER_VENV_PYTHON = ROOT / "processamento" / "limpeza_baloes" / "cleaner_v2" / ".venv" / "bin" / "python"


def _load_json(path: Path, label: str) -> dict:
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: raise ValueError(f"{label} inválido.") from exc
    if not isinstance(data, dict): raise ValueError(f"{label} inválido.")
    return data


def _selection(value: object) -> dict[str,float]:
    if not isinstance(value, dict): raise ValueError("Seleção regional ausente.")
    out={}
    for k in ("left","top","width","height"):
        try: n=float(value.get(k))
        except (TypeError,ValueError): raise ValueError(f"Seleção inválida: {k}.") from None
        if not math.isfinite(n): raise ValueError(f"Seleção inválida: {k}.")
        out[k]=n
    if out["left"]<0 or out["top"]<0 or out["width"]<=0 or out["height"]<=0 or out["left"]+out["width"]>100.000001 or out["top"]+out["height"]>100.000001:
        raise ValueError("Seleção regional ultrapassa os limites da imagem.")
    return out


def _bbox(sel,w,h):
    x1=max(0,min(w,math.floor(sel["left"]*w/100))); y1=max(0,min(h,math.floor(sel["top"]*h/100)))
    x2=max(0,min(w,math.ceil((sel["left"]+sel["width"])*w/100))); y2=max(0,min(h,math.ceil((sel["top"]+sel["height"])*h/100)))
    if x2<=x1 or y2<=y1: raise ValueError("Seleção regional vazia.")
    return x1,y1,x2,y2


def _case(manga,chapter,stage,source_file):
    c=_case_dir(manga,chapter,stage,source_file); mp=c/"special-manifest.json"
    if not mp.is_file(): raise ValueError("Caso especial não encontrado.")
    m=_load_json(mp,"Manifesto do caso especial")
    if m.get("status")!=STATUS_PENDING: raise ValueError("O caso especial não está pendente.")
    if m.get("special_type")!=SUPPORTED_TYPE: raise ValueError("Esta correção está disponível somente para Cor/gradiente/textura.")
    return c,mp,m


def _refs(case_dir:Path, manifest:dict):
    refs=manifest.get("references") or {}
    sp=(case_dir/str(refs.get("source") or "")).resolve(); cp=(case_dir/str(refs.get("current") or "")).resolve(); base=case_dir.resolve()
    if not sp.is_relative_to(base) or not cp.is_relative_to(base) or not sp.is_file() or not cp.is_file(): raise ValueError("Snapshots do caso especial não encontrados.")
    if _sha256(sp)!=str(refs.get("source_sha256") or "") or _sha256(cp)!=str(refs.get("current_sha256") or ""): raise RuntimeError("Snapshots imutáveis do caso especial falharam na validação de integridade.")
    return sp,cp


def proposal_dir(manga:Path,chapter:str,source_stage:str,source_file:str,proposal_id:str)->Path:
    chapter=_chapter(chapter); stage=_normalize_stage(source_stage); source_file=_image_name(source_file,"Imagem fonte")
    pid=str(proposal_id or "").strip()
    if not pid or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in pid): raise ValueError("Identificador da proposta especial inválido.")
    base=(_case_dir(manga,chapter,stage,source_file)/"proposals").resolve(); target=(base/pid).resolve()
    if not target.is_relative_to(base): raise ValueError("Caminho da proposta especial inválido.")
    return target


def generate_preview(manga,chapter,source_stage,source_file,clean_file,selection_raw,base_proposal_id=None):
    chapter=_chapter(chapter); stage=_normalize_stage(source_stage); source_file=_image_name(source_file,"Imagem fonte"); clean_file=_image_name(clean_file,"Imagem limpa")
    case_dir,_,case=_case(manga,chapter,stage,source_file)
    if str(case.get("clean_file") or "")!=clean_file: raise ValueError("Resultado do caso especial divergente.")
    source_ref,current_ref=_refs(case_dir,case)
    source_off=(_source_dir(manga,chapter,stage)/source_file).resolve(); clean_off=(_clean_dir(manga,chapter,stage)/clean_file).resolve()
    if not source_off.is_file() or not clean_off.is_file(): raise ValueError("Artefato oficial atual não encontrado.")
    refs=case["references"]
    if _sha256(source_off)!=refs["source_sha256"] or _sha256(clean_off)!=refs["current_sha256"]: raise RuntimeError("CASO_ESPECIAL_OBSOLETO: os artefatos oficiais mudaram após a sinalização.")
    sel=_selection(selection_raw)
    base_current=current_ref
    base_pid=str(base_proposal_id or "").strip()
    previous_regions=[]
    if base_pid:
        base_dir=proposal_dir(manga,chapter,stage,source_file,base_pid); base_mp=base_dir/"proposal.json"; base_preview=base_dir/"preview.png"
        if not base_mp.is_file() or not base_preview.is_file(): raise ValueError("Prévia especial anterior não encontrada.")
        base_manifest=_load_json(base_mp,"Manifesto da prévia especial anterior")
        if base_manifest.get("schema")!=SCHEMA or base_manifest.get("status")!=STATUS_PROPOSAL or base_manifest.get("proposal_id")!=base_pid: raise ValueError("Prévia especial anterior indisponível.")
        if base_manifest.get("chapter")!=chapter or base_manifest.get("source_stage")!=stage or base_manifest.get("source_file")!=source_file or base_manifest.get("clean_file")!=clean_file: raise ValueError("Prévia especial anterior pertence a outro artefato.")
        if base_manifest.get("official_source_sha256")!=_sha256(source_off) or base_manifest.get("official_clean_sha256")!=_sha256(clean_off): raise RuntimeError("PROPOSTA_ESPECIAL_OBSOLETA: os artefatos oficiais mudaram após a geração da prévia anterior.")
        if _sha256(base_preview)!=base_manifest.get("preview_sha256"): raise RuntimeError("Integridade da prévia especial anterior inválida.")
        base_current=base_preview
        previous_regions=list(base_manifest.get("regions") or [])
        if not previous_regions and base_manifest.get("selection_percent"):
            previous_regions=[{"selection_percent":base_manifest.get("selection_percent"),"bbox_pixels":base_manifest.get("bbox_pixels")}]
    with Image.open(source_ref) as a, Image.open(base_current) as b:
        if a.size!=b.size: raise RuntimeError("Dimensões divergentes entre referências especiais.")
        w,h=b.size
    bbox=_bbox(sel,w,h); pid=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")+"_"+uuid.uuid4().hex[:8]
    root=case_dir/"proposals"; root.mkdir(parents=True,exist_ok=True); final=proposal_dir(manga,chapter,stage,source_file,pid)
    tmp=Path(tempfile.mkdtemp(prefix=".proposal-",dir=str(root))); preview=tmp/"preview.png"; report=tmp/"worker-report.json"
    try:
        if not CLEANER_VENV_PYTHON.is_file(): raise RuntimeError(f"Python isolado do Cleaner V2 não encontrado: {CLEANER_VENV_PYTHON}")
        env=os.environ.copy(); env["PYTHONPATH"]=str(ROOT)+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        cmd=[str(CLEANER_VENV_PYTHON),str(Path(__file__).resolve()),"--worker","--source",str(source_ref),"--current",str(base_current),"--preview",str(preview),"--report",str(report),"--bbox",",".join(map(str,bbox))]
        proc=subprocess.run(cmd,cwd=str(ROOT),env=env,text=True,capture_output=True,check=False)
        if proc.returncode!=0: raise RuntimeError("Falha ao gerar proposta especial: "+((proc.stderr or proc.stdout or "").strip()[-1200:]))
        if not preview.is_file() or not report.is_file(): raise RuntimeError("Worker especial não produziu os artefatos esperados.")
        worker=_load_json(report,"Relatório do worker especial")
        # Esta etapa só pode diferir da base acumulada dentro da nova seleção.
        with Image.open(preview).convert("RGB") as pi, Image.open(base_current).convert("RGB") as ci:
            x1,y1,x2,y2=bbox
            for box in ((0,0,w,y1),(0,y2,w,h),(0,y1,x1,y2),(x2,y1,w,y2)):
                if box[2]>box[0] and box[3]>box[1] and ImageChops.difference(pi.crop(box),ci.crop(box)).getbbox():
                    raise RuntimeError("Preview especial alterou pixels fora da nova região selecionada.")
        manifest={"schema":SCHEMA,"proposal_id":pid,"status":STATUS_PROPOSAL,"chapter":chapter,"source_stage":stage,"source_file":source_file,"clean_file":clean_file,"special_type":SUPPORTED_TYPE,"selection_percent":sel,"bbox_pixels":{"x":bbox[0],"y":bbox[1],"width":bbox[2]-bbox[0],"height":bbox[3]-bbox[1]},"regions":previous_regions+[{"selection_percent":sel,"bbox_pixels":{"x":bbox[0],"y":bbox[1],"width":bbox[2]-bbox[0],"height":bbox[3]-bbox[1]}}],"base_proposal_id":base_pid or None,"created_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"case_source_sha256":refs["source_sha256"],"case_current_sha256":refs["current_sha256"],"official_source_sha256":_sha256(source_off),"official_clean_sha256":_sha256(clean_off),"preview_file":"preview.png","preview_sha256":_sha256(preview),"worker":worker,"safety":{"official_image_modified":False,"source_image_modified":False,"merge_source_modified":False,"composition_limited_to_selection":True,"promotion_requires_explicit_approval":True}}
        report.unlink(missing_ok=True); (tmp/"proposal.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); os.replace(tmp,final)
        return {"status":STATUS_PROPOSAL,"proposal_id":pid,"preview_file":"preview.png","selection_percent":sel,"bbox_pixels":manifest["bbox_pixels"],"regions":manifest["regions"],"region_count":len(manifest["regions"]),"message":f"Prévia especial acumulada com {len(manifest['regions'])} região(ões), sem alterar o resultado oficial."}
    except Exception:
        if tmp.exists(): shutil.rmtree(tmp,ignore_errors=True)
        raise


def generate_preview_job(manga,chs,payload):
    if len(chs)!=1: raise ValueError("A correção especial gera uma prévia por vez.")
    ch=chs[0]
    return generate_preview(manga,ch.name,payload.get("source_stage"),payload.get("source_file"),payload.get("clean_file"),payload.get("selection"),payload.get("base_proposal_id"))


def approve_proposal(manga,chapter,source_stage,source_file,clean_file,proposal_id):
    chapter=_chapter(chapter); stage=_normalize_stage(source_stage); source_file=_image_name(source_file,"Imagem fonte"); clean_file=_image_name(clean_file,"Imagem limpa")
    case_dir,case_mp,case=_case(manga,chapter,stage,source_file); _refs(case_dir,case)
    pdir=proposal_dir(manga,chapter,stage,source_file,proposal_id); pp=pdir/"proposal.json"; preview=pdir/"preview.png"
    if not pp.is_file() or not preview.is_file(): raise ValueError("Proposta especial incompleta.")
    pm=_load_json(pp,"Manifesto da proposta especial")
    if pm.get("schema")!=SCHEMA or pm.get("status")!=STATUS_PROPOSAL or pm.get("proposal_id")!=proposal_id: raise ValueError("Proposta especial indisponível para aprovação.")
    if pm.get("chapter")!=chapter or pm.get("source_stage")!=stage or pm.get("source_file")!=source_file or pm.get("clean_file")!=clean_file: raise ValueError("Identidade da proposta especial divergente.")
    source_off=(_source_dir(manga,chapter,stage)/source_file).resolve(); clean_off=(_clean_dir(manga,chapter,stage)/clean_file).resolve()
    if _sha256(source_off)!=pm.get("official_source_sha256") or _sha256(clean_off)!=pm.get("official_clean_sha256"): raise RuntimeError("PROPOSTA_ESPECIAL_OBSOLETA: os artefatos oficiais mudaram após a geração da prévia.")
    if _sha256(preview)!=pm.get("preview_sha256"): raise RuntimeError("Integridade do preview especial inválida.")
    with Image.open(preview) as a, Image.open(clean_off) as b:
        if a.size!=b.size: raise RuntimeError("Dimensões divergentes entre preview e resultado oficial.")
    original_clean=clean_off.read_bytes(); original_case=case_mp.read_bytes(); original_prop=pp.read_bytes(); now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp=None
    try:
        fd,name=tempfile.mkstemp(prefix=".textoff-special-promote-",suffix=clean_off.suffix,dir=str(clean_off.parent)); os.close(fd); tmp=Path(name); shutil.copy2(preview,tmp)
        os.replace(tmp,clean_off); tmp=None
        promoted=_sha256(clean_off)
        if promoted!=pm["preview_sha256"]: raise RuntimeError("Falha de integridade após promoção especial.")
        pm.update({"status":STATUS_APPROVED,"approved_at":now,"promoted_to":str(clean_off.relative_to(manga)),"promoted_sha256":promoted})
        pm["safety"].update({"official_image_modified":True,"source_image_modified":False,"merge_source_modified":False})
        case.update({"status":STATUS_CORRECTED,"updated_at":now,"approved_at":now,"approved_proposal_id":proposal_id,"approved_sha256":promoted})
        case["safety"].update({"official_image_modified":True,"promotion_automatic":False})
        # Escritas de estado por último; qualquer falha restaura imagem + manifests.
        pp.write_text(json.dumps(pm,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        case_mp.write_text(json.dumps(case,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return {"status":STATUS_CORRECTED,"proposal_id":proposal_id,"promoted_to":str(clean_off.relative_to(manga)),"promoted_sha256":promoted,"message":"Correção especial aprovada somente no resultado Texto Off. IMG e 02_MERGE permanecem intactos."}
    except Exception:
        if tmp: tmp.unlink(missing_ok=True)
        clean_off.write_bytes(original_clean); case_mp.write_bytes(original_case); pp.write_bytes(original_prop)
        raise


def approve_proposal_job(manga,chs,payload):
    if len(chs)!=1: raise ValueError("A correção especial aprova uma página por vez.")
    ch=chs[0]
    return approve_proposal(manga,ch.name,payload.get("source_stage"),payload.get("source_file"),payload.get("clean_file"),str(payload.get("proposal_id") or ""))


def _worker(source:Path,current:Path,preview:Path,report:Path,bbox):
    import numpy as np, torch
    from simple_lama_inpainting import SimpleLama
    from processamento.limpeza_baloes.cleaner_v2.level2 import PADDING, _find_model
    src=Image.open(source).convert("RGB"); cur=Image.open(current).convert("RGB")
    if src.size!=cur.size: raise RuntimeError("Dimensões divergentes no worker especial.")
    w,h=src.size; x1,y1,x2,y2=bbox
    if not (0<=x1<x2<=w and 0<=y1<y2<=h): raise ValueError("BBox especial inválida.")
    cx1=max(0,x1-int(PADDING)); cy1=max(0,y1-int(PADDING)); cx2=min(w,x2+int(PADDING)); cy2=min(h,y2+int(PADDING))
    src_np=np.asarray(src); cur_np=np.asarray(cur).copy(); crop=Image.fromarray(src_np[cy1:cy2,cx1:cx2]); mask=np.zeros((cy2-cy1,cx2-cx1),dtype=np.uint8); mask[y1-cy1:y2-cy1,x1-cx1:x2-cx1]=255
    model_path=_find_model(); os.environ["LAMA_MODEL"]=str(model_path); device=torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu"); model=SimpleLama(device=device); result=model(crop,Image.fromarray(mask,mode="L")); result_np=np.asarray(result)
    # SimpleLama pads a entrada para múltiplos de 8 e devolve também esse padding.
    # A composição especial trabalha nas dimensões originais do crop: remova apenas
    # a sobra inferior/direita criada pelo modelo, sem resize/interpolação.
    crop_h,crop_w=mask.shape
    if result_np.shape[0]<crop_h or result_np.shape[1]<crop_w: raise RuntimeError(f"Resultado LaMa menor que o recorte especial: {result_np.shape[:2]} < {(crop_h,crop_w)}")
    result_np=result_np[:crop_h,:crop_w]
    local=mask>0; target=cur_np[cy1:cy2,cx1:cx2]; target[local]=result_np[local]; cur_np[cy1:cy2,cx1:cx2]=target
    preview.parent.mkdir(parents=True,exist_ok=True); Image.fromarray(cur_np).save(preview,"PNG")
    report.write_text(json.dumps({"method":"lama_regional_assisted","device":str(device),"model":str(model_path),"padding":int(PADDING),"crop_pixels":{"x":cx1,"y":cy1,"width":cx2-cx1,"height":cy2-cy1}},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return 0


def _parse_bbox(raw):
    try: vals=tuple(int(x) for x in str(raw).split(","))
    except ValueError: raise argparse.ArgumentTypeError("BBox inválida.") from None
    if len(vals)!=4: raise argparse.ArgumentTypeError("BBox deve possuir quatro inteiros.")
    return vals


def main():
    p=argparse.ArgumentParser(); p.add_argument("--worker",action="store_true"); p.add_argument("--source",type=Path); p.add_argument("--current",type=Path); p.add_argument("--preview",type=Path); p.add_argument("--report",type=Path); p.add_argument("--bbox",type=_parse_bbox); a=p.parse_args()
    if not a.worker: p.error("Módulo disponível apenas em modo worker.")
    for n in ("source","current","preview","report","bbox"):
        if getattr(a,n) is None: p.error(f"--{n} é obrigatório.")
    return _worker(a.source,a.current,a.preview,a.report,a.bbox)
if __name__=="__main__": raise SystemExit(main())
