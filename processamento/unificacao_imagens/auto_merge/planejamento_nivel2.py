"""Build Level II safe-path plans from a validated Level I manifest."""
import hashlib
import json
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.image_stitcher_level2 import (
    Level2Config,
    analyze_uniform_color_bands,
    solve_pending_region,
)


def _level1_input(manga: Path, chapter: str) -> tuple[dict, str, Path]:
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter
    path = directory / "auto-merge-manifest.json"
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("algorithm") != "auto_merge_level1_resolved_segments" or data.get("schema_version") != 1:
        raise ValueError("O manifesto não autoriza execução do Nível II.")
    if data.get("chapter") != chapter or not isinstance(data.get("pending_segments"), list):
        raise ValueError("Manifesto do Nível I incompatível com o capítulo.")
    if not data["pending_segments"]:
        raise ValueError("O capítulo não possui residual do Nível I.")
    for item in data.get("artifacts", []):
        name = item.get("file")
        if not isinstance(name, str) or Path(name).name != name or not (directory / name).is_file():
            raise ValueError("Artefato do Nível I ausente ou inválido.")
    return data, hashlib.sha256(raw).hexdigest(), directory


def plan_level2(chapter: Path, progress_callback=None) -> dict:
    manga = chapter.parent.parent
    source = chapter.name
    manifest, source_hash, level1_dir = _level1_input(manga, source)
    pages = v3.list_pages(chapter)
    if not pages:
        raise ValueError("Nenhuma imagem-fonte encontrada.")
    infos, white_bands, total, _ = v3.analyze_chapter(
        pages, progress_callback=progress_callback,
    )
    if total != int(manifest.get("total_height") or 0):
        raise ValueError("As imagens-fonte mudaram desde o manifesto do Nível I.")
    config = Level2Config()
    if progress_callback:
        progress_callback({"stage": "uniform_bands", "current": 0, "total": len(pages),
                           "message": "Analisando faixas de cor uniforme"})
    uniform_bands = analyze_uniform_color_bands(
        pages,
        sample_width=v3.DEFAULT_SAMPLE_WIDTH,
        max_channel_std=config.uniform_max_channel_std,
        max_row_delta=config.uniform_max_row_delta,
    )
    candidates = list(white_bands) + list(uniform_bands)
    if progress_callback:
        progress_callback({"stage": "uniform_bands", "current": len(pages), "total": len(pages),
                           "message": "Faixas candidatas analisadas"})
    source_intervals = [(int(info.global_start), int(info.global_end)) for info in infos]
    plans = []
    for index, residual in enumerate(manifest["pending_segments"], start=1):
        start, end = int(residual["global_start"]), int(residual["global_end"])
        if not 0 <= start < end <= total:
            raise ValueError("Intervalo residual do Nível I inválido.")
        plan = solve_pending_region(
            start, end, candidates, config, source_intervals=source_intervals,
        )
        plans.append({"segment_id": index, "source": residual, "plan": plan})
        if progress_callback:
            progress_callback({"stage": "plan", "current": index,
                               "total": len(manifest["pending_segments"]),
                               "message": f"Residual {index}/{len(manifest['pending_segments'])} planejado"})
    return {
        "manifest": manifest,
        "manifest_sha256": source_hash,
        "level1_dir": level1_dir,
        "infos": infos,
        "config": config,
        "plans": plans,
        "total_height": total,
    }
