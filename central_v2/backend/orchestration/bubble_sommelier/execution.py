import json
from pathlib import Path
from .artifacts import merge_dir, manifest
from .runtime import run
def execute(manga:Path,chapters:list[str],progress,preflight=None)->list[dict]:
    results=[]; total=len(chapters)
    for index,chapter in enumerate(chapters,1):
        if preflight: preflight()
        target=manifest(manga,chapter); run(merge_dir(manga,chapter),target,chapter)
        report=json.loads(target.read_text(encoding="utf-8"))
        results.append({"chapter":chapter,**report.get("summary",{})})
        progress(index,total,f"Curadoria {chapter} concluída")
    return results
