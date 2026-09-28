"""Materialize only Level IV intervals approved by the global composition."""
import os
import tempfile
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens.auto_merge.materializacao_nivel3 import (
    render_source_interval,
)


def _save_exclusive(image: Image.Image, path: Path) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".am4-", suffix=".png", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        image.save(temporary, format="PNG", optimize=False)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def materialize_level4(chapter: Path, infos: list, artifacts: list[dict], stage: Path) -> list[dict]:
    stage.mkdir(parents=True, exist_ok=False)
    created, saved = [], []
    try:
        for item in artifacts:
            start, end = item["global_start"], item["global_end"]
            path = stage / item["file"]
            _save_exclusive(render_source_interval(chapter, infos, start, end), path)
            created.append(path)
            with Image.open(path) as image:
                if image.height != end - start or image.width != item["width"]:
                    raise ValueError("Dimensão divergente no artefato do Nível IV.")
            saved.append(item)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        stage.rmdir()
        raise
    return saved
