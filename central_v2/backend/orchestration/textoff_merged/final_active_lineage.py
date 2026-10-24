"""Resolve the active final-page lineage across Laboratory restorations."""
import hashlib
from pathlib import Path

from .laboratorio_final_history import archived_path


def active_page_rows(manifest: dict, page: str, folder) -> list[dict]:
    """Return the current ancestry, omitting branches abandoned by restoration."""
    folder = Path(folder).resolve()
    current = (manifest.get("pages") or {}).get(page)
    if not isinstance(current, dict):
        raise ValueError("Página final sem registro vigente.")
    events = [(index, entry) for index, entry in enumerate(manifest.get("history", []))
              if isinstance(entry, dict) and entry.get("page") == page]
    if not events:
        return [current]
    first = events[0][1].get("superseded")
    if not isinstance(first, dict):
        raise ValueError("Histórico final sem registro anterior.")
    active = [first]
    snapshots = {}
    for position, (index, event) in enumerate(events):
        old = event.get("superseded")
        if not isinstance(old, dict) or not _same(active[-1], old):
            raise ValueError("Sequência do Consolidado Final não é verificável.")
        snapshots[index] = list(active)
        next_row = events[position + 1][1].get("superseded") if position + 1 < len(events) else current
        if not isinstance(next_row, dict):
            raise ValueError("Histórico final sem sucessor verificável.")
        reason = event.get("reason")
        if reason == "laboratorio_restore":
            restored = _restored_branch(events, snapshots, index, event, page, folder)
            if not _same(restored[-1], next_row):
                raise ValueError("Restauração não corresponde à versão histórica escolhida.")
            active = [*restored[:-1], next_row]
        elif reason == "page_restoration":
            active = [next_row]
        else:
            active.append(next_row)
    if not _same(active[-1], current):
        raise ValueError("Linhagem final não alcança a página vigente.")
    return active


def _restored_branch(events, snapshots, current_index, event, page, folder):
    revision = event.get("restored_revision_id")
    if not isinstance(revision, str):
        raise ValueError("Restauração sem revisão histórica identificável.")
    for index, older in events:
        if index >= current_index:
            break
        digest = older.get("archived_sha256")
        expected = hashlib.sha256(f"{index}:{digest}".encode()).hexdigest()
        if revision == expected and archived_path(folder, older, page):
            return snapshots[index]
    raise ValueError("Revisão restaurada sem PNG histórico verificável.")


def _same(left, right):
    digest = left.get("sha256")
    return (isinstance(digest, str) and len(digest) == 64
            and isinstance(left.get("origin"), str)
            and digest == right.get("sha256")
            and left["origin"] == right.get("origin"))
