"""Constrain isolated Combo workspace roots and source trees."""
import json
import tempfile
from pathlib import Path


def _safe_roots(source, output, provider, chapters):
    if not source.is_dir() or output is None:
        return False
    roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(), Path("/private/tmp").resolve()}
    if source.is_relative_to(output) or output.is_relative_to(source):
        return False
    if not any(output.is_relative_to(root) for root in roots):
        return False
    if not output.exists():
        return True
    marker = output / ".combo-workspace.json"
    try:
        if marker.is_symlink() or (output / ".combo-workspace").is_symlink():
            return False
        saved = json.loads(marker.read_text(encoding="utf-8"))
        return (saved.get("source") == str(source) and saved.get("provider") == provider
                and saved.get("chapters") == list(chapters))
    except (OSError, ValueError, TypeError):
        return False


def _reject_links(root):
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("SYMLINK_IN_SOURCE_TREE")
