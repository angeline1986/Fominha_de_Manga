"""Confined, read-only access to persisted Auto-Merge documents."""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Document:
    status: str
    data: dict | None = None
    error: str | None = None


def read_document(path: Path, boundary: Path) -> Document:
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(boundary.resolve()):
            return Document("invalid", error="Registro fora do diretório da obra.")
        if not resolved.exists():
            return Document("absent")
        data = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return Document("invalid", error="O registro não contém um objeto JSON.")
        return Document("recorded", data)
    except (OSError, ValueError, RuntimeError):
        return Document("invalid", error="Não foi possível ler o registro.")


def artifact_exists(directory: Path, name: str) -> bool:
    try:
        path = directory / name
        return path.resolve().is_relative_to(directory.resolve()) and path.is_file()
    except (OSError, ValueError, RuntimeError):
        return False
