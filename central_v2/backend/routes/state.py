import json
from pathlib import Path

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.state.manga_state import build_structural_state


def state_response(
    provider: str,
    manga_name: str,
    output_root: Path = OUTPUT_ROOT,
) -> bytes:
    payload = build_structural_state(
        output_root,
        provider,
        manga_name,
    )

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
