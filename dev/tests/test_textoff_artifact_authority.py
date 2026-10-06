"""M7 proves that operational readers consume the registry-selected target."""
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.consolidated_artifacts import consolidated_image
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2
from central_v2.backend.orchestration.textoff_merged.level2_vision import ALGORITHM
from central_v2.backend.orchestration.bubble_sommelier import artifacts as sommelier_artifacts
from central_v2.backend.orchestration.bubble_sommelier.mapear_results import load_mapear_results
from central_v2.backend.routes import bubble_sommelier as sommelier_routes

merged_query = importlib.import_module("central_v2.backend.orchestration.textoff_merged.query")
sommelier_query = importlib.import_module("central_v2.backend.orchestration.bubble_sommelier.query")
from central_v2.backend.routes import textoff_merged as merged_routes


class ArtifactAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "manga"
        self.manga.mkdir()
        self.registry_path = self.root / "registry.json"
        registry = json.loads(artifact_migration.REGISTRY_PATH.read_text())
        for stage in registry["stages"]:
            if stage.get("dual_write"):
                stage["read_authority"] = "target"
        registry["read_authority"] = "target"
        self.registry_path.write_text(json.dumps(registry))
        self.registry_patch = patch.object(artifact_migration, "REGISTRY_PATH", self.registry_path)
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)
        self.stages = {stage["stage_id"]: stage for stage in registry["stages"]}

    def chapter_dir(self, stage_id, side, chapter="1"):
        entry = self.stages[stage_id]
        return self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / entry[f"{side}_path"] / chapter

    def write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))

    def mapear_report(self, reason):
        return {"pages": [{"source": "page.png", "styled_balloon_candidates": [{
            "candidate_type": "soft_gradient", "features": {"candidate": True, "reason": reason},
        }]}]}

    def test_auto_cleaner_returns_target_manifest_value(self):
        for side, count in (("legacy", 1), ("target", 7)):
            self.write_json(self.chapter_dir("auto_cleaner", side) / "json/clean-manifest.json", {
                "level1": {"transparent_balloons_total": count},
            })
        row = {"chapter": "1", "merge_valid": True}
        with patch.object(merged_query, "query_merged", return_value={"chapters": [row]}), \
             patch.object(merged_query, "_manifest_matches_merge", return_value=True), \
             patch.object(merged_query, "_transparent_masks_ready", return_value=False), \
             patch.object(merged_query, "_deferred_text_masks_ready", return_value=False), \
             patch.object(merged_query, "observe_shadow_read"):
            result = merged_query.query_merged_level1(self.manga)
        self.assertEqual(result["chapters"][0]["transparent_balloons"], 7)

    def test_mapear_returns_target_occurrence_and_works_without_legacy(self):
        legacy = self.chapter_dir("mapear", "legacy") / "styled-balloon-report.json"
        target = self.chapter_dir("mapear", "target") / "styled-balloon-report.json"
        self.write_json(legacy, self.mapear_report("legacy-value"))
        self.write_json(target, self.mapear_report("target-value"))
        result = load_mapear_results(self.manga, "1")
        self.assertEqual(result["soft_gradient"]["occurrences"][0]["reason"], "target-value")
        legacy.unlink()
        before_missing_legacy = {path.relative_to(self.manga): path.read_bytes()
                                 for path in self.manga.rglob("*") if path.is_file()}
        result = load_mapear_results(self.manga, "1")
        self.assertEqual(result["soft_gradient"]["occurrences"][0]["reason"], "target-value")
        after = {path.relative_to(self.manga): path.read_bytes()
                 for path in self.manga.rglob("*") if path.is_file()}
        self.assertEqual(before_missing_legacy, after)

    def test_consolidated_route_returns_target_manifest_and_source_bytes(self):
        filename = "page_clean.png"
        selection = {"artifact": artifact_ref("clean", filename), "selected_from": LEVEL1}
        for side, content in (("legacy", b"legacy-image"), ("target", b"target-image")):
            source = self.chapter_dir("auto_cleaner", side) / "clean" / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(content)
            manifest = {**selection, "sha256": hashlib.sha256(content).hexdigest()}
            folder = self.chapter_dir("mapear_input_consolidado", side) / "json/clean-manifest.json"
            self.write_json(folder, {"selections": [manifest]})
        with patch.object(merged_routes, "_context", return_value=("p", "title")), \
             patch.object(merged_routes, "resolve_manga", return_value=self.manga), \
             patch.object(merged_routes, "query_level3", return_value={"chapters": [{
                 "chapter": "1", "cleaned": True, "candidate_pages": [{"source": filename}],
             }]}), patch.object(merged_routes, "observe_shadow_read"):
            response = merged_routes.textoff_merged_level3_image_response(
                {"provider": "p", "manga": "title", "chapter": "1", "file": filename}, self.root
            )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"target-image")
        self.assertEqual(consolidated_image(self.manga, "1", filename).read_bytes(), b"target-image")

    def test_bubble_sommelier_query_returns_target_report_value(self):
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1/page.png"
        merge.parent.mkdir(parents=True)
        merge.write_bytes(b"merge")
        for side, count in (("legacy", 2), ("target", 9)):
            self.write_json(self.chapter_dir("bubble_sommelier", side) / "report.json", {
                "profile_id": "p", "checkpoints": {"result": {
                    "pages": 1, "crops": 1, "coverageGe075": 1, "candidates": count,
                }},
            })
        with patch.object(sommelier_query, "validate_report", side_effect=lambda report, _profile: report):
            result = sommelier_query.query(self.manga)
        self.assertEqual(result["chapters"][0]["sommelier"]["candidates"], 9)

    def test_bubble_review_and_crop_routes_use_target_report_and_crop(self):
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1/page.png"
        merge.parent.mkdir(parents=True)
        merge.write_bytes(b"merge")
        for side, content, count in (("legacy", b"legacy-crop", 2), ("target", b"target-crop", 8)):
            digest = hashlib.sha256(content).hexdigest()
            folder = self.chapter_dir("bubble_sommelier", side)
            crop = folder / "crops/id1.png"
            crop.parent.mkdir(parents=True, exist_ok=True)
            crop.write_bytes(content)
            self.write_json(folder / "report.json", {
                "profile_id": "p", "checkpoints": {"result": {
                    "pages": 1, "crops": 1, "coverageGe075": 1, "candidates": count,
                }}, "pages": [{"page_id": "page.png", "bubbles": [{
                    "identity": "id1", "crop": {"sha256": digest}, "candidate": True,
                }]}],
            })
        context = patch.object(sommelier_routes, "_context", return_value=("p", "title"))
        manga = patch.object(sommelier_routes, "resolve_manga", return_value=self.manga)
        with context, manga, patch.object(sommelier_routes, "observe_shadow_read"), \
             patch.object(sommelier_artifacts, "validate_report", side_effect=lambda report, _profile: report):
            query = {"provider": "p", "manga": "title", "chapter": "1"}
            review = sommelier_routes.review_response(query, self.root)
            crop = sommelier_routes.crop_response({**query, "identity": "id1"}, self.root)
        self.assertEqual(review.status, 200)
        self.assertEqual(json.loads(review.body)["summary"]["candidates"], 8)
        self.assertEqual(crop.status, 200)
        self.assertEqual(crop.body, b"target-crop")

    def test_transparency_basic_returns_target_manifest_value(self):
        row = {"chapter": "1", "merge_valid": True, "cleaned": True,
               "transparent_masks_ready": True, "deferred_text_masks_ready": True,
               "transparent_balloons": 1, "deferred_components": 0,
               "transparent_pages": ["page.png"]}
        for side, changed in (("legacy", 3), ("target", 11)):
            self.write_json(self.chapter_dir("auto_cleaner_transparencia_basica", side)
                            / "json/clean-manifest.json", {
                "algorithm": ALGORITHM, "candidate_source_artifacts": ["page.png"],
                "clean_artifacts": ["clean/page_clean.png"], "outputs_total": 1,
                "pages_total": 1, "changed_pixels": changed, "outcome": "visual_changes",
            })
        self.write_json(self.chapter_dir("auto_cleaner", "target") / "json/clean-manifest.json", {})
        with patch.object(merged_query, "query_merged_level1", return_value={"chapters": [row]}), \
             patch.object(merged_query, "_valid_level2", return_value=(object(), None, None)), \
             patch.object(merged_query, "observe_shadow_read"):
            result = merged_query.query_merged_level2(self.manga)
        self.assertEqual(result["chapters"][0]["level2_changed_pixels"], 11)


if __name__ == "__main__":
    unittest.main()
