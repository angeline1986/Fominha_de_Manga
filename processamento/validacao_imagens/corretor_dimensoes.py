"""Aplicação segura de uma correção proporcional em uma imagem de IMG."""

from pathlib import Path
import tempfile

from PIL import Image


def corrigir_imagem(source: Path, expected: tuple[int, int], target_width: int) -> dict:
    """Preserva o original em _old e troca apenas a página confirmada."""
    if target_width <= 0:
        raise ValueError("Largura de destino inválida.")
    backup = source.with_name(f"{source.stem}_old{source.suffix}")
    if backup.exists() or backup.is_symlink():
        raise ValueError(f"A correção foi bloqueada: {backup.name} já existe.")
    temporary = None
    try:
        with Image.open(source) as image:
            if image.size != expected:
                raise ValueError("A imagem mudou desde a análise. Execute a validação novamente.")
            target_height = max(1, round(image.height * target_width / image.width))
            corrected = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            with tempfile.NamedTemporaryFile(
                prefix=f".{source.stem}-validacao-", suffix=source.suffix,
                dir=source.parent, delete=False,
            ) as handle:
                temporary = Path(handle.name)
            corrected.save(temporary, format=image.format)
        with Image.open(temporary) as check:
            if check.size != (target_width, target_height):
                raise ValueError("A imagem corrigida não passou na verificação.")
        if backup.exists() or backup.is_symlink():
            raise ValueError(f"A correção foi bloqueada: {backup.name} já existe.")
        source.rename(backup)
        try:
            temporary.replace(source)
        except Exception:
            backup.rename(source)
            raise
        return {"file": source.name, "backup": backup.name,
                "from": list(expected), "to": [target_width, target_height]}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
