"""Replace Bubble Sommelier outputs while preserving legacy data on failure."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile


@contextmanager
def replace_execution_artifacts(output_dir: Path):
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
