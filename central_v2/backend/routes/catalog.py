import json
from pathlib import Path

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.state.catalog import build_catalog


def catalog_response(output_root: Path = OUTPUT_ROOT):
    payload = build_catalog(output_root)
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
