"""Contrato M0: estado regional sintético, sem imagens reais ou classificadores."""

from copy import deepcopy

import pytest

from processamento.limpeza_baloes.pipeline.contracts import (
    ROUTE_LEVEL_3, ROUTE_LEVEL_4, ROUTE_LEVEL_5, ROUTE_PROTECT, ROUTE_REVIEW,
)
from processamento.limpeza_baloes.pipeline.manifests import sha256_file
from processamento.limpeza_baloes.pipeline.state import (
    STATUS_PENDING, STATUS_PROTECTED, STATUS_RESOLVED, STATUS_REVIEW,
    build_page_state, page_progress, resolve_region,
)


@pytest.fixture
def make_state(tmp_path):
    # Arquivos sintéticos servem apenas à identidade/hash, sem decodificação.
    raw = tmp_path / "synthetic#raw.json"
    source = tmp_path / "synthetic-source.bin"
    raw.write_text("{}", encoding="utf-8")
    source.write_bytes(b"M0 synthetic source; no real pixels")

    def build(*routes):
        candidates = [
            {
                "candidate_id": f"region-{index}",
                "source_index": index,
                "bbox": [index * 20, 0, index * 20 + 10, 10],
                "routing": {"destination": route, "reason_codes": ["M0_FIXTURE"]},
            }
            for index, route in enumerate(routes)
        ]
        return build_page_state({
            "source": {
                "page_key": "synthetic",
                "raw_json": raw.name,
                "raw_json_sha256": sha256_file(raw),
            },
            "level1": {"candidates": candidates},
        }, source)

    return build


def test_protected_only_is_valid_resolution_without_residual(make_state):
    assert ROUTE_PROTECT == "PROTEGER"
    state = make_state(ROUTE_PROTECT, ROUTE_PROTECT)
    assert all(r["status"] == STATUS_PROTECTED for r in state["regions"])
    assert page_progress(state) == {
        "level3_pending": False, "level4_pending": False,
        "level5_pending": False, "review_pending": False, "has_residual": False,
    }


def test_review_only_requires_human_decision_without_automatic_queue(make_state):
    state = make_state(ROUTE_REVIEW)
    assert state["regions"][0]["status"] == STATUS_REVIEW
    assert page_progress(state) == {
        "level3_pending": False, "level4_pending": False,
        "level5_pending": False, "review_pending": True, "has_residual": True,
    }


@pytest.mark.parametrize("route,queue", [
    (ROUTE_LEVEL_3, "level3_pending"),
    (ROUTE_LEVEL_4, "level4_pending"),
    (ROUTE_LEVEL_5, "level5_pending"),
])
def test_each_level_has_an_independent_queue(make_state, route, queue):
    state = make_state(route)
    assert state["regions"][0]["status"] == STATUS_PENDING
    expected = {
        "level3_pending": False, "level4_pending": False,
        "level5_pending": False, "review_pending": False, "has_residual": True,
    }
    expected[queue] = True
    assert page_progress(state) == expected
    resolved = resolve_region(state, "region-0", resolved_by=route)
    assert resolved["regions"][0]["status"] == STATUS_RESOLVED
    assert not any(page_progress(resolved).values())


def test_resolving_iii_preserves_v_and_does_not_create_iv_queue(make_state):
    original = make_state(ROUTE_LEVEL_3, ROUTE_LEVEL_5, ROUTE_PROTECT)
    snapshot = deepcopy(original)
    resolved = resolve_region(original, "region-0", resolved_by=ROUTE_LEVEL_3)
    assert original == snapshot
    assert resolved["regions"][1:] == snapshot["regions"][1:]
    assert resolved["regions"][0]["status"] == STATUS_RESOLVED
    assert page_progress(resolved) == {
        "level3_pending": False, "level4_pending": False,
        "level5_pending": True, "review_pending": False, "has_residual": True,
    }


def test_resolving_one_region_keeps_same_level_sibling_pending(make_state):
    state = make_state(ROUTE_LEVEL_3, ROUTE_LEVEL_3)
    resolved = resolve_region(state, "region-0", resolved_by=ROUTE_LEVEL_3)
    assert resolved["regions"][1] == state["regions"][1]
    assert page_progress(resolved)["level3_pending"] is True


def test_review_survives_completion_of_automatic_work(make_state):
    state = make_state(ROUTE_LEVEL_3, ROUTE_PROTECT, ROUTE_REVIEW)
    resolved = resolve_region(state, "region-0", resolved_by=ROUTE_LEVEL_3)
    assert resolved["regions"][1:] == state["regions"][1:]
    assert page_progress(resolved) == {
        "level3_pending": False, "level4_pending": False,
        "level5_pending": False, "review_pending": True, "has_residual": True,
    }


@pytest.mark.parametrize("route", [ROUTE_PROTECT, ROUTE_REVIEW])
def test_automatic_resolution_rejects_protected_and_review_regions(make_state, route):
    state = make_state(route)
    snapshot = deepcopy(state)
    with pytest.raises(ValueError, match="Only LEVEL_3/4/5 regions can be resolved"):
        resolve_region(state, "region-0", resolved_by=ROUTE_LEVEL_3)
    assert state == snapshot
