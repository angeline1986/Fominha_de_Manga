from pathlib import Path

import pytest

from processamento.limpeza_baloes.pipeline.contracts import (
    ROUTE_LEVEL_3,
    ROUTE_LEVEL_4,
    ROUTE_LEVEL_5,
    ROUTE_PROTECT,
    ROUTE_REVIEW,
)
from processamento.limpeza_baloes.pipeline.manifests import sha256_file
from processamento.limpeza_baloes.pipeline.state import (
    STATUS_PENDING,
    STATUS_PROTECTED,
    STATUS_REVIEW,
    assert_current_sources,
    build_page_state,
    page_progress,
    resolve_region,
)


def _audit(raw: Path, routes):
    candidates = []
    for i, route in enumerate(routes, 1):
        candidates.append({
            "candidate_id": f"ctd-{i:04d}-test",
            "source_index": i,
            "bbox": [i, i, i + 10, i + 10],
            "eligibility": {"decision": "INCERTO", "reason_codes": ["TEST"]},
            "visual_profile": {"profile": "INCERTO", "reason_codes": ["TEST"]},
            "routing": {"destination": route, "reason_codes": ["TEST_ROUTE"]},
        })
    return {
        "schema_version": 1,
        "algorithm": "test",
        "milestone": "1C",
        "mode": "AUDIT_ONLY",
        "source": {
            "page_key": "page-001",
            "raw_json": raw.name,
            "raw_json_sha256": sha256_file(raw),
            "image_path": None,
            "original_path": None,
            "resolved_source_image": None,
            "scale": 1.0,
        },
        "level1": {
            "candidates_detected": len(candidates),
            "candidates": candidates,
        },
        "level2": {},
        "safety": {"pixel_mutation_performed": False},
    }


def test_initial_state_and_page_projection(tmp_path):
    raw = tmp_path / "page-001#raw.json"
    image = tmp_path / "page-001.png"
    raw.write_text('{"blk_list":[]}', encoding="utf-8")
    image.write_bytes(b"not-an-image-but-stable-for-hash")

    state = build_page_state(
        _audit(raw, [ROUTE_LEVEL_3, ROUTE_LEVEL_4, ROUTE_LEVEL_5,
                     ROUTE_PROTECT, ROUTE_REVIEW]),
        image,
    )

    assert state["regions"][0]["status"] == STATUS_PENDING
    assert state["regions"][3]["status"] == STATUS_PROTECTED
    assert state["regions"][4]["status"] == STATUS_REVIEW
    assert state["regions"][0]["reason_codes"] == ["TEST_ROUTE"]
    assert page_progress(state) == {
        "level3_pending": True,
        "level4_pending": True,
        "level5_pending": True,
        "review_pending": True,
        "has_residual": True,
    }


def test_resolved_region_disappears_only_from_its_queue(tmp_path):
    raw = tmp_path / "page-001#raw.json"
    image = tmp_path / "page-001.png"
    raw.write_text("{}", encoding="utf-8")
    image.write_bytes(b"source")

    state = build_page_state(_audit(raw, [ROUTE_LEVEL_3, ROUTE_LEVEL_5]), image)
    state = resolve_region(state, "ctd-0001-test", resolved_by="LEVEL_3")

    progress = page_progress(state)
    assert progress["level3_pending"] is False
    assert progress["level5_pending"] is True
    assert progress["has_residual"] is True


def test_all_resolved_has_no_residual(tmp_path):
    raw = tmp_path / "page-001#raw.json"
    image = tmp_path / "page-001.png"
    raw.write_text("{}", encoding="utf-8")
    image.write_bytes(b"source")

    state = build_page_state(_audit(raw, [ROUTE_LEVEL_3]), image)
    state = resolve_region(state, "ctd-0001-test", resolved_by="LEVEL_3")

    assert page_progress(state) == {
        "level3_pending": False,
        "level4_pending": False,
        "level5_pending": False,
        "review_pending": False,
        "has_residual": False,
    }


def test_source_change_fails_closed(tmp_path):
    raw = tmp_path / "page-001#raw.json"
    image = tmp_path / "page-001.png"
    raw.write_text("{}", encoding="utf-8")
    image.write_bytes(b"source")

    state = build_page_state(_audit(raw, [ROUTE_LEVEL_3]), image)
    assert_current_sources(state, raw_json=raw, source_image=image)

    image.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="STALE_STATE"):
        assert_current_sources(state, raw_json=raw, source_image=image)


def test_protected_and_review_do_not_enter_level_queues(tmp_path):
    raw = tmp_path / "page-001#raw.json"
    image = tmp_path / "page-001.png"
    raw.write_text("{}", encoding="utf-8")
    image.write_bytes(b"source")

    state = build_page_state(_audit(raw, [ROUTE_PROTECT, ROUTE_REVIEW]), image)
    progress = page_progress(state)

    assert progress["level3_pending"] is False
    assert progress["level4_pending"] is False
    assert progress["level5_pending"] is False
    assert progress["review_pending"] is True
    assert progress["has_residual"] is True


def test_rejects_old_flat_audit_contract(tmp_path):
    raw = tmp_path / "page-001#raw.json"
    image = tmp_path / "page-001.png"
    raw.write_text("{}", encoding="utf-8")
    image.write_bytes(b"source")
    old_shape = {
        "page_key": "page-001",
        "raw_json": raw.name,
        "raw_json_sha256": sha256_file(raw),
        "candidates": [],
    }
    with pytest.raises(ValueError, match="source identity"):
        build_page_state(old_shape, image)
