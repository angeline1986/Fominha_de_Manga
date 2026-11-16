from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


FILENAME = "selected-proposals.json"


def selection_path(manga: Path, chapter: str) -> Path:
    return Path(manga) / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_MANUAL_PROPOSALS" / str(chapter) / FILENAME


def read_selected_ids(manga: Path, chapter: str) -> list[str]:
    path = selection_path(manga, chapter)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Registro das faixas selecionadas está ilegível.") from exc
    ids = data.get("proposal_ids") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("schema") != "manual_merge_selected_v1" or not isinstance(ids, list) or any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Registro das faixas selecionadas está inválido.")
    return ids


def write_selected_ids(manga: Path, chapter: str, ids: list[str]) -> None:
    path = selection_path(manga, chapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{FILENAME}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema": "manual_merge_selected_v1", "proposal_ids": ids}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def active_selected_ranges(manga: Path, chapter: str) -> list[dict]:
    ranges = []
    for proposal_id in read_selected_ids(manga, chapter):
        if Path(proposal_id).name != proposal_id:
            raise ValueError("Identificador de faixa selecionada inválido.")
        path = selection_path(manga, chapter).parent / proposal_id / "merge-manual-manifest.json"
        try:
            proposal = json.loads(path.read_text(encoding="utf-8"))
            if proposal.get("status") == "EFETIVADO":
                continue
            block = proposal["source_block"]
            start, end = int(block["global_start"]), int(block["global_end"])
            if proposal.get("proposal_id") != proposal_id or proposal.get("chapter") != chapter or proposal.get("status") != "PROPOSTA_GERADA" or end <= start:
                raise ValueError("Faixa confirmada incompatível com seu manifesto.")
        except (AttributeError, OSError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Não foi possível ler uma faixa confirmada.") from exc
        ranges.append({"proposal_id": proposal_id, "global_start": start, "global_end": end})
    return ranges


def remaining_intervals(pending: list[tuple[int, int]], chosen: list[tuple[int, int]]) -> list[tuple[int, int]]:
    remaining = sorted(pending)
    for start, end in sorted(chosen):
        updated = []
        for left, right in remaining:
            if end <= left or start >= right:
                updated.append((left, right))
            else:
                if left < start:
                    updated.append((left, start))
                if end < right:
                    updated.append((end, right))
        remaining = updated
    return remaining
