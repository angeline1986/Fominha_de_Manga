"""Publicação isolada de relatórios de reconhecimento transparente."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .transparent_recognition import recognize

SCHEMA = "transparent_recognition_from_level1_v1"


def publish(level1_dir: Path, destination: Path) -> dict:
    """Reconhece e grava apenas um relatório próprio, sem alterar as fontes."""
    report = recognize(level1_dir)
    if report.get("schema") != SCHEMA:
        raise ValueError("Contrato de reconhecimento incompatível.")

    target = Path(destination).resolve()
    payload = (json.dumps(
        report, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n").encode("utf-8")

    if target.exists():
        if not target.is_file() or target.is_symlink():
            raise ValueError("Destino existente não é um arquivo regular.")
        if target.read_bytes() == payload:
            return {"status": "reused", "path": str(target), **report}
        raise FileExistsError(
            "Relatório existente diverge da fonte. Nenhuma substituição realizada."
        )

    if target.parent.is_symlink():
        raise ValueError("Diretório de destino não pode ser um link simbólico.")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=".transparent-",
            suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

        # Criação exclusiva: nunca substituir um relatório existente.
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return {"status": "created", "path": str(target), **report}
