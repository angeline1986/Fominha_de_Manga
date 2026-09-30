"""Manual ROI previews for Merged special treatments VI to VIII."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.execution import preview
from .artifact_paths import artifact_file
from .stages import LEVEL1, stage_chapter
from .manifests import _manifest_matches_merge, _stage_manifest
from .query import query_merged_level1

TREATMENTS = {"VI": "degrade", "VII": "estilizado", "VIII": "gradiente_suave"}


def query_manual_special(manga: Path, level: str) -> dict:
    if level not in TREATMENTS:
        raise ValueError("Nível especial inválido.")
    result = query_merged_level1(manga)
    for row in result["chapters"]:
        manifest = _stage_manifest(manga, LEVEL1, row["chapter"])
        ready = bool(row["merge_valid"] and _manifest_matches_merge(
            manifest, manga, row["chapter"]))
        row.update(level1_ready=ready, selectable=ready,
                   level1_pages=manifest.get("clean_artifacts", []))
    return result


def resolve_manual_page(manga: Path, chapter: str, filename: str) -> Path:
    row = next((item for item in query_manual_special(manga, "VI")["chapters"]
                if item["chapter"] == chapter and item["level1_ready"]), None)
    if row is None:
        raise ValueError("Capítulo sem Nível I íntegro.")
    folder = stage_chapter(manga, LEVEL1, chapter)
    result = artifact_file(folder, filename, "clean")
    if result is None:
        raise ValueError("Imagem não consta nos artefatos do Nível I.")
    return result


def run_manual_special(manga: Path, level: str, chapter: str, filename: str,
                       selections: list) -> dict:
    treatment = TREATMENTS.get(level)
    if treatment is None:
        raise ValueError("Nível especial inválido.")
    source = resolve_manual_page(manga, chapter, filename)
    payload = {"treatment": treatment, "level": "MERGED_NIVEL_I",
               "chapter": chapter, "filename": source.name,
               "expected_sha256": sha256(source), "selections": selections}
    return preview(manga, payload)
