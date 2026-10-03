from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile

from central_v2.backend.orchestration.bubble_sommelier.runtime import validate_profile_id


STAGE = Path("FLUXO_SECUNDARIO") / "04_TEXTO_OFF" / "BUBBLE_SOMMELIER"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def merge_dir(manga: Path, chapter: str) -> Path:
    return manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter


def execution_dir(manga: Path, chapter: str) -> Path:
    return manga / STAGE / chapter


def report_path(manga: Path, chapter: str) -> Path:
    return execution_dir(manga, chapter) / "report.json"


def crops_dir(manga: Path, chapter: str) -> Path:
    return execution_dir(manga, chapter) / "crops"


@contextmanager
def replace_execution_artifacts(output_dir: Path):
    """Replace only BubbleSommelier-owned outputs, restoring legacy data on failure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = {item.name for item in output_dir.iterdir()}
    managed = {"report.json", "crops", "sommelier-report.json"}
    unexpected = entries - managed
    if unexpected:
        raise RuntimeError(
            f"Diretório de execução contém arquivos não gerenciados: {output_dir}"
        )

    legacy_report = output_dir / "sommelier-report.json"
    if legacy_report.exists() and not legacy_report.is_file():
        raise RuntimeError(f"Report legado não é um arquivo: {legacy_report}")

    backup_context = None
    backup_path = None
    if legacy_report.is_file():
        backup_context = tempfile.TemporaryDirectory(
            prefix="bubble-sommelier-legacy-", dir=output_dir.parent
        )
        backup_path = Path(backup_context.name) / legacy_report.name
        legacy_report.replace(backup_path)

    try:
        _remove_runtime_output(output_dir / "report.json")
        _remove_runtime_output(output_dir / "crops")
        yield
    except Exception:
        _remove_runtime_output(output_dir / "report.json")
        _remove_runtime_output(output_dir / "crops")
        if backup_path and backup_path.exists():
            backup_path.replace(legacy_report)
        raise
    else:
        if backup_path and backup_path.exists():
            backup_path.unlink()
    finally:
        if backup_context:
            backup_context.cleanup()


def _remove_runtime_output(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: p.name,
    )


def validate_selection(manga: Path, chapters: object) -> list[str]:
    if not isinstance(chapters, list) or not chapters:
        raise ValueError("Selecione ao menos um capítulo.")
    result = []
    for raw in chapters:
        chapter = str(raw)
        if chapter in {"", ".", ".."} or Path(chapter).name != chapter:
            raise ValueError(f"Capítulo inválido: {chapter}.")
        if not images(merge_dir(manga, chapter)):
            raise ValueError(f"Capítulo {chapter} não possui MERGEs válidos.")
        if chapter not in result:
            result.append(chapter)
    return result


def validate_report(report: object, profile_id: str) -> dict:
    validate_profile_id(profile_id)
    if not isinstance(report, dict) or report.get("status") != "completed":
        raise RuntimeError("O runtime não produziu um report concluído válido.")
    if report.get("profile_id") != profile_id:
        raise RuntimeError("O profile do report não corresponde ao profile solicitado.")

    checkpoints = report.get("checkpoints")
    result = checkpoints.get("result") if isinstance(checkpoints, dict) else None
    required = ("pages", "crops", "coverageGe075", "candidates")
    if not isinstance(result, dict) or any(
        isinstance(result.get(key), bool)
        or not isinstance(result.get(key), int)
        or result[key] < 0
        for key in required
    ):
        raise RuntimeError("O report não contém checkpoints.result válidos.")
    return report
