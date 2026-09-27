"""Append-only operational events for Central V2 Auto-Merge Level I."""
import json
import os
from pathlib import Path


def record_event(manga: Path, event: dict) -> None:
    directory = manga / "FLUXO_SECUNDARIO" / "PROCESSING_LOG"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "auto-merge-level1-events.jsonl"
    payload = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        remaining = memoryview(payload)
        while remaining:
            remaining = remaining[os.write(descriptor, remaining):]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
