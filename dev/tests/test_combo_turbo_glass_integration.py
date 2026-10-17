import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.combo_turbo.composition import compose_page
from central_v2.backend.orchestration.combo_turbo.glass_validator import validate_glass_page
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA, manifest_path,
)
from central_v2.backend.orchestration.textoff_merged.level2_process import process
from central_v2.backend.orchestration.textoff_merged.level2_validation import build_output_manifest
from central_v2.backend.orchestration.textoff_merged.consolidated import _valid_level2
from central_v2.backend.orchestration.textoff_merged.manifests import (
    _stage_manifest, _stage_manifest_sha256,
)
from central_v2.backend.orchestration.textoff_merged.level2_manual_protection import (
    load_level1_protection_context,
)
from central_v2.backend.orchestration.textoff_merged.residue_occurrences import (
    MANIFEST_NAME as RESIDUE_MANIFEST_NAME, update_page,
)
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2, stage_chapter
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class GlassProducerIntegrationTests(unittest.TestCase):
    page = "page-001.png"

    def test_real_producer_manifest_validates_and_composes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = (Path(temp) / "Gazing at you").resolve()
            merge = root / "IMG" / "12" / "MERGE"
            merge.mkdir(parents=True)
            source = merge / self.page
            Image.fromarray(np.zeros((9, 8, 3), dtype=np.uint8)).save(source)
            l1 = stage_chapter(root, LEVEL1, "12", read_legacy=False)
            clean_ref = artifact_ref("clean", "page-001_clean.png")
            label_ref = artifact_ref("mask", "page-001_balloon.png")
            deferred_ref = artifact_ref("mask", "page-001_deferred.png")
            for ref in (clean_ref, label_ref, deferred_ref):
                (l1 / ref).parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(np.full((9, 8, 3), 80, dtype=np.uint8)).save(l1 / clean_ref)
            Image.fromarray(np.ones((9, 8), dtype=np.uint8)).save(l1 / label_ref)
            Image.fromarray(np.ones((9, 8), dtype=np.uint8) * 255).save(l1 / deferred_ref)
            l1_report = {"pages": [{"source": self.page, "transparent_balloons": [
                {"balloon": 1, "mask_label": 1}], "transparent_components_deferred": 1,
                "transparent_mask_artifact": label_ref,
                "deferred_text_mask_artifact": deferred_ref}]}
            (l1 / "json").mkdir(parents=True)
            (l1 / "json/level1-balloon-report.json").write_text(json.dumps(l1_report))
            l1_manifest = {"integrity_ok": True, "source_stage": "MERGE",
                           "source_artifacts": [self.page], "outputs_total": 1,
                           "clean_artifacts": [clean_ref], "level1": {
                               "algorithm": "textoff_level1_balloon_transparency_gate_v4"}}
            (l1 / "json/clean-manifest.json").write_text(json.dumps(l1_manifest))
            check = manifest_path(root, "12")
            check.parent.mkdir(parents=True)
            check.write_text(json.dumps({"schema": SCHEMA, "version": 1,
                "provider": "comix", "manga": root.name, "chapter": "12",
                "source_snapshot": {}, "approved_occurrences": [{"id": "roi-1",
                "page": self.page, "tipo": "residuo_degrade", "box_normalized": {
                    "left": 0, "top": 0, "width": 0.2, "height": 1}}]}))
            output = stage_chapter(root, LEVEL2, "12", read_legacy=False)
            report_path = output / "json/level2-transparent-report.json"
            report_path.parent.mkdir(parents=True)
            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._inpaint",
                       side_effect=lambda image, _mask, _model: image):
                report = process(merge, l1, output, report_path, runtime={
                    "model": object(), "device": "cpu"}, candidate_pages={self.page},
                    protected_occurrences={"page-001.png": [{"id": "roi-1",
                        "tipo": "residuo_degrade", "box_normalized": {"left": 0,
                        "top": 0, "width": 0.2, "height": 1}}]},
                    protection_source={"kind": "CHECK",
                        "path": str(check.relative_to(root)), "sha256": sha256(check), "revision": 1})
            report["report_reference"] = artifact_ref("json", report_path.name)
            page = report["pages"][0]
            built, _ = build_output_manifest(report, [page], [source], {self.page},
                                              l1_manifest, sha256(l1 / "json/clean-manifest.json"))
            (output / "json/clean-manifest.json").write_text(json.dumps(built))
            with patch("central_v2.backend.orchestration.combo_turbo.glass_validator._manifest_matches_merge",
                       return_value=True), patch(
                    "central_v2.backend.orchestration.combo_turbo.glass_validator.v3.merge_output_dir",
                    return_value=merge):
                current_l1 = _stage_manifest(root, LEVEL1, "12")
                current_l1_hash = _stage_manifest_sha256(root, LEVEL1, "12")
                consolidated_reader, _, _ = _valid_level2(
                    root, "12", current_l1, current_l1_hash)
                self.assertIsNotNone(consolidated_reader)
                protected_files = [source, l1 / clean_ref, check, report_path,
                                   output / page["clean"], output / page["mask"],
                                   output / "json/clean-manifest.json"]
                before = {path: path.read_bytes() for path in protected_files}
                first = validate_glass_page(root, "comix", "12", self.page)
                second = validate_glass_page(root, "comix", "12", self.page)
                composed = compose_page(root, "comix", "12", self.page,
                    level1_path=l1 / clean_ref, output_dir=Path(temp) / "composed",
                    glass_path=output / page["clean"], mask_path=output / page["mask"])
                self.assertEqual(before, {path: path.read_bytes() for path in protected_files})
            self.assertEqual(first["status"], "REUSABLE", first)
            self.assertEqual(first, second)
            self.assertEqual(built["provenance_version"], 1)
            self.assertEqual(page["protected_occurrence_ids"], ["roi-1"])
            self.assertEqual(composed["status"], "COMPOSED", composed)
            self.assertEqual(sha256(check), built["page_results"][0]["protection_source"]["sha256"])
            glass_manifest_path = output / "json/clean-manifest.json"
            saved = glass_manifest_path.read_bytes()
            report_saved = report_path.read_bytes()
            broken = json.loads(saved)
            broken["page_results"][0]["protected_occurrence_ids"] = ["other-id"]
            glass_manifest_path.write_text(json.dumps(broken))
            broken_report = json.loads(report_saved)
            broken_report["pages"][0]["protected_occurrence_ids"] = ["other-id"]
            report_path.write_text(json.dumps(broken_report))
            with patch("central_v2.backend.orchestration.combo_turbo.glass_validator._manifest_matches_merge",
                       return_value=True), patch(
                    "central_v2.backend.orchestration.combo_turbo.glass_validator.v3.merge_output_dir",
                    return_value=merge):
                invalid = validate_glass_page(root, "comix", "12", self.page)
            self.assertEqual(invalid["status"], "INVALID")
            self.assertIn("PROTECTION_APPLICATION_MISMATCH", invalid["reasons"])
            glass_manifest_path.write_bytes(saved)
            report_path.write_bytes(report_saved)
            level1_report_path = l1 / "json/level1-balloon-report.json"
            level1_report_bytes = level1_report_path.read_bytes()
            label_ref = json.loads(level1_report_bytes)["pages"][0]["transparent_mask_artifact"]
            label_path = l1 / label_ref
            label_bytes = label_path.read_bytes()
            with patch("central_v2.backend.orchestration.combo_turbo.glass_validator._manifest_matches_merge",
                       return_value=True), patch(
                    "central_v2.backend.orchestration.combo_turbo.glass_validator.v3.merge_output_dir",
                    return_value=merge):
                label_path.write_bytes(label_bytes + b"changed")
                self.assertEqual(validate_glass_page(root, "comix", "12", self.page)["status"], "STALE")
                label_path.write_bytes(label_bytes)
                changed_report = json.loads(level1_report_bytes)
                changed_report["fixture_revision"] = 2
                level1_report_path.write_text(json.dumps(changed_report))
                self.assertEqual(validate_glass_page(root, "comix", "12", self.page)["status"], "STALE")
                level1_report_path.write_bytes(level1_report_bytes)
            check_payload = json.loads(check.read_text())
            check_payload["revision"] = 2
            check.write_text(json.dumps(check_payload))
            with patch("central_v2.backend.orchestration.combo_turbo.glass_validator._manifest_matches_merge",
                       return_value=True), patch(
                    "central_v2.backend.orchestration.combo_turbo.glass_validator.v3.merge_output_dir",
                    return_value=merge):
                stale = validate_glass_page(root, "comix", "12", self.page)
            self.assertEqual(stale["status"], "STALE")
            self.assertIn("PROTECTION_SOURCE_CHANGED", stale["reasons"])

    def test_legacy_protection_source_is_hashed_without_fabricating_check(self):
        with tempfile.TemporaryDirectory() as temp:
            root = (Path(temp) / "Gazing at you").resolve()
            document = {"provider": "comix", "obra": root.name, "capitulo": "12"}
            catalog = stage_chapter(root, "RESIDUE_OCCURRENCES", "12",
                                     read_legacy=False) / RESIDUE_MANIFEST_NAME
            occurrence = {"id": "legacy-1", "tipo": "residuo_degrade",
                          "box_normalized": {"left": 0, "top": 0,
                                             "width": 0.2, "height": 1}}
            update_page(catalog, document, self.page, "1", [occurrence])
            protections, source = load_level1_protection_context(root, "comix", root.name, "12")
            row = {"protection_source": source, "protected_occurrence_ids": ["legacy-1"],
                   "protected_types_applied": ["residuo_degrade"],
                   "protected_occurrences": 1, "protected_types": ["residuo_degrade"]}
            from central_v2.backend.orchestration.combo_turbo.glass_provenance import (
                validate_protection_source,
            )
            self.assertEqual(source["kind"], "RESIDUE_OCCURRENCES")
            self.assertEqual(source["sha256"], sha256(catalog))
            self.assertNotIn("check_sha256", source)
            self.assertIsNone(validate_protection_source(root, "comix", "12", self.page, row))
            self.assertEqual(protections[self.page], [occurrence])


if __name__ == "__main__":
    unittest.main()
