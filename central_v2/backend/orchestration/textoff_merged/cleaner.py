"""Adapter from TextOff Merged use cases to the Cleaner V2 domain API."""
import json
import time
from pathlib import Path

from processamento.limpeza_baloes.cleaner_v2 import integration
from .level1_cleaner import clean_level1_chapter


def run_cleaner_v2(images, target, *, source_stage, progress_job, chapter_name, level1_only=False):
    if level1_only:
        return clean_level1_chapter(
            images,
            target,
            source_stage=source_stage,
            progress_job=progress_job,
            chapter_name=chapter_name,
        )
    options = {
        "source_stage": source_stage,
        "progress_job": progress_job,
        "chapter_name": chapter_name,
    }
    started = time.perf_counter()
    result = integration.clean_chapter(images, target, **options)
    manifest_path = Path(target) / "clean-manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Cleaner V2 não gerou o manifesto do TextOff Merged.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["execution"] = {
            "duration_seconds": round(time.perf_counter() - started, 3),
            "duration_scope": "chapter_total_including_legacy_level2_and_promotion",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, TypeError):
        raise RuntimeError("Não foi possível registrar a duração no manifesto do TextOff Merged.")
    return result
