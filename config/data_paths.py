from __future__ import annotations

import os
from pathlib import Path


DEFAULT_DATA_ROOT = Path.home() / "Documents" / "FominhaData"

DATA_ROOT = Path(
    os.environ.get("FOMINHA_DATA_ROOT", str(DEFAULT_DATA_ROOT))
).expanduser().resolve()

OUTPUT_ROOT = DATA_ROOT / "output"
