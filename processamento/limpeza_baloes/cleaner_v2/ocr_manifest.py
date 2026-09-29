"""Describe the OCR configuration that Panel Cleaner actually applies."""
from __future__ import annotations

import configparser
from pathlib import Path


def ocr_manifest_metadata(profile: Path) -> dict:
    config = configparser.ConfigParser()
    config.read(profile, encoding="utf-8")
    section = config["Preprocessor"]
    enabled = section.getboolean("ocr_enabled", fallback=False)
    language = section.get("ocr_language", fallback="unknown")
    engine = section.get("ocr_engine", fallback="auto")
    tesseract = section.getboolean("ocr_use_tesseract", fallback=False)

    if not enabled:
        effective_engine, effective_language = "disabled", None
    elif not tesseract:
        # Panel Cleaner forces MangaOCR when Tesseract is disabled, regardless
        # of ocr_engine=auto. MangaOCR is Japanese-only.
        effective_engine, effective_language = "MangaOCR", "jpn"
    else:
        effective_engine, effective_language = engine, language

    return {
        "enabled": enabled,
        "configured_language": language,
        "configured_engine": engine,
        "tesseract_enabled": tesseract,
        "effective_engine": effective_engine,
        "effective_language": effective_language,
        "detector_language_codes": ["ja", "eng"] if language.startswith("detect_") else [],
        "note": (
            "Detect per box labels Japanese and English, but with Tesseract disabled "
            "Panel Cleaner uses Japanese-only MangaOCR for OCR. Korean and Chinese "
            "OCR are not enabled by this profile."
        ) if enabled and not tesseract and language.startswith("detect_") else "",
    }
