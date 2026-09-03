#!/usr/bin/env python3
import json, re, time
from pathlib import Path
from processamento.limpeza_baloes.bubble_cleaner import EasyOCRBackend, process_image, resolve_model
EXT={".png",".jpg",".jpeg",".webp"}
def key(p): return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)",p.name)]
def run_clean_flow(output_dir, *, ask_number, print_header, print_option, c):
    providers=[output_dir/n for n in ("comix","mangago") if (output_dir/n).is_dir()]
    if not providers: print(c("error","Nenhum provider encontrado.")); return
    print_header("LIMPAR BALÕES")
    for i,p in enumerate(providers,1): print_option(i,p.name.capitalize()); print()
    print(f"  {c('number','0.',bold=True)} Voltar")
    x=ask_number("\nSelecione uma opção › ",range(len(providers)+1))
    if not x:return
    provider=providers[x-1]
    mangas=sorted([p for p in provider.iterdir() if p.is_dir() and (p/"IMG").is_dir()],key=key)
    print_header(provider.name.upper())
    for i,p in enumerate(mangas,1): print_option(i,p.name); print()
    print(f"  {c('number','0.',bold=True)} Voltar")
    x=ask_number("\nSelecione uma opção › ",range(len(mangas)+1))
    if not x:return
    manga=mangas[x-1]
    chapters=sorted([p for p in (manga/"IMG").iterdir() if p.is_dir() and any(q.suffix.lower() in EXT for q in p.iterdir() if q.is_file())],key=key)
    print_header(manga.name.upper())
    for i,p in enumerate(chapters,1): print_option(i,p.name); print()
    raw=input(c("prompt","\nCapítulos (1,2,5 ou 1-5 ou todos) › ",bold=True)).strip().lower()
    if raw in {"todos","all"}: nums=list(range(1,len(chapters)+1))
    else:
        s=set()
        for part in raw.split(","):
            part=part.strip()
            if not part:continue
            if "-" in part:
                a,b=map(int,part.split("-",1)); a,b=min(a,b),max(a,b); s.update(range(a,b+1))
            else:s.add(int(part))
        nums=sorted(n for n in s if 1<=n<=len(chapters))
    model=resolve_model(None); ocr_backend=EasyOCRBackend(["en"]); ok=fail=0
    for n in nums:
        ch=chapters[n-1]; target=manga/"FLUXO_SECUNDARIO"/"04_TEXTO_OFF"/"ORIGINAL"/ch.name; target.mkdir(parents=True,exist_ok=True)
        reports=[]
        images=sorted([p for p in ch.iterdir() if p.is_file() and p.suffix.lower() in EXT],key=key)
        chapter_start=time.perf_counter()
        print(c("prompt",f"Processando {ch.name}: {len(images)} página(s)"))
        for page_no,img in enumerate(images,1):
            page_start=time.perf_counter()
            try:
                reports.append(process_image(img,target,model,["en"],0.55,ocr_backend=ocr_backend)); ok+=1
                page_elapsed=time.perf_counter()-page_start
                chapter_elapsed=time.perf_counter()-chapter_start
                avg=chapter_elapsed/page_no
                remaining=max(0,len(images)-page_no)*avg
                print(c("success",f"[{page_no}/{len(images)}] {img.name} · {page_elapsed:.1f}s · restante ~{remaining/60:.1f} min"), flush=True)
            except Exception as e:
                fail+=1
                print(c("error",f"[{page_no}/{len(images)}] {img.name}: {e}"), flush=True)
        manifest={"schema_version":1,"algorithm":"bubble_cleaner_v3_5","source_immutable":True,"pages_total":len(reports),"integrity_ok":all(r["summary"]["integrity_ok"] for r in reports)}
        (target/"clean-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print(c("success",f"Concluído: {ch.name}"))
    print_header("RESUMO"); print(c("success",f"Páginas processadas: {ok}")); print(c("error" if fail else "success",f"Falhas: {fail}"))
