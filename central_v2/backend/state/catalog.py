import re
from pathlib import Path


CATALOG_PROVIDERS = ("comix", "mangago", "ridi")


def _natural_key(value: str) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


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
            if path.is_dir() and (path / "IMG").is_dir()
        ]

        catalog[provider] = sorted(mangas, key=_natural_key)

    return catalog
