"""List image files without following links outside their chapter folder."""
import os
from pathlib import Path

from central_v2.backend.state.manga_state import IMAGE_EXTENSIONS
from central_v2.backend.state.sorting import natural_sort_key


def _images(folder):
    root, files = folder.resolve(), []
    with os.scandir(folder) as entries:
        for entry in entries:
            path = Path(entry.path)
            if (path.suffix.lower() not in IMAGE_EXTENSIONS
                    or path.stem.lower().endswith("_old")):
                continue
            try:
                if not entry.is_file(follow_symlinks=True):
                    continue
                if entry.is_symlink() and not path.resolve().is_relative_to(root):
                    continue
            except OSError:
                continue
            files.append(path)
    return sorted(files, key=lambda path: natural_sort_key(path.name))
