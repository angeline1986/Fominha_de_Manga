"""Shared status vocabulary and safe helpers for Combo Turbo validation."""
from pathlib import Path
import string

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file

STATUSES = {"REUSABLE", "MISSING", "STALE", "INVALID", "UNVERIFIED"}
STAGES = {"SOLIDOS", "GLASS"}


def result(stage, chapter, page, status, *, integrity=False, check=False,
           artifact=None, mask=None, manifest=None, reasons=(), **extra):
    return {
        "stage": stage, "chapter": chapter, "page": page, "status": status,
        "integrity_ok": integrity, "check_verified": check,
        "artifact_sha256": artifact, "mask_sha256": mask,
        "manifest_sha256": manifest, "reasons": list(dict.fromkeys(reasons)),
        **extra,
    }


def valid_page_id(page):
    return (isinstance(page, str) and page not in {"", ".", ".."}
            and Path(page).name == page and "\\" not in page
            and Path(page).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"})


def valid_chapter_id(chapter):
    return (isinstance(chapter, str) and chapter not in {"", ".", ".."}
            and Path(chapter).name == chapter and "\\" not in chapter)


def safe_file(root: Path, reference: str) -> Path:
    return contained_file(root, reference)


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return image.size


def check_digest_field(manifest: dict):
    for key in ("check_sha256", "source_check_manifest_sha256"):
        value = manifest.get(key)
        if isinstance(value, str) and len(value) == 64:
            return value
    source = manifest.get("source_check")
    if isinstance(source, dict):
        value = source.get("sha256")
        if isinstance(value, str) and len(value) == 64:
            return value
    return None


def is_sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in string.hexdigits for character in value))
