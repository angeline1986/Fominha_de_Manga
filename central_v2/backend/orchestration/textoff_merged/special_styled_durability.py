"""Filesystem durability helpers for coordinated Artístico publication."""
import os
from pathlib import Path


def replace(source: Path, destination: Path) -> None:
    """Rename atomically and sync both directory entries before proceeding."""
    source, destination = Path(source), Path(destination)
    os.replace(source, destination)
    for parent in {source.parent, destination.parent}:
        descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
