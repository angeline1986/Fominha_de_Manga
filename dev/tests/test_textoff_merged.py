import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orquestracao.textoff.merged import execute_merged, query_merged, validate_selection


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
            with patch("orquestracao.textoff.merged.v3.is_chapter_merged") as strict_validation:
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
            with patch("orquestracao.textoff.merged.v3.is_chapter_merged", return_value=False):
                with self.assertRaisesRegex(ValueError, "MERGE oficial válido"):
                    validate_selection(manga, ["1"])
            with self.assertRaisesRegex(ValueError, "repetidos"):
                validate_selection(manga, ["1", "1"])

    def test_execution_delegates_to_existing_cleaner_with_merge_authority(self):
        with tempfile.TemporaryDirectory() as root:
            manga = self.make_manga(root)
            events = []
            images = [Path("official-merge.png")]
            with patch("orquestracao.textoff.merged.v3.is_chapter_merged", return_value=True), \
                 patch("orquestracao.textoff.merged.v3.merge_artifact_files", return_value=images), \
                 patch("processamento.limpeza_baloes.cleaner_v2.integration.clean_chapter", return_value={
                     "status": "ok", "pages": 1, "outputs": 1, "masks": 1,
                 }) as clean:
                result = execute_merged(manga, ["1"], lambda name, event: events.append(event))
            self.assertEqual(result[0]["status"], "ok")
            self.assertEqual(clean.call_args.args[0], images)
            self.assertEqual(clean.call_args.kwargs["source_stage"], "MERGE")
            self.assertEqual(clean.call_args.args[1], manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED" / "1")
            self.assertTrue(any(event["stage"] == "done" for event in events))


if __name__ == "__main__":
    unittest.main()
