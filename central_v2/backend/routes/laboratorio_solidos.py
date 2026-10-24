"""Quick, preview-only solid-white text filter for Laboratory-selected ROIs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import uuid
from urllib.parse import urlencode
from PIL import Image
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.laboratorio_source import resolve_source
from central_v2.backend.orchestration.textoff_special.inputs import validate_selections

PREVIEWS = "_laboratorio_solidos_previews"

def _json(data, code=200):
    return RouteResponse(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def _box(row, width, height):
    x, y = round(row["x"]), round(row["y"])
    w, h = round(row["width"]), round(row["height"])
    if w < 12 or h < 12 or x < 0 or y < 0 or x+w > width or y+h > height:
        raise ValueError("Área fora da imagem ou muito pequena.")
    return x, y, w, h

def _filter(image, selections):
    import cv2
    import numpy as np
    pixels = np.asarray(image.convert("RGB")).copy()
    height, width = pixels.shape[:2]
    mask_all = np.zeros((height, width), dtype=np.uint8)
    audit = []
    for row in selections:
        x, y, w, h = _box(row, width, height)
        cropped = pixels[y:y+h, x:x+w].copy()
        gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)
        white_fraction = float(np.mean(np.min(cropped, axis=2) >= 245))
        if white_fraction < .70:
            audit.append({"box": [x,y,w,h], "status": "preserved_requires_review",
                          "reason": "Fundo não suficientemente branco", "changed_pixels": 0})
            continue
        if w <= 6 or h <= 6:
            raise ValueError("Área selecionada muito pequena")
        dark = (gray[3:-3, 3:-3] < 205).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
        selected = np.zeros_like(dark, dtype=np.uint8)
        accepted = 0
        for idx in range(1, count):
            bx, by, bw, bh, area = (int(v) for v in stats[idx])
            if 2 <= area < w*h*.20 and bw < w*.80 and bh < h*.70:
                selected[labels == idx] = 255
                accepted += 1
        region_mask = np.zeros((h,w), dtype=np.uint8)
        region_mask[3:-3,3:-3] = selected
        region_mask = cv2.dilate(region_mask, np.ones((3,3),np.uint8),iterations=1)
        region_mask[gray >= 253] = 0
        region_mask[:3,:] = 0; region_mask[-3:,:] = 0
        region_mask[:,:3] = 0; region_mask[:,-3:] = 0
        changed = int(np.count_nonzero(region_mask))
        if changed > w*h*.30 or (not accepted and changed):
            audit.append({"box": [x,y,w,h],"status":"preserved_requires_review",
                          "reason":"Máscara insegura", "changed_pixels":0})
            continue
        pixels[y:y+h,x:x+w][region_mask>0] = 255
        mask_all[y:y+h,x:x+w] = np.maximum(mask_all[y:y+h,x:x+w],region_mask)
        audit.append({"box":[x,y,w,h], "status":"candidate" if changed else "unchanged",
                      "changed_pixels":changed,"components":accepted,
                      "white_fraction":round(white_fraction,4)})
    return Image.fromarray(pixels), Image.fromarray(mask_all), audit

def execute(payload, output_root):
    try:
        if not isinstance(payload, dict): raise ValueError("Requisição inválida")
        provider, manga = payload.get("provider"), payload.get("manga")
        selections = validate_selections(payload.get("selections"))
        if len(selections) > 30: raise ValueError("Limite de 30 áreas por prévia")
        _, source, chapter, page = resolve_source(payload, output_root)
        source_hash = _sha(source)
        with Image.open(source) as inp: original = inp.convert("RGB")
        if original.width*original.height > 100_000_000:
            raise ValueError("Imagem excede o limite operacional")
        result, mask, audit = _filter(original,selections)
        if _sha(source) != source_hash: raise ValueError("Imagem mudou durante execução")
        output_dir = Path(output_root).resolve()/PREVIEWS
        output_dir.mkdir(parents=True,exist_ok=True)
        run_id = uuid.uuid4().hex
        target = output_dir/run_id
        target.mkdir()
        try:
            result.save(target/"preview.png")
            mask.save(target/"mask.png")
            meta = {"schema":"laboratorio_solidos_preview_v1", "source_sha256":source_hash,
                    "provider":provider,"manga":manga,"chapter":chapter,"page":page,
                    "preview_sha256":_sha(target/"preview.png"),"regions":audit,
                    "preview_only":True}
            (target/"manifest.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n")
        except Exception:
            import shutil
            shutil.rmtree(target,ignore_errors=True)
            raise
        return _json({"run_id":run_id,"image_url":"/api/textoff/laboratorio/solidos/image?"+
                      urlencode({"run_id":run_id}), "regions":audit, "status":"preview"})
    except (ValueError,OSError,ImportError) as error:
        return _json({"error":str(error)},400)

def image_response(query, output_root):
    rid=(query.get("run_id") or [""])[0]
    if len(rid)!=32 or any(c not in "0123456789abcdef" for c in rid):
        return _json({"error":"Execução inválida"},400)
    path=Path(output_root).resolve()/PREVIEWS/rid
    try:
        meta=json.loads((path/"manifest.json").read_text())
        preview=path/"preview.png"
        if meta.get("preview_only") is not True or _sha(preview)!=meta.get("preview_sha256"):
            raise ValueError("Prévia divergente")
        return RouteResponse(200,preview.read_bytes(),"image/png")
    except (OSError,ValueError):
        return _json({"error":"Prévia indisponível"},404)
