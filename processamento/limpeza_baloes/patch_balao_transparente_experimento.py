"""Diagnóstico isolado: reproduz checkpoints históricos do Texto Off em f4a26ce.

Não altera IMG, 02_MERGE, 04_TEXTO_OFF nem qualquer saída oficial.
Usa a opção 9 já existente e grava somente em reports/experimentos.
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw

from processamento.limpeza_baloes import patch_degrade_experimento as base
import subprocess
import re

# Congelado de f4a26ce:
MODEL_REPO = "huyvux3005/manga109-segmentation-bubble"
MODEL_FILE = "best.pt"
MODEL_REVISION = "f9a4108c4955136a810e5e92207972f3fb3a65fd"
CONF = 0.25
IOU = 0.45
HISTORICAL_AUTH_ALGORITHM = "textoff_level1_balloon_gate_v1"

TEST_CHAPTER = "Ch. 3"
TEST_PAGES = ("page-036.png", "page-037.png", "page-040.png", "page-084.png")
OUT = base.OUT / "transparent_historical_f4a26ce"



def protect_colored_balloons(source_images, output_dir: Path, report_path: Path) -> dict:
    """Implementação congelada de functional_guard.py em f4a26ce."""
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO

    SAT_MEAN_RISK = 25.0
    SAT_P90_RISK = 55.0
    MIN_INTERIOR_PIXELS = 500
    model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE, revision=MODEL_REVISION)
    model = YOLO(model_path)
    output_dir = Path(output_dir)
    pages = []
    protected_total = 0

    for src in map(Path, source_images):
        original = cv2.imread(str(src))
        if original is None:
            raise RuntimeError(f"Guard histórico falhou ao ler original: {src}")
        clean_path = _single(output_dir, src.stem, "clean")
        mask_path = _single(output_dir, src.stem, "mask")
        cleaned = cv2.imread(str(clean_path))
        cleaner_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if cleaned is None or cleaner_mask is None:
            raise RuntimeError(f"Guard histórico falhou ao ler artefatos de {src.name}.")

        result = model.predict(source=original, conf=CONF, iou=IOU, verbose=False)[0]
        hsv = cv2.cvtColor(original, cv2.COLOR_BGR2HSV)
        page_balloons = []

        if result.masks is not None:
            for idx, poly in enumerate(result.masks.xy, start=1):
                pts = np.asarray(poly, dtype=np.int32)
                if len(pts) < 3:
                    continue
                balloon = np.zeros(original.shape[:2], dtype=np.uint8)
                cv2.fillPoly(balloon, [pts], 255)
                area = int(np.count_nonzero(balloon))
                if area <= 0:
                    continue
                interior = cv2.erode(balloon, np.ones((9, 9), np.uint8), iterations=1)
                valid = interior > 0
                interior_pixels = int(np.count_nonzero(valid))
                if interior_pixels < MIN_INTERIOR_PIXELS:
                    valid = balloon > 0
                    interior_pixels = area

                sat = hsv[:, :, 1][valid].astype(np.float32)
                sat_mean = float(sat.mean()) if sat.size else 0.0
                sat_p90 = float(np.percentile(sat, 90)) if sat.size else 0.0
                lum = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)[valid].astype(np.float32)
                lum_std = float(lum.std()) if lum.size else 0.0
                sustained = bool(sat.size and sat_mean >= SAT_MEAN_RISK and sat_p90 >= SAT_P90_RISK)
                pale = bool(sat.size and sat_p90 >= 80.0 and lum_std >= 35.0)
                risky = sustained or pale
                before = int(np.count_nonzero(cleaner_mask[balloon > 0]))
                if risky:
                    cleaned[balloon > 0] = original[balloon > 0]
                    cleaner_mask[balloon > 0] = 0
                    protected_total += 1
                page_balloons.append({
                    "balloon_id": idx, "area_pixels": area, "interior_pixels": interior_pixels,
                    "saturation_mean": round(sat_mean,4), "saturation_p90": round(sat_p90,4),
                    "luminance_std": round(lum_std,4),
                    "risk_signals":{"sustained_chroma":sustained,"pale_gradient_risk":pale},
                    "mask_pixels_before_guard":before, "protected_from_level3":risky,
                    "route_hint":"LEVEL_5" if risky else "UNDECIDED"
                })
        cv2.imwrite(str(clean_path), cleaned)
        cv2.imwrite(str(mask_path), cleaner_mask)
        pages.append({"source":src.name,"balloons":page_balloons})

    report={"schema_version":1,"algorithm":"textoff_level2_colored_balloon_guard_v1",
            "mode":"FUNCTIONAL_FAIL_CLOSED_GUARD","protected_balloons_total":protected_total,
            "pages":pages}
    Path(report_path).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return report

def _single(folder: Path, stem: str, kind: str) -> Path:
    matches = sorted(p for p in folder.glob(f"{stem}_{kind}.*") if p.is_file())
    if len(matches) != 1:
        raise RuntimeError(
            f"Esperado 1 artefato {kind} para {stem}; encontrados: "
            + (", ".join(p.name for p in matches) if matches else "nenhum")
        )
    return matches[0]


def _copy_checkpoint(clean_path: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(clean_path, target)
    return target


def _historical_balloon_authorization(source: Path, output_dir: Path, report_path: Path) -> dict:
    """Cópia funcional do apply_balloon_authorization em f4a26ce."""
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO

    model_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILE,
        revision=MODEL_REVISION,
    )
    model = YOLO(model_path)
    names = {str(v).strip().lower() for v in (model.names or {}).values()}
    if getattr(model, "task", None) != "segment" or "balloon" not in names:
        raise RuntimeError(
            f"Modelo histórico inválido: task={getattr(model, 'task', None)!r}, "
            f"classes={model.names!r}"
        )

    clean_path = _single(output_dir, source.stem, "clean")
    mask_path = _single(output_dir, source.stem, "mask")
    original = cv2.imread(str(source))
    cleaned = cv2.imread(str(clean_path))
    cleaner_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if original is None or cleaned is None or cleaner_mask is None:
        raise RuntimeError("Falha ao ler os artefatos do checkpoint histórico.")
    if original.shape != cleaned.shape or cleaner_mask.shape[:2] != original.shape[:2]:
        raise RuntimeError("Dimensões divergentes no checkpoint histórico.")

    result = model.predict(source=original, conf=CONF, iou=IOU, verbose=False)[0]
    balloon_mask = np.zeros(original.shape[:2], dtype=np.uint8)
    balloons = 0
    if result.masks is not None:
        for poly in result.masks.xy:
            pts = np.asarray(poly, dtype=np.int32)
            if len(pts) >= 3:
                cv2.fillPoly(balloon_mask, [pts], 255)
                balloons += 1

    effective = cv2.bitwise_and(cleaner_mask, balloon_mask)

    # Exatamente a política histórica: ORIGINAL como base e apenas pixels
    # autorizados vindos do resultado do Cleaner.
    final = original.copy()
    final[effective > 0] = cleaned[effective > 0]

    if not cv2.imwrite(str(clean_path), final):
        raise RuntimeError("Falha ao gravar clean histórico autorizado.")
    if not cv2.imwrite(str(mask_path), effective):
        raise RuntimeError("Falha ao gravar mask histórica autorizada.")

    cp = int(np.count_nonzero(cleaner_mask))
    ap = int(np.count_nonzero(effective))
    report = {
        "schema_version": 1,
        "algorithm": HISTORICAL_AUTH_ALGORITHM,
        "policy": "cleaner_mask_intersection_balloon_mask",
        "fail_closed": True,
        "model": {
            "repo": MODEL_REPO,
            "file": MODEL_FILE,
            "revision": MODEL_REVISION,
            "task": "segment",
            "class": "balloon",
            "conf": CONF,
            "iou": IOU,
        },
        "pages_total": 1,
        "cleaner_mask_pixels": cp,
        "authorized_mask_pixels": ap,
        "authorized_percent": round(ap / cp * 100, 4) if cp else 0.0,
        "pages": [{
            "source": source.name,
            "balloons_detected": balloons,
            "cleaner_mask_pixels": cp,
            "authorized_mask_pixels": ap,
            "authorized_percent": round(ap / cp * 100, 4) if cp else 0.0,
        }],
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _montage(items: list[tuple[str, Path]], target: Path) -> None:
    opened = []
    try:
        for label, path in items:
            opened.append((label, Image.open(path).convert("RGB")))
        max_h = max(im.height for _, im in opened)
        normalized = []
        for label, im in opened:
            if im.height != max_h:
                width = max(1, round(im.width * (max_h / im.height)))
                im = im.resize((width, max_h), Image.Resampling.LANCZOS)
            normalized.append((label, im))

        header = 44
        gap = 8
        width = sum(im.width for _, im in normalized) + gap * (len(normalized) - 1)
        canvas = Image.new("RGB", (width, max_h + header), "white")
        draw = ImageDraw.Draw(canvas)
        x = 0
        for label, im in normalized:
            canvas.paste(im, (x, header))
            draw.text((x + 8, 14), label, fill="black")
            x += im.width + gap
        canvas.save(target, "PNG")
    finally:
        for _, im in opened:
            try:
                im.close()
            except Exception:
                pass


def _run_page(page: Path) -> Path:
    target = OUT / TEST_CHAPTER / page.stem
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    print(f"\n--- {TEST_CHAPTER} · {page.name} ---")
    print("Checkpoint 1/4: Panel Cleaner bruto...")
    clean_path, mask_path = base._run_cleaner(page, target)
    raw = _copy_checkpoint(clean_path, target / "01_cleaner_bruto.png")
    shutil.copy2(mask_path, target / "01_cleaner_mask.png")

    print("Checkpoint 2/4: Guard histórico de f4a26ce...")
    guard_report_path = target / "02_guard_report.json"
    guard_report = protect_colored_balloons([page], clean_path.parent, guard_report_path)
    clean_path = _single(clean_path.parent, page.stem, "clean")
    guard = _copy_checkpoint(clean_path, target / "02_apos_guard.png")
    shutil.copy2(_single(clean_path.parent, page.stem, "mask"), target / "02_apos_guard_mask.png")

    print("Checkpoint 3/4: Balloon Authorization histórica de f4a26ce...")
    auth_report_path = target / "03_balloon_authorization_report.json"
    auth_report = _historical_balloon_authorization(page, clean_path.parent, auth_report_path)
    clean_path = _single(clean_path.parent, page.stem, "clean")
    auth = _copy_checkpoint(clean_path, target / "03_apos_balloon_authorization.png")
    shutil.copy2(_single(clean_path.parent, page.stem, "mask"), target / "03_apos_balloon_authorization_mask.png")

    print("Checkpoint 4/4: Nível II / LaMa histórico...")
    # IMPORTANTE: o LaMa não está instalado no Python do Fominha/menu.
    # O pipeline histórico executava level2.py no Python isolado do Cleaner V2.
    source_dir = target / "historical_source"
    source_dir.mkdir()
    shutil.copy2(page, source_dir / page.name)
    level2_report_path = target / "04_level2_report.json"
    level2_script = base.CLEANER_DIR / "level2.py"
    cmd = [
        str(base.CLEANER_PY),
        str(level2_script),
        "--source-dir", str(source_dir),
        "--output-dir", str(clean_path.parent),
        "--report", str(level2_report_path),
    ]
    proc = subprocess.run(cmd, cwd=str(base.CLEANER_DIR), check=False)
    if proc.returncode:
        raise RuntimeError(
            f"Nível II histórico falhou com código {proc.returncode}. "
            f"Comando executado no ambiente isolado do Cleaner V2: {' '.join(cmd)}"
        )
    level2_report = json.loads(level2_report_path.read_text(encoding="utf-8"))
    clean_path = _single(clean_path.parent, page.stem, "clean")
    lama = _copy_checkpoint(clean_path, target / "04_apos_level2_lama.png")

    comparison = target / "00_comparativo_historico_f4a26ce.png"
    _montage([
        ("ORIGINAL", page),
        ("1 CLEANER BRUTO", raw),
        ("2 APOS GUARD", guard),
        ("3 APOS AUTH f4a26ce", auth),
        ("4 LAMA NIVEL II", lama),
    ], comparison)

    run = {
        "reference_commit": "f4a26cedf06d8494137f0093a5338c75591bd7ee",
        "source": str(page),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "checkpoints": {
            "cleaner_raw": raw.name,
            "after_guard": guard.name,
            "after_historical_authorization": auth.name,
            "after_level2_lama": lama.name,
            "comparison": comparison.name,
        },
        "guard": {
            "algorithm": guard_report.get("algorithm"),
            "protected_balloons_total": guard_report.get("protected_balloons_total"),
        },
        "authorization": {
            "algorithm": auth_report.get("algorithm"),
            "cleaner_mask_pixels": auth_report.get("cleaner_mask_pixels"),
            "authorized_mask_pixels": auth_report.get("authorized_mask_pixels"),
            "authorized_percent": auth_report.get("authorized_percent"),
        },
        "level2": {
            "algorithm": level2_report.get("algorithm"),
            "pages_level2": level2_report.get("pages_level2"),
            "components_level2": level2_report.get("components_level2"),
            "type_counts": level2_report.get("type_counts"),
        },
        "official_files_modified": False,
    }
    (target / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nComparativo: {comparison}")
    print("Ordem: ORIGINAL | CLEANER BRUTO | APÓS GUARD | APÓS AUTH f4a26ce | LAMA NÍVEL II")
    print("Nenhum arquivo oficial foi alterado.")
    return comparison



def _merge_chapter_dir() -> Path:
    # IMG = <obra>/IMG; Merge oficial fica no mesmo root da obra.
    work_root = Path(base.IMG).parent
    candidates = [
        work_root / "FLUXO_SECUNDARIO" / "02_MERGE" / TEST_CHAPTER,
        work_root / "FLUXO_SECUNDARIO" / "02_MERGE" / TEST_CHAPTER.replace("Ch. ", ""),
    ]
    for folder in candidates:
        if folder.is_dir():
            return folder
    raise FileNotFoundError(
        "Não encontrei o Merge do Ch. 3. Procurado em: " +
        " | ".join(str(x) for x in candidates)
    )


def _range_from_name(path: Path):
    m = re.fullmatch(r"page-(\d+)-(\d+)\.(?:png|jpg|jpeg|webp)", path.name, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _merged_candidates_for_page(page_number: int = 37) -> list[Path]:
    folder = _merge_chapter_dir()
    found = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        rg = _range_from_name(path)
        if rg and rg[0] <= page_number <= rg[1]:
            found.append(path)
    return found


def _mask_components(mask_path: Path) -> list[dict]:
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return []
    binary = (mask > 0).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    rows = []
    for idx in range(1, n):
        x, y, w, h, area = map(int, stats[idx])
        rows.append({"component": idx, "bbox": [x, y, w, h], "area": area})
    return rows


def _run_merged_raw(page: Path) -> Path:
    target = OUT / "MERGED_LONG_STRIP" / page.stem
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    print(f"\n--- MERGE LONGO · {page.name} ---")
    print("Objetivo: reproduzir SOMENTE o Cleaner V2 bruto sobre a geometria longa.")
    print("Sem Guard, Authorization, Local Heal ou LaMa.\n")

    started = time.monotonic()
    clean_path, mask_path = base._run_cleaner(page, target)
    raw = _copy_checkpoint(clean_path, target / "01_cleaner_bruto_merge.png")
    raw_mask = target / "01_cleaner_mask_merge.png"
    shutil.copy2(mask_path, raw_mask)

    comps = _mask_components(raw_mask)
    near_historical = []
    for row in comps:
        x, y, w, h = row["bbox"]
        # Não força igualdade: registra candidatos geometricamente próximos do
        # componente histórico [208,3573,180,141].
        if abs(y - 3573) <= 700 or (
            abs(w - 180) <= 70 and abs(h - 141) <= 70
        ):
            near_historical.append(row)

    comparison = target / "00_original_vs_cleaner_merge.png"
    _montage([
        ("ORIGINAL MERGE", page),
        ("CLEANER V2 BRUTO MERGE", raw),
    ], comparison)

    with Image.open(page) as im:
        source_size = [im.width, im.height]

    report = {
        "reference_commit": "f4a26cedf06d8494137f0093a5338c75591bd7ee",
        "experiment": "merged_long_strip_raw_cleaner",
        "source": str(page),
        "source_size": source_size,
        "historical_component_reference": {
            "bbox": [208, 3573, 180, 141],
            "rectangularity": 0.8877,
            "internal_std": 4.3045,
        },
        "mask_components": comps,
        "candidates_near_historical_geometry": near_historical,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "official_files_modified": False,
    }
    (target / "run_merge.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Dimensão da entrada: {source_size[0]}x{source_size[1]}")
    print(f"Componentes na máscara: {len(comps)}")
    print("Referência histórica procurada: bbox=[208,3573,180,141]")
    if near_historical:
        print("Candidatos próximos:")
        for row in near_historical:
            print(f"  comp {row['component']}: bbox={row['bbox']} area={row['area']}")
    else:
        print("Nenhum componente geometricamente próximo da referência histórica.")

    print(f"\nComparativo: {comparison}")
    print(f"Relatório:   {target / 'run_merge.json'}")
    print("Nenhum arquivo oficial foi alterado.")
    return comparison


def run() -> None:
    print("\nDIAGNÓSTICO BALÃO TRANSPARENTE · GEOMETRIA HISTÓRICA")
    print("Teste isolado do Cleaner V2 sobre o MERGE longo que contém a page-037.")
    print("Sem Guard, Authorization, Local Heal ou LaMa.\n")

    try:
        candidates = _merged_candidates_for_page(37)
    except FileNotFoundError as exc:
        print(exc)
        return

    if not candidates:
        print(f"Nenhum arquivo de Merge contendo a page-037 foi encontrado em {_merge_chapter_dir()}.")
        return

    print(f"Merge Ch. 3: {_merge_chapter_dir()}")
    print("Arquivos cujo intervalo contém a página 037:")
    for idx, page in enumerate(candidates, 1):
        try:
            with Image.open(page) as im:
                dims = f"{im.width}x{im.height}"
        except Exception:
            dims = "dimensão indisponível"
        print(f"[{idx}] {page.name}  ({dims})")
    print("[0] Voltar")

    raw = input("\nMerge › ").strip()
    if raw == "0":
        return
    try:
        page = candidates[int(raw) - 1]
    except (ValueError, IndexError):
        print("Seleção inválida.")
        return

    _run_merged_raw(page)


def run_transparent_balloon_experiment():
    return run()
