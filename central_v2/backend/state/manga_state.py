from pathlib import Path

from central_v2.backend.state.catalog import CATALOG_PROVIDERS
from central_v2.backend.state.sorting import natural_sort_key as _natural_key


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _is_active_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and not path.stem.lower().endswith("_old")
    )


def resolve_manga(
    output_root: Path,
    provider: str,
    manga_name: str,
) -> Path:
    if provider not in CATALOG_PROVIDERS:
        raise ValueError("Provider inválido.")

    base = (output_root / provider).resolve()
    target = (base / manga_name).resolve()

    if not target.is_relative_to(base) or not target.is_dir():
        raise ValueError("Obra inválida.")

    return target


def build_structural_state(
    output_root: Path,
    provider: str,
    manga_name: str,
) -> dict:
    manga = resolve_manga(output_root, provider, manga_name)
    img_root = manga / "IMG"

    chapter_names = []

    if img_root.is_dir():
        chapter_names = sorted(
            [
                path.name
                for path in img_root.iterdir()
                if path.is_dir()
                and any(_is_active_image(file) for file in path.iterdir())
            ],
            key=_natural_key,
        )

    return {
        "provider": provider,
        "manga": manga_name,
        "chapters": chapter_names,
        "summary": {
            "chapters": len(chapter_names),
        },
    }
