"""Resolve one manifest-bound Merged image without accepting arbitrary paths."""
from pathlib import Path
import math

from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_file, json_file
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter
from .artifacts import read_json, sha256

LEVELS = {"MERGED_NIVEL_I": {"MERGE"},
          "MERGED_NIVEL_II": {LEVEL1, "MERGED_NIVEL_I"}}


def basename(value: object) -> str:
    if not isinstance(value, str) or value in {"", ".", ".."} or Path(value).name != value:
        raise ValueError("Capítulo ou arquivo inválido.")
    return value


def resolve_input(manga: Path, level: str, chapter: str, filename: str,
                  expected_sha256: str) -> dict:
    manga = manga.resolve()
    if not isinstance(level, str) or level not in LEVELS:
        raise ValueError("Nível Merged inválido.")
    folder = stage_chapter(manga, level, basename(chapter))
    manifest_path = json_file(folder, "clean-manifest.json").resolve()
    if not manifest_path.is_relative_to(manga):
        raise ValueError("Manifesto fora da obra.")
    manifest_hash = sha256(manifest_path)
    manifest = read_json(manifest_path)
    if sha256(manifest_path) != manifest_hash:
        raise ValueError("PROPOSTA_OBSOLETA: o manifesto mudou durante a leitura.")
    if manifest.get("integrity_ok") is not True or manifest.get("source_stage") not in LEVELS[level]:
        raise ValueError("Manifesto Merged não elegível.")
    names = manifest.get("clean_artifacts")
    if not isinstance(names, list):
        raise ValueError("Manifesto sem imagens limpas.")
    matches = [name for name in names if isinstance(name, str) and Path(name).name == basename(filename)]
    if len(matches) != 1:
        raise ValueError("Imagem ausente ou ambígua no manifesto.")
    source = artifact_file(folder, matches[0], "clean")
    if source is None or not source.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Imagem ausente ou fora do capítulo.")
    source = source.resolve()
    if not source.is_relative_to(manga):
        raise ValueError("Imagem fora da obra.")
    source_hash = sha256(source)
    if source_hash != expected_sha256:
        raise ValueError("PROPOSTA_OBSOLETA: a imagem de entrada mudou.")
    predecessors = [{"path": str(manifest_path), "sha256": manifest_hash}]
    if level == "MERGED_NIVEL_II":
        parent = stage_chapter(manga, LEVEL1, chapter)
        parent_manifest = json_file(parent, "clean-manifest.json").resolve()
        if not parent_manifest.is_relative_to(manga):
            raise ValueError("Predecessor fora da obra.")
        parent_hash = sha256(parent_manifest)
        if parent_hash != manifest.get("source_level1_manifest_sha256"):
            raise ValueError("PROPOSTA_OBSOLETA: o predecessor Nível I mudou.")
        predecessors.append({"path": str(parent_manifest), "sha256": parent_hash})
    return {"path": str(source), "sha256": source_hash, "level": level,
            "chapter": chapter, "filename": filename, "manga": str(manga),
            "predecessors": predecessors}


def validate_selections(selections: object) -> list[dict]:
    if not isinstance(selections, list) or not selections:
        raise ValueError("Selecione pelo menos uma ROI.")
    result = []
    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError("ROI inválida.")
        values = {key: selection.get(key) for key in ("x", "y", "width", "height")}
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in values.values()):
            raise ValueError("A ROI deve conter coordenadas numéricas finitas.")
        if values["width"] <= 0 or values["height"] <= 0:
            raise ValueError("ROI sem área.")
        result.append(values)
    return result


def assert_unchanged(source: dict) -> None:
    for item in [source, *source["predecessors"]]:
        if sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("PROPOSTA_OBSOLETA: entrada ou manifesto mudou durante a execução.")
