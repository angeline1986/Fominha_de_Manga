import json
from pathlib import Path

import pytest

from central_v2.backend.orchestration.textoff_merged import final_consolidated as final
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


def _baseline(tmp_path, monkeypatch):
    manga = tmp_path / "provider" / "manga"
    manga.mkdir(parents=True)
    intermediate = stage_chapter(manga, "TO_MERGED_CONSOLIDADO", "1", read_legacy=False)
    (intermediate / "json").mkdir(parents=True)
    sources = {}
    selections = []
    for page in ("page-001.png", "page-002.png"):
        source = tmp_path / page
        source.write_bytes(f"baseline:{page}".encode())
        sources[page] = source
        selections.append({"source": page, "selected_from": LEVEL1,
                           "artifact": f"clean/{page}", "sha256": sha256(source)})
    manifest = intermediate / "json" / "clean-manifest.json"
    manifest.write_text(json.dumps({"selections": selections}), encoding="utf-8")
    monkeypatch.setattr(final, "consolidated_is_current", lambda *_: True)
    monkeypatch.setattr(final, "consolidated_image", lambda _m, _c, name: sources[name])
    final.rebuild_final_baseline(manga, "1")
    return manga


def _promote(manga, treatment, page, content, *, status="processed"):
    stage_name = "PINCEL_SUAVE" if treatment == "gradiente_suave" else "PINCEL_DEGRADE"
    operational = stage_chapter(manga, stage_name, "1", read_legacy=False)
    output = operational / "clean" / f"{page}.{treatment}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    record = {"status": status, "run_id": f"run{len(content)}",
              "output": {"artifact": f"clean/{output.name}", "sha256": sha256(output)}}
    row, image, manifest_hash = final.read_final_page(manga, "1", page)
    manifest = final.final_manifest_path(manga, "1")
    source = {"page": page, "path": str(image), "sha256": sha256(image),
              "selected_from": row["origin"], "consolidated_manifest": str(manifest),
              "consolidated_manifest_sha256": manifest_hash}
    final.promote_treatment_pages(manga, "1", treatment, {page: record},
                                  [{"source": source}])


def test_final_tracks_actual_treatment_order_and_keeps_page_set(tmp_path, monkeypatch):
    manga = _baseline(tmp_path, monkeypatch)
    _promote(manga, "gradiente_suave", "page-001.png", b"suave")
    suave_row, suave_image, _ = final.read_final_page(manga, "1", "page-001.png")
    suave_hash = sha256(suave_image)
    _promote(manga, "degrade", "page-001.png", b"degrade")
    degrade_row, _, _ = final.read_final_page(manga, "1", "page-001.png")
    assert degrade_row["treatment"] == "degrade"
    assert degrade_row["input_sha256"] == suave_hash
    assert suave_row["treatment"] == "gradiente_suave"
    payload = json.loads(final.final_manifest_path(manga, "1").read_text())
    assert set(payload["pages"]) == {"page-001.png", "page-002.png"}
    assert len(payload["history"]) == 2


def test_final_failure_preserves_previous_page_and_manifest(tmp_path, monkeypatch):
    manga = _baseline(tmp_path, monkeypatch)
    page = "page-001.png"
    before = final.final_manifest_path(manga, "1").read_bytes()
    row, image, manifest_hash = final.read_final_page(manga, "1", page)
    image_before = image.read_bytes()
    source = {"page": page, "path": str(image), "sha256": sha256(image),
              "selected_from": row["origin"],
              "consolidated_manifest": str(final.final_manifest_path(manga, "1")),
              "consolidated_manifest_sha256": manifest_hash}
    with pytest.raises(ValueError, match="Output persistido inválido"):
        final.promote_treatment_pages(manga, "1", "degrade", {page: {"status": "processed",
            "output": {"artifact": "clean/missing.png", "sha256": "bad"}}},
            [{"source": source}])
    assert final.final_manifest_path(manga, "1").read_bytes() == before
    assert (stage_chapter(manga, final.STAGE, "1", read_legacy=False) / page).read_bytes() == image_before


def test_no_change_is_promoted_as_a_valid_current_version(tmp_path, monkeypatch):
    manga = _baseline(tmp_path, monkeypatch)
    _promote(manga, "gradiente_suave", "page-002.png", b"same", status="no_change")
    row, image, _ = final.read_final_page(manga, "1", "page-002.png")
    assert row["status"] == "no_change"
    assert image.read_bytes() == b"same"


def test_degrade_then_suave_and_later_rebuild_keep_treatment_order(tmp_path, monkeypatch):
    manga = _baseline(tmp_path, monkeypatch)
    intermediate = stage_chapter(manga, "TO_MERGED_CONSOLIDADO", "1", read_legacy=False)
    intermediate_bytes = (intermediate / "json/clean-manifest.json").read_bytes()
    _promote(manga, "degrade", "page-001.png", b"degrade-first")
    degrade_row, degrade_image, _ = final.read_final_page(manga, "1", "page-001.png")
    degrade_hash = sha256(degrade_image)
    _promote(manga, "gradiente_suave", "page-001.png", b"smooth-second")
    smooth_row, smooth_image, _ = final.read_final_page(manga, "1", "page-001.png")
    assert smooth_row["treatment"] == "gradiente_suave"
    assert smooth_row["input_sha256"] == degrade_hash
    assert degrade_row["treatment"] == "degrade"
    final.rebuild_final_baseline(manga, "1")
    current, image, _ = final.read_final_page(manga, "1", "page-001.png")
    assert image.read_bytes() == b"smooth-second"
    assert current["treatment"] == "gradiente_suave"
    assert sha256(intermediate / "json/clean-manifest.json") == sha256_bytes(intermediate_bytes)


def sha256_bytes(content):
    import hashlib
    return hashlib.sha256(content).hexdigest()
