"""Projection of manual ranges recorded in the current official composition."""

import json
from pathlib import Path

from processamento.merge_manual.proposal import MANIFEST_NAME


def applied_manual_ranges(manga: Path, chapter: str) -> list[dict]:
    official = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter / "merge-manifest.json"
    try:
        payload = json.loads(official.read_text(encoding="utf-8"))
        composition = payload.get("composition") or {}
        declared = composition.get("manual_ranges")
        if declared is None:
            proposal_id = composition.get("manual_proposal_id")
            bounds = composition.get("manual_range")
            declared = [{"proposal_id": proposal_id, "global_start": bounds[0], "global_end": bounds[1]}]
        if not isinstance(declared, list) or not declared:
            return []
        result = []
        for item in declared:
            proposal_id = str(item["proposal_id"])
            start, end = int(item["global_start"]), int(item["global_end"])
            if not proposal_id or Path(proposal_id).name != proposal_id or start < 0 or end <= start:
                return []
            manifest_path = (manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO"
                             / "MERGE_MANUAL_PROPOSALS" / chapter / proposal_id / MANIFEST_NAME)
            proposal = json.loads(manifest_path.read_text(encoding="utf-8"))
            if proposal.get("proposal_id") != proposal_id or proposal.get("chapter") != chapter or proposal.get("status") != "EFETIVADO":
                return []
            result.append({"global_start": start, "global_end": end, "proposal_id": proposal_id})
        ordered = sorted(result, key=lambda value: value["global_start"])
        if any(left["global_end"] > right["global_start"] for left, right in zip(ordered, ordered[1:])):
            return []
        return ordered
    except (AttributeError, IndexError, KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return []
