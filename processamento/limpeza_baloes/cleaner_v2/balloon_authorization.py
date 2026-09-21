"""Texto Off Nível I: restringe a máscara do Cleaner V2 a balões segmentados."""
from pathlib import Path
import json

MODEL_REPO="huyvux3005/manga109-segmentation-bubble"
MODEL_FILE="best.pt"
MODEL_REVISION="f9a4108c4955136a810e5e92207972f3fb3a65fd"
CONF=0.25
IOU=0.45
ALGORITHM="textoff_level1_balloon_component_gate_v2"
COMPONENT_MIN_AREA=20
COMPONENT_MIN_INSIDE_RATIO=0.90
BALLOON_INTERIOR_ERODE_RATIO=0.025
BALLOON_INTERIOR_ERODE_MIN=2
BALLOON_INTERIOR_ERODE_MAX=8

def apply_balloon_authorization(source_images, output_dir, report_path, *, progress_job=None, chapter_name=None):
    try:
        import cv2
        import numpy as np
        from huggingface_hub import hf_hub_download
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Nível I requer cv2, numpy, huggingface_hub e ultralytics.") from exc

    try:
        model_path=hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE, revision=MODEL_REVISION)
        model=YOLO(model_path)
    except Exception as exc:
        raise RuntimeError("Nível I não conseguiu carregar o segmentador de balões; Cleaner V2 global NÃO será promovido.") from exc

    if getattr(model,"task",None)!="segment" or "balloon" not in {str(v).strip().lower() for v in (model.names or {}).values()}:
        raise RuntimeError(f"Modelo inválido para Nível I: task={getattr(model,'task',None)!r}, classes={model.names!r}")

    output_dir=Path(output_dir)
    pages=[]
    total_cleaner=total_authorized=0

    for i,src in enumerate(map(Path,source_images),1):
        cleans=sorted(p for p in output_dir.glob(f"{src.stem}_clean.*") if p.is_file())
        masks=sorted(p for p in output_dir.glob(f"{src.stem}_mask.*") if p.is_file())
        if len(cleans)!=1 or len(masks)!=1:
            raise RuntimeError(f"Nível I esperava 1 clean e 1 mask para {src.name}.")
        clean_path,mask_path=cleans[0],masks[0]
        original=cv2.imread(str(src))
        cleaned=cv2.imread(str(clean_path))
        cleaner_mask=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
        if original is None or cleaned is None or cleaner_mask is None:
            raise RuntimeError(f"Nível I falhou ao ler artefatos de {src.name}.")
        if original.shape!=cleaned.shape or cleaner_mask.shape[:2]!=original.shape[:2]:
            raise RuntimeError(f"Nível I encontrou dimensões divergentes em {src.name}.")

        if progress_job is not None:
            prefix=f"Cap. {chapter_name}: " if chapter_name else ""
            progress_job.progress_detail=prefix+f"validando balões do Nível I ({i}/{len(source_images)})..."
            progress_job.message=progress_job.progress_detail

        try:
            result=model.predict(source=original,conf=CONF,iou=IOU,verbose=False)[0]
        except Exception as exc:
            raise RuntimeError(f"Nível I falhou ao segmentar {src.name}; Cleaner V2 global NÃO será promovido.") from exc

        balloon_masks=[]
        if result.masks is not None:
            for poly in result.masks.xy:
                pts=np.asarray(poly,dtype=np.int32)
                if len(pts)<3:
                    continue
                bm=np.zeros(original.shape[:2],dtype=np.uint8)
                cv2.fillPoly(bm,[pts],255)
                x,y,w,h=cv2.boundingRect(pts)
                margin=max(BALLOON_INTERIOR_ERODE_MIN,
                           min(BALLOON_INTERIOR_ERODE_MAX,
                               int(round(min(w,h)*BALLOON_INTERIOR_ERODE_RATIO))))
                if margin>0:
                    k=2*margin+1
                    interior=cv2.erode(bm,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k)))
                    if np.count_nonzero(interior):
                        bm=interior
                balloon_masks.append(bm)
        balloons=len(balloon_masks)

        binary=(cleaner_mask>0).astype(np.uint8)
        n,labels,stats,_=cv2.connectedComponentsWithStats(binary,8)
        effective=np.zeros_like(cleaner_mask)
        component_decisions=[]
        authorized_components=0

        for label in range(1,n):
            area=int(stats[label,cv2.CC_STAT_AREA])
            if area<COMPONENT_MIN_AREA:
                component_decisions.append({"component":label,"area":area,"decision":"preserve",
                                            "reason":"component_too_small"})
                continue
            component=(labels==label)
            best_ratio=0.0
            best_balloon=None
            for bi,bm in enumerate(balloon_masks,1):
                inside=int(np.count_nonzero(component & (bm>0)))
                ratio=inside/area if area else 0.0
                if ratio>best_ratio:
                    best_ratio=ratio
                    best_balloon=bi

            if best_ratio>=COMPONENT_MIN_INSIDE_RATIO:
                effective[component]=cleaner_mask[component]
                decision="remove"
                reason="inside_single_balloon"
                authorized_components+=1
            else:
                decision="preserve"
                reason="outside_or_ambiguous"

            x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP])
            w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
            component_decisions.append({"component":label,"bbox":[x,y,w,h],"area":area,
                                        "best_balloon":best_balloon,
                                        "inside_ratio":round(best_ratio,4),
                                        "decision":decision,"reason":reason})

        final=original.copy()
        final[effective>0]=cleaned[effective>0]

        clean_tmp=clean_path.with_name(clean_path.stem+".level1-tmp"+clean_path.suffix)
        mask_tmp=mask_path.with_name(mask_path.stem+".level1-tmp"+mask_path.suffix)
        if not cv2.imwrite(str(clean_tmp),final) or not cv2.imwrite(str(mask_tmp),effective):
            clean_tmp.unlink(missing_ok=True); mask_tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Nível I falhou ao gravar artefatos de {src.name}.")
        clean_tmp.replace(clean_path); mask_tmp.replace(mask_path)

        cp=int(np.count_nonzero(cleaner_mask)); ap=int(np.count_nonzero(effective))
        total_cleaner+=cp; total_authorized+=ap
        pages.append({"source":src.name,"balloons_detected":balloons,"cleaner_mask_pixels":cp,
                      "authorized_mask_pixels":ap,"authorized_percent":round(ap/cp*100,4) if cp else 0.0,
                      "components_total":max(0,n-1),"components_authorized":authorized_components,
                      "component_decisions":component_decisions})

    report={"schema_version":2,"algorithm":ALGORITHM,
            "policy":"cleaner_component_must_be_inside_single_balloon_interior",
            "fail_closed":True,
            "component_policy":{"min_area":COMPONENT_MIN_AREA,
                                "min_inside_ratio":COMPONENT_MIN_INSIDE_RATIO,
                                "balloon_interior_erode_ratio":BALLOON_INTERIOR_ERODE_RATIO,
                                "balloon_interior_erode_min":BALLOON_INTERIOR_ERODE_MIN,
                                "balloon_interior_erode_max":BALLOON_INTERIOR_ERODE_MAX,
                                "ambiguous_action":"preserve","outside_action":"preserve"},
            "model":{"repo":MODEL_REPO,"file":MODEL_FILE,"revision":MODEL_REVISION,
            "task":"segment","class":"balloon","conf":CONF,"iou":IOU},"pages_total":len(pages),
            "cleaner_mask_pixels":total_cleaner,"authorized_mask_pixels":total_authorized,
            "authorized_percent":round(total_authorized/total_cleaner*100,4) if total_cleaner else 0.0,
            "pages":pages}
    Path(report_path).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return report
