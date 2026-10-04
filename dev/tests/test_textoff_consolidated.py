import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged.consolidated import (
    consolidated_is_current, rebuild_consolidated,
)
from central_v2.backend.orchestration.textoff_merged.consolidated_artifacts import consolidated_image
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2
from central_v2.backend.orchestration.textoff_merged.level2_vision import ALGORITHM
from central_v2.backend.orchestration.textoff_merged.comparison import comparison_pairs
from central_v2.backend.orchestration.textoff_merged import query as query_module


class TextoffConsolidatedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "manga"
        self.chapter = "1"
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1"
        merge.mkdir(parents=True)
        names = ["page-001-005.png", "page-005-010.png"]
        for name in names:
            (merge / name).write_bytes(b"merge:" + name.encode())
        (merge / "merge-manifest.json").write_text(json.dumps({
            "merged_images": 2, "source_total_height": 10,
            "outputs": [
                {"file": names[0], "global_start": 0, "global_end": 5},
                {"file": names[1], "global_start": 5, "global_end": 10},
            ],
        }), encoding="utf-8")
        self.sources = names
        self._write_stage(LEVEL1, [b"level1-a", b"level1-b"], None)

    def _write_stage(self, stage, contents, source_hash, candidates=None):
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / stage / self.chapter
        (folder / "clean").mkdir(parents=True, exist_ok=True)
        (folder / "json").mkdir(parents=True, exist_ok=True)
        clean_names = [Path(name).stem + "_clean.png" for name in self.sources]
        for name, content in zip(clean_names, contents):
            (folder / "clean" / name).write_bytes(content)
        manifest = {
            "source_stage": "MERGE" if stage == LEVEL1 else LEVEL1,
            "integrity_ok": True, "source_artifacts": self.sources,
            "clean_artifacts": [f"clean/{name}" for name in clean_names],
            "outputs_total": len(clean_names),
        }
        if stage == LEVEL2:
            candidates = candidates or self.sources
            changed = candidates[:len(contents)]
            unchanged = candidates[len(contents):]
            page_results = []
            mask_refs = []
            report_pages = []
            for source in candidates:
                clean = f"clean/{Path(source).stem}_clean.png" if source in changed else None
                level1_clean = f"clean/{Path(source).stem}_clean.png"
                mask = f"mask/{Path(source).stem}_text_mask.png"
                (folder / mask).parent.mkdir(parents=True, exist_ok=True)
                (folder / mask).write_bytes(b"mask:" + source.encode())
                row = {"source": source, "clean": clean, "level1_clean": level1_clean,
                       "mask": mask, "changed_pixels": 1 if clean else 0,
                       "changed_outside_mask": 0, "mask_pixels": 1}
                page_results.append({key: value for key, value in row.items() if key != "changed_outside_mask"})
                report_pages.append(row)
                mask_refs.append(mask)
            report = {"integrity_ok": True, "pages_analyzed": len(candidates), "pages": report_pages}
            (folder / "json/level2-report.json").write_text(json.dumps(report), encoding="utf-8")
            level1_manifest_path = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
            level1_manifest = json.loads(level1_manifest_path.read_text())
            manifest.update({
                "algorithm": ALGORITHM,
                "source_level1_manifest_sha256": source_hash,
                "source_level1_artifacts": [item for item in level1_manifest["clean_artifacts"]
                                            if any(Path(source).stem in item for source in candidates)],
                "candidate_source_artifacts": candidates,
                "analyzed_source_artifacts": candidates,
                "changed_source_artifacts": changed,
                "unchanged_source_artifacts": unchanged,
                "page_results": page_results,
                "pages_total": len(candidates), "analyzed_pages_total": len(candidates),
                "changed_pages_total": len(changed),
                "clean_artifacts": [f"clean/{Path(source).stem}_clean.png" for source in changed],
                "outputs_total": len(changed),
                "changed_artifacts": [f"clean/{Path(source).stem}_clean.png" for source in changed],
                "mask_artifacts": mask_refs,
                "report": "json/level2-report.json",
                "outcome": "visual_changes" if changed else "no_visual_change",
            })
        (folder / "json/clean-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")

    def test_falls_back_to_level1_until_valid_level2_exists(self):
        result = rebuild_consolidated(self.manga, self.chapter)
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/1"
        manifest = json.loads((folder / "json/clean-manifest.json").read_text())
        self.assertEqual(result["level2_outputs_used"], 0)
        self.assertEqual([item["selected_from"] for item in manifest["selections"]], [LEVEL1, LEVEL1])
        self.assertFalse((folder / "clean/page-001-005_clean.png").exists())
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))
        self.assertEqual(consolidated_image(self.manga, self.chapter, "page-001-005_clean.png").read_bytes(),
                         b"level1-a")

    def test_prefers_valid_level2_and_invalidates_when_its_manifest_changes(self):
        level1_manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest.read_bytes()).hexdigest()
        self._write_stage(LEVEL2, [b"level2-a", b"level2-b"], source_hash)
        level2_manifest_path = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_II/1/json/clean-manifest.json"
        level2_manifest = json.loads(level2_manifest_path.read_text())
        level2_manifest["candidate_source_artifacts"] = self.sources
        level2_manifest["pages_total"] = 2
        level2_manifest["changed_artifacts"] = level2_manifest["clean_artifacts"]
        level2_manifest_path.write_text(json.dumps(level2_manifest), encoding="utf-8")
        result = rebuild_consolidated(self.manga, self.chapter)
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/1"
        manifest_path = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_II/1/json/clean-manifest.json"
        manifest = json.loads((folder / "json/clean-manifest.json").read_text())
        self.assertEqual(result["level2_outputs_used"], 2)
        self.assertEqual([item["selected_from"] for item in manifest["selections"]], [LEVEL2, LEVEL2])
        self.assertEqual((folder / "clean/page-005-010_clean.png").read_bytes(), b"level2-b")
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))
        manifest_path.write_text(manifest_path.read_text() + " ", encoding="utf-8")
        self.assertFalse(consolidated_is_current(self.manga, self.chapter))

    def test_keeps_only_changed_pages_in_level2_and_references_level1_for_rest(self):
        level1_manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest.read_bytes()).hexdigest()
        self._write_stage(LEVEL2, [b"level2-changed"], source_hash, candidates=[self.sources[0]])

        result = rebuild_consolidated(self.manga, self.chapter)
        consolidated = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/1"
        self.assertEqual(result["level2_outputs_used"], 1)
        self.assertTrue((consolidated / "clean/page-001-005_clean.png").is_file())
        self.assertFalse((consolidated / "clean/page-005-010_clean.png").exists())
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))

    def test_mixed_changed_and_unchanged_pages_promote_with_level1_fallback(self):
        level1_manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest.read_bytes()).hexdigest()
        self._write_stage(LEVEL2, [b"level2-changed"], source_hash)

        result = rebuild_consolidated(self.manga, self.chapter)
        target = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/1"
        manifest = json.loads((target / "json/clean-manifest.json").read_text())
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))
        self.assertEqual(result["level2_outputs_used"], 1)
        self.assertEqual([item["selected_from"] for item in manifest["selections"]], [LEVEL2, LEVEL1])
        pairs = comparison_pairs(self.manga, self.chapter, "2")
        self.assertEqual([item["name"] for item in pairs], self.sources)
        self.assertEqual(pairs[0]["after"].read_bytes(), b"level2-changed")
        self.assertEqual(pairs[1]["before"], pairs[1]["after"])

    def test_all_unchanged_candidate_pages_are_valid_no_change(self):
        level1_manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest.read_bytes()).hexdigest()
        self._write_stage(LEVEL2, [], source_hash)
        result = rebuild_consolidated(self.manga, self.chapter)
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))
        self.assertEqual(result["level2_outputs_used"], 0)
        pairs = comparison_pairs(self.manga, self.chapter, "2")
        self.assertEqual(len(pairs), 2)
        self.assertTrue(all(pair["before"] == pair["after"] for pair in pairs))

    def test_query_reports_mixed_and_no_change_levels_as_complete(self):
        level1_manifest_path = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest_path.read_bytes()).hexdigest()
        self._write_stage(LEVEL2, [b"level2-changed"], source_hash)
        row = {"chapter": self.chapter, "merge_valid": True, "cleaned": True,
               "transparent_masks_ready": True, "deferred_text_masks_ready": True,
               "transparent_balloons": 2, "deferred_components": 1,
               "transparent_pages": self.sources}
        with patch.object(query_module, "query_merged_level1", return_value={"chapters": [dict(row)]}):
            result = query_module.query_merged_level2(self.manga)
        self.assertEqual(result["chapters"][0]["level2_status"], "processed")

        self._write_stage(LEVEL2, [], source_hash)
        with patch.object(query_module, "query_merged_level1", return_value={"chapters": [dict(row)]}):
            result = query_module.query_merged_level2(self.manga)
        self.assertEqual(result["chapters"][0]["level2_status"], "no_change")

    def test_query_keeps_incomplete_or_missing_clean_output_pending(self):
        level1_manifest_path = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest_path.read_bytes()).hexdigest()
        self._write_stage(LEVEL2, [b"level2-changed"], source_hash)
        row = {"chapter": self.chapter, "merge_valid": True, "cleaned": True,
               "transparent_masks_ready": True, "deferred_text_masks_ready": True,
               "transparent_balloons": 2, "deferred_components": 1,
               "transparent_pages": self.sources}
        level2_dir = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_II/1"
        report_path = level2_dir / "json/level2-report.json"
        report = json.loads(report_path.read_text())
        report["pages"].pop()
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with patch.object(query_module, "query_merged_level1", return_value={"chapters": [dict(row)]}):
            result = query_module.query_merged_level2(self.manga)
        self.assertEqual(result["chapters"][0]["level2_status"], "pending")

        self._write_stage(LEVEL2, [b"level2-changed"], source_hash)
        (level2_dir / "clean/page-001-005_clean.png").unlink()
        with patch.object(query_module, "query_merged_level1", return_value={"chapters": [dict(row)]}):
            result = query_module.query_merged_level2(self.manga)
        self.assertEqual(result["chapters"][0]["level2_status"], "pending")


if __name__ == "__main__":
    unittest.main()
