"""Read existing Mapear soft-gradient results for a Sommelier report."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.artifact_paths import (
    artifact_file, json_file,
)
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL3, stage_chapter


FEATURE_FIELDS = (
    "reason", "interior_pixels", "saturated_ratio", "dominant_hue_ratio",
    "gray_std_bright_pixels", "chroma_ratio_bright_pixels",
)


def _unavailable(status: str, diagnostic: str) -> dict:
    return {
        "source": "styled-balloon-report",
        "available": False,
        "status": status,
        "diagnostic": diagnostic,
        "soft_gradient": {"count": 0, "occurrences": []},
    }


def _report_path(manga: Path, chapter: str) -> Path | None:
    chapter_dir = stage_chapter(manga, LEVEL3, chapter)
    manifest_path = json_file(chapter_dir, "clean-manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        manifest = None
    except (OSError, json.JSONDecodeError, TypeError):
        manifest = None

    if isinstance(manifest, dict):
        report = artifact_file(chapter_dir, manifest.get("report"), "json")
        if report is not None:
            return report
    fallback = json_file(chapter_dir, "styled-balloon-report.json")
    return fallback if fallback.is_file() else None


def _occurrences(report: object) -> list[dict]:
    if not isinstance(report, dict) or not isinstance(report.get("pages"), list):
        raise ValueError("Relatório Mapear sem lista de páginas válida.")

    found = []
    for page in report["pages"]:
        if not isinstance(page, dict) or not isinstance(page.get("source"), str):
            raise ValueError("Página inválida no relatório Mapear.")
        candidates = page.get("styled_balloon_candidates")
        if not isinstance(candidates, list):
            raise ValueError("Lista de candidatos inválida no relatório Mapear.")
        for item in candidates:
            if not isinstance(item, dict) or not isinstance(item.get("features"), dict):
                raise ValueError("Ocorrência inválida no relatório Mapear.")
            features = item["features"]
            candidate = features.get("candidate")
            candidate_type = item.get("candidate_type")
            if not isinstance(candidate, bool) or not isinstance(candidate_type, str):
                raise ValueError("Classificação inválida no relatório Mapear.")
            if candidate is not True or candidate_type != "soft_gradient":
                continue

            occurrence = dict(item)
            occurrence["page"] = page["source"]
            occurrence["candidate"] = candidate
            for field in FEATURE_FIELDS:
                if field in features:
                    occurrence[field] = features[field]
            found.append(occurrence)
    return found


def load_mapear_results(manga: Path, chapter: str) -> dict:
    """Load and filter the persisted Mapear report without running Mapear."""
    try:
        path = _report_path(manga, chapter)
    except (OSError, TypeError, ValueError):
        return _unavailable("unavailable", "styled_balloon_report_not_found")
    if path is None:
        return _unavailable("unavailable", "styled_balloon_report_not_found")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        occurrences = _occurrences(report)
    except FileNotFoundError:
        return _unavailable("unavailable", "styled_balloon_report_not_found")
    except json.JSONDecodeError:
        return _unavailable("invalid", "styled_balloon_report_invalid_json")
    except (OSError, TypeError, ValueError):
        return _unavailable("invalid", "styled_balloon_report_invalid_contract")

    return {
        "source": "styled-balloon-report",
        "available": True,
        "status": "available",
        "soft_gradient": {"count": len(occurrences), "occurrences": occurrences},
    }


def incorporate_mapear_results(report: dict, manga: Path, chapter: str) -> dict:
    """Return the Sommelier report with an additive Mapear section."""
    return {**report, "mapear": load_mapear_results(manga, chapter)}
