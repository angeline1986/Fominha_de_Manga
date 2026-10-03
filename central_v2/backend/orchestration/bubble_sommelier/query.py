import json
from pathlib import Path
from .artifacts import images, merge_dir, manifest
def _sort(v):
    numeric=v.replace(".","",1).isdigit()
    return (not numeric, float(v) if numeric else v)
def query(manga: Path) -> dict:
    root=manga/"FLUXO_SECUNDARIO"/"02_MERGE"; chapters=[]
    if root.is_dir():
        for chapter in sorted((p.name for p in root.iterdir() if p.is_dir()),key=_sort):
            imgs=images(merge_dir(manga,chapter)); report={}; path=manifest(manga,chapter)
            if path.is_file():
                try: report=json.loads(path.read_text(encoding="utf-8"))
                except (OSError,json.JSONDecodeError): report={}
            summary=report.get("summary",{})
            chapters.append({"chapter":chapter,"merge_count":len(imgs),"merge_valid":bool(imgs),
              "sommelier":{"analyzed":report.get("status")=="completed","balloons":summary.get("balloons",0),
              "normal":summary.get("normal",0),"special":summary.get("special",0)} if report else None})
    return {"chapters":chapters}
