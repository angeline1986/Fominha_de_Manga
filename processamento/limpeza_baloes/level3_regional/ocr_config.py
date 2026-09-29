"""Idioma/modelos configurados para o OCR regional do TextOff."""

OCR_LANGUAGE_GROUPS = (
    ("en", "ko"),
    ("ch_sim", "en"),
    ("ch_tra", "en"),
)


def create_readers(reader_factory, gpu=False):
    """Cria pares compatíveis com EasyOCR sem combinar scripts incompatíveis."""
    return tuple(
        (languages, reader_factory(list(languages), gpu=gpu))
        for languages in OCR_LANGUAGE_GROUPS
    )


def manifest_metadata(regions):
    detections = [
        detection
        for region in regions
        for detection in region.get("detections", [])
    ]
    return {
        "engine": "EasyOCR",
        "configured_languages": sorted({
            language
            for group in OCR_LANGUAGE_GROUPS
            for language in group
        }),
        "reader_language_groups": [list(group) for group in OCR_LANGUAGE_GROUPS],
        "detection_count": len(detections),
        "detection_count_by_reader": {
            "+".join(group): sum(
                tuple(item.get("reader_languages", [])) == group
                for item in detections
            )
            for group in OCR_LANGUAGE_GROUPS
        },
        "language_semantics": (
            "reader_languages registra os modelos usados; não identifica "
            "o idioma de cada texto detectado."
        ),
    }
