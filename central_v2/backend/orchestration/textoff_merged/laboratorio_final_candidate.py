"""Authenticate a Laboratory preview before offering it for final review."""
from pathlib import Path
import re

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import (
    contained_file, read_json, sha256,
)
from central_v2.backend.orchestration.textoff_special.catalog import ROOT, treatment_for

STAGING = ROOT / "reports/experimentos/textoff_laboratorio"
SOLID_PREVIEWS = "_laboratorio_solidos_previews"
TREATMENTS = {"degrade", "estilizado", "gradiente_suave", "solidos"}
RUN_ID = re.compile(r"[0-9a-f]{32}\Z")


def candidate(manga: Path, chapter: str, page: str, treatment: str,
              run_id: str, output_root: Path) -> dict:
    if treatment not in TREATMENTS or not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("Tratamento ou execução do Laboratório inválidos.")
    if treatment == "solidos":
        return _solid(manga, chapter, page, run_id, output_root)
    folder = (STAGING / run_id).resolve()
    if not folder.is_relative_to(STAGING.resolve()):
        raise ValueError("Execução fora do Laboratório.")
    manifest = read_json(folder / "manifest.json")
    request = read_json(folder / "request.json")
    source = request.get("source")
    validation = manifest.get("validation")
    if not isinstance(source, dict) or not isinstance(validation, dict):
        raise ValueError("Manifesto experimental incompleto.")
    raw_source_path = source.get("path")
    if not isinstance(raw_source_path, str) or not Path(raw_source_path).is_absolute():
        raise ValueError("Origem experimental inválida.")
    source_path = Path(raw_source_path).resolve()
    if (manifest.get("run_id") != run_id or request.get("run_id") != run_id
            or request.get("treatment") != treatment
            or not isinstance(manifest.get("treatment"), dict)
            or manifest["treatment"].get("algorithm") != treatment_for(treatment).algorithm
            or manifest.get("source") != source
            or manifest.get("execution_status") != "succeeded"
            or source.get("level") != "LAB"
            or source.get("manga") != str(manga)
            or source.get("chapter") != chapter or source.get("filename") != page
            or not source_path.is_relative_to(manga)):
        raise ValueError("Resultado não corresponde à página selecionada.")
    result = contained_file(folder, manifest["result_file"])
    digest = validation.get("result_sha256")
    snapshot = contained_file(folder, "input/source.png")
    if (not isinstance(source.get("sha256"), str)
            or sha256(snapshot) != source["sha256"] or sha256(result) != digest):
        raise ValueError("Resultado do Laboratório com hash divergente.")
    return {"path": result, "sha256": digest, "source_sha256": source["sha256"],
            "treatment": treatment, "run_id": run_id,
            "artifact": manifest["result_file"]}


def _solid(manga: Path, chapter: str, page: str, run_id: str,
           output_root: Path) -> dict:
    root = (Path(output_root).resolve() / SOLID_PREVIEWS).resolve()
    folder = (root / run_id).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("Execução fora do Laboratório.")
    meta = read_json(folder / "manifest.json")
    if (meta.get("schema") != "laboratorio_solidos_preview_v1"
            or meta.get("preview_only") is not True
            or meta.get("provider") != manga.parent.name
            or meta.get("manga") != manga.name
            or meta.get("chapter") != chapter or meta.get("page") != page):
        raise ValueError("Resultado Sólidos não corresponde à página selecionada.")
    result = contained_file(folder, "preview.png")
    digest = meta.get("preview_sha256")
    if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not isinstance(meta.get("source_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", meta["source_sha256"])
            or sha256(result) != digest):
        raise ValueError("Resultado Sólidos com hash divergente.")
    return {"path": result, "sha256": digest,
            "source_sha256": meta["source_sha256"], "treatment": "solidos",
            "run_id": run_id, "artifact": "preview.png"}


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        if image.format != "PNG":
            raise ValueError("O resultado deve ser um PNG válido.")
        size = image.size
        image.verify()
    if min(size) <= 0:
        raise ValueError("Dimensões de imagem inválidas.")
    return size
