"""Observe registry-mapped new artifact trees without affecting legacy reads."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .artifact_migration import REGISTRY_PATH
from .artifact_validation import validate_stage_chapter


logger = logging.getLogger(__name__)


def observe_shadow_read(
    manga: Path,
    stage_id: str,
    chapter: str,
    *,
    registry_path: Path = REGISTRY_PATH,
) -> None:
    """Log M4 comparison results; this function never supplies consumer data."""
    legacy_path = target_path = None
    try:
        registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
        entry = next(
            item for item in registry.get("stages", [])
            if item.get("stage_id") == stage_id
        )
        legacy_path = f"{entry.get('legacy_path')}/{chapter}"
        target_path = f"{entry.get('target_path')}/{chapter}"
        if (registry.get("legacy_read_enabled") is not True
                or registry.get("new_read_enabled") is not True
                or registry.get("read_authority") != "legacy"
                or entry.get("read_authority") != "legacy"
                or entry.get("dual_write") is not True):
            return

        result = validate_stage_chapter(
            manga, stage_id, chapter, registry_path=registry_path
        )
        status = result["comparison_status"]
        artifacts = result.get("artifacts", [])
        differences = [
            item.get("artifact") for item in artifacts
            if item.get("comparison_status") != "MATCH"
        ]
        summary = ",".join(str(item) for item in differences[:8])
        report = (
            "SHADOW_READ stage=%s chapter=%s legacy_path=%s target_path=%s "
            "comparison_status=%s artifact_count=%d differences=%s"
        )
        values = (
            stage_id, chapter, result.get("legacy_path"), result.get("target_path"),
            status, len(artifacts), summary,
        )
        if status in {"MATCH", "STRUCTURAL_MATCH"}:
            logger.info(report, *values)
        else:
            logger.warning(report, *values)
    except FileNotFoundError as exc:
        if str(exc).startswith("Ambos os artefatos estão ausentes:"):
            logger.warning(
                "SHADOW_READ stage=%s chapter=%s legacy_path=%s target_path=%s "
                "comparison_status=MISSING_LEGACY artifact_count=0 "
                "differences=legacy_and_target_missing",
                stage_id, chapter, legacy_path, target_path,
            )
            return
        logger.exception(
            "SHADOW_READ_ERROR stage=%s chapter=%s legacy_path=%s target_path=%s",
            stage_id, chapter, legacy_path, target_path,
        )
    except Exception:
        logger.exception(
            "SHADOW_READ_ERROR stage=%s chapter=%s legacy_path=%s target_path=%s",
            stage_id, chapter, legacy_path, target_path,
        )
