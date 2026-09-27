"""Public Level I query DTO; it does not decide workflow eligibility."""
from processamento.unificacao_imagens.auto_merge.documentos import Document


def _record(document: Document) -> dict:
    return {"status": document.status, "error": document.error, **(document.data or {})}


def level1_state(provider: str, manga: str, rows: list[dict]) -> dict:
    return {
        "provider": provider,
        "manga": manga,
        "chapters": [
            {
                "chapter": row["chapter"], "pages": row["pages"],
                "level1": _record(row["level1"]),
                "attempt": _record(row["attempt"]),
                "official": _record(row["official"]),
                "clean": row.get("clean", False),
                "pdf_merge": row.get("pdf_merge", False),
            }
            for row in rows
        ],
    }
