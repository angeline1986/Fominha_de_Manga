from contextlib import contextmanager
import hashlib
import json
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


def validate_chapter_id(chapter: object) -> str:
    if (
        not isinstance(chapter, str)
        or not chapter
        or chapter in {".", ".."}
        or "/" in chapter
        or "\\" in chapter
        or "\x00" in chapter
    ):
        raise ValueError("chapter ausente ou inválido.")
    return chapter


def validate_crop_identity(identity: object) -> str:
    if (
        not isinstance(identity, str)
        or not identity
        or identity in {".", ".."}
        or any(not (char.isascii() and (char.isalnum() or char in "_-")) for char in identity)
        or not identity[0].isascii()
        or not identity[0].isalnum()
    ):
        raise ValueError("identity ausente ou inválida.")
    return identity


def load_review_report(manga: Path, chapter: str, *, stage_dir: Path | None = None) -> dict:
    chapter = validate_chapter_id(chapter)
    if not merge_dir(manga, chapter).is_dir():
        raise FileNotFoundError(f"Capítulo não encontrado: {chapter}")

    path = Path(stage_dir) / "report.json" if stage_dir is not None else report_path(manga, chapter)
    if not path.is_file():
        raise FileNotFoundError(f"Report não encontrado para o capítulo {chapter}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Report do BubbleSommelier inválido.") from exc

    if not isinstance(report, dict):
        raise ValueError("Report do BubbleSommelier inválido.")
    profile_id = report.get("profile_id")
    validate_report(report, profile_id)
    pages = report.get("pages")
    if not isinstance(pages, list):
        raise ValueError("Report sem páginas válidas.")

    identities = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("page_id"), str):
            raise ValueError("Report contém uma página inválida.")
        bubbles = page.get("bubbles")
        if not isinstance(bubbles, list):
            raise ValueError("Report contém uma lista de bubbles inválida.")
        for bubble in bubbles:
            if not isinstance(bubble, dict):
                raise ValueError("Report contém um bubble inválido.")
            identity = validate_crop_identity(bubble.get("identity"))
            crop = bubble.get("crop")
            if (
                not isinstance(crop, dict)
                or not isinstance(crop.get("sha256"), str)
                or not isinstance(bubble.get("candidate"), bool)
            ):
                raise ValueError("Report contém dados de crop/candidate inválidos.")
            if identity in identities:
                raise ValueError("Report contém identities duplicadas.")
            identities.add(identity)
    return report


def crop_path(manga: Path, chapter: str, identity: str, *, stage_dir: Path | None = None) -> Path:
    chapter = validate_chapter_id(chapter)
    identity = validate_crop_identity(identity)

    manga_root = manga.resolve(strict=True)
    stage_root = (manga / STAGE).resolve(strict=True) if stage_dir is None else None
    if stage_root is not None and not stage_root.is_relative_to(manga_root):
        raise ValueError("Diretório de crops fora da obra.")
    chapter_root = (Path(stage_dir) if stage_dir is not None else execution_dir(manga, chapter)).resolve(strict=True)
    if not chapter_root.is_relative_to(stage_root if stage_root is not None else manga_root):
        raise ValueError("Diretório do capítulo fora da curadoria.")

    crops_entry = (Path(stage_dir) if stage_dir is not None else execution_dir(manga, chapter)) / "crops"
    if crops_entry.is_symlink():
        raise ValueError("Diretório de crops inválido.")
    crops_root = crops_entry.resolve(strict=True)
    if crops_root.parent != chapter_root or crops_root.name != "crops":
        raise ValueError("Diretório de crops fora do capítulo.")

    target = (crops_root / f"{identity}.png").resolve(strict=True)
    if not target.is_relative_to(crops_root) or not target.is_file():
        raise FileNotFoundError(f"Crop não encontrado: {identity}")
    return target


def crop_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
