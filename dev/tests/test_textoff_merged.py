import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import (
    execute_merged, execute_merged_level1, query_merged, query_merged_level1, query_merged_level2,
    validate_selection,
)


class TextoffMergedUseCaseTests(unittest.TestCase):
    def make_manga(self, root):
        manga = Path(root) / "manga"
        for name in ("1", "2"):
            (manga / "IMG" / name).mkdir(parents=True)
            (manga / "FLUXO_SECUNDARIO" / "02_MERGE" / name).mkdir(parents=True)
        merge = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "1"
        (merge / "page-001-005.png").write_bytes(b"merge")
        (merge / "merge-manifest.json").write_text(json.dumps({
            "merged_images": 1, "source_total_height": 5,
            "outputs": [{"file": "page-001-005.png", "global_start": 0, "global_end": 5}],
        }), encoding="utf-8")
        clean = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED" / "1"
        clean.mkdir(parents=True)
        (clean / "clean-manifest.json").write_text(json.dumps({
            "source_stage": "MERGE", "integrity_ok": True,
            "source_artifacts": ["page-001-005.png"], "outputs_total": 1,
        }), encoding="utf-8")
        return manga

    def test_query_projects_merge_and_cleaner_manifest_status(self):
        with tempfile.TemporaryDirectory() as root:
            manga = self.make_manga(root)
            with patch("central_v2.backend.orchestration.textoff_merged.query.v3.is_chapter_merged") as strict_validation:
                result = query_merged(manga)
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["chapters"][0], {
                "chapter": "1", "merge_valid": True, "merge_count": 1,
                "cleaned": True, "clean_count": 1, "selectable": True,
            })
            self.assertFalse(result["chapters"][1]["selectable"])
            strict_validation.assert_not_called()

    def test_selection_rejects_invalid_merge_and_duplicate_chapter(self):
        with tempfile.TemporaryDirectory() as root:
            manga = self.make_manga(root)
            with patch("central_v2.backend.orchestration.textoff_merged.execution.v3.is_chapter_merged", return_value=False):
                with self.assertRaisesRegex(ValueError, "MERGE oficial válido"):
                    validate_selection(manga, ["1"])
            with self.assertRaisesRegex(ValueError, "repetidos"):
                    validate_selection(manga, ["1", "1"])

    def test_level_tables_separate_new_level1_and_deferred_transparency_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            manga = self.make_manga(root)
            output = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED_NIVEL_I" / "1"
            output.mkdir(parents=True)
            (output / "page-001-005_clean.png").write_bytes(b"clean")
            (output / "page-001-005_transparent_balloons.png").write_bytes(b"labels")
            (output / "page-001-005_deferred_text.png").write_bytes(b"deferred")
            (output / "clean-manifest.json").write_text(json.dumps({
                "source_stage": "MERGE", "integrity_ok": True,
                "source_artifacts": ["page-001-005.png"], "clean_artifacts": ["page-001-005_clean.png"],
                "outputs_total": 1,
                "pages_total": 1,
                "level1": {"transparent_balloons_total": 2, "transparent_components_deferred": 3,
                           "transparent_mask_artifacts": ["page-001-005_transparent_balloons.png"],
                           "deferred_text_mask_artifacts": ["page-001-005_deferred_text.png"],
                           "report": "level1-balloon-report.json"},
            }), encoding="utf-8")
            (output / "level1-balloon-report.json").write_text(json.dumps({
                "pages": [{"source": "page-001-005.png", "transparent_balloons": [{"balloon": 1}],
                           "deferred_text_mask_artifact": "page-001-005_deferred_text.png",
                           "transparent_components_deferred": 3}],
            }), encoding="utf-8")
            level1 = query_merged_level1(manga)["chapters"][0]
            level2 = query_merged_level2(manga)["chapters"][0]
            self.assertTrue(level1["cleaned"])
            self.assertEqual(level1["transparent_balloons"], 2)
            self.assertEqual(level1["transparent_page_count"], 1)
            self.assertEqual(level1["transparent_pages"], ["page-001-005.png"])
            self.assertEqual(level1["deferred_components"], 3)
            self.assertEqual(level2["level2_status"], "pending")
            self.assertTrue(level2["selectable"])

    def test_level2_table_marks_chapters_without_level1_output(self):
        with tempfile.TemporaryDirectory() as root:
            manga = self.make_manga(root)
            rows = query_merged_level2(manga)["chapters"]
            self.assertEqual(rows[0]["level2_status"], "missing_level1")
            self.assertFalse(rows[0]["selectable"])

    def test_execution_delegates_to_existing_cleaner_with_merge_authority(self):
        with tempfile.TemporaryDirectory() as root:
            manga = self.make_manga(root)
            events = []
            images = [Path("official-merge.png")]
            def fake_cleaner(_images, target, **_kwargs):
                target.mkdir(parents=True, exist_ok=True)
                (target / "clean-manifest.json").write_text("{}", encoding="utf-8")
                return {"status": "ok", "pages": 1, "outputs": 1, "masks": 1}
            with patch("central_v2.backend.orchestration.textoff_merged.execution.v3.is_chapter_merged", return_value=True), \
                 patch("central_v2.backend.orchestration.textoff_merged.execution.v3.merge_artifact_files", return_value=images), \
                 patch("processamento.limpeza_baloes.cleaner_v2.integration.clean_chapter", side_effect=fake_cleaner) as clean:
                result = execute_merged(manga, ["1"], lambda name, event: events.append(event))
            self.assertEqual(result[0]["status"], "ok")
            self.assertEqual(clean.call_args.args[0], images)
            self.assertEqual(clean.call_args.kwargs["source_stage"], "MERGE")
            self.assertEqual(clean.call_args.args[1], manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED" / "1")
            manifest = json.loads((clean.call_args.args[1] / "clean-manifest.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(manifest["execution"]["duration_seconds"], 0)
            self.assertTrue(any(event["stage"] == "done" for event in events))

    def test_new_level1_uses_isolated_target_and_skips_legacy_refinement(self):
        with tempfile.TemporaryDirectory() as root:
            manga = self.make_manga(root)
            images = [Path("official-merge.png")]
            with patch("central_v2.backend.orchestration.textoff_merged.execution.v3.is_chapter_merged", return_value=True), \
                 patch("central_v2.backend.orchestration.textoff_merged.execution.v3.merge_artifact_files", return_value=images), \
                 patch("central_v2.backend.orchestration.textoff_merged.cleaner.clean_level1_chapter", return_value={"status": "ok"}) as clean:
                execute_merged_level1(manga, ["1"], lambda *_: None)
            self.assertEqual(clean.call_args.args[1], manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED_NIVEL_I" / "1")
            self.assertEqual(clean.call_args.kwargs["source_stage"], "MERGE")


if __name__ == "__main__":
    unittest.main()
