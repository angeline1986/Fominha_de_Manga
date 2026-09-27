"""Exclusive filesystem writes for Level I stage and official manifests."""
import json
import os
import tempfile
from pathlib import Path


def write_json_exclusive(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, name = tempfile.mkstemp(prefix=".am1-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def copy_file_exclusive(source: Path, destination: Path) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".am1-", dir=destination.parent)
    temporary = Path(name)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            while block := reader.read(1024 * 1024):
                writer.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
