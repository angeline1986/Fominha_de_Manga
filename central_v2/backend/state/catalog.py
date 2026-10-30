from pathlib import Path

from .sorting import natural_sort_key as _natural_key
from .work_layout import images_root


CATALOG_PROVIDERS = ("comix", "mangago", "ridi")


def build_catalog(output_root: Path) -> dict[str, list[str]]:
    catalog: dict[str, list[str]] = {}

    for provider in CATALOG_PROVIDERS:
        provider_dir = output_root / provider

        if not provider_dir.is_dir():
            catalog[provider] = []
            continue

        mangas = [
            path.name
            for path in provider_dir.iterdir()
            if path.is_dir() and images_root(path).is_dir()
        ]

        catalog[provider] = sorted(mangas, key=_natural_key)

    return catalog
