"""Verify that a brush input still matches the official final version."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

LABORATORY_RESTORE_REQUIRED = "Restaure a página do Laboratório antes de executar outro Pincel."


def require_official_paint_source(record):
    if record.get("origin") == "LABORATORIO":
        raise ValueError(LABORATORY_RESTORE_REQUIRED)


def assert_input_unchanged(manga, source, manifest_path, manifest_hash):
    path = Path(source["path"]).resolve()
    if (not path.is_relative_to(Path(manga).resolve()) or not path.is_file()
            or sha256(path) != source["sha256"]
            or Path(source["consolidated_manifest"]).resolve() != manifest_path.resolve()
            or sha256(manifest_path) != manifest_hash
            or source.get("consolidated_manifest_sha256") != manifest_hash):
        raise ValueError("Versão vigente mudou durante a execução do Pincel.")
