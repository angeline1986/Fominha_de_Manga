"""Physical roots shared by Central V2 readers and writers."""
from pathlib import Path

IMAGE_DIR = "IMG"
SECONDARY_DIR = "FLUXO_SECUNDARIO"
MERGE_DIR = "02_MERGE"
PROCESSING_DIR = "01_MERGE_PROCESSAMENTO"
TEXT_OFF_DIR = "04_TEXTO_OFF"
PDF_MERGED_DIR = "03_PDF_MERGE"
AUTO_MERGE_STAGES = {
    1: "AUTO_MERGE", 2: "MERGE_LEVEL2", 3: "MERGE_LEVEL3",
    4: "MERGE_LEVEL4", 5: "MERGE_LEVEL5",
}
PROCESSING_STAGES = frozenset((*AUTO_MERGE_STAGES.values(), "BALANCE_STATUS"))
TEXT_OFF_RELATIVE = Path(SECONDARY_DIR) / TEXT_OFF_DIR


def images_root(manga: Path) -> Path:
    return Path(manga) / IMAGE_DIR


def secondary_root(manga: Path) -> Path:
    return Path(manga) / SECONDARY_DIR


def merge_root(manga: Path) -> Path:
    return secondary_root(manga) / MERGE_DIR


def textoff_root(manga: Path) -> Path:
    return Path(manga) / TEXT_OFF_RELATIVE


def pdf_root(manga: Path, source: str) -> Path:
    if source == "original":
        return Path(manga) / "PDF"
    if source == "merged":
        return secondary_root(manga) / PDF_MERGED_DIR
    raise ValueError("Origem do PDF inválida.")


def processing_stage_root(manga: Path, stage: str) -> Path:
    if stage not in PROCESSING_STAGES:
        raise ValueError("Estágio de processamento inválido.")
    return secondary_root(manga) / PROCESSING_DIR / stage
