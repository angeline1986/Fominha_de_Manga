import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import level2
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.level2_vision import ALGORITHM
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class TextoffLevel2OrchestrationTests(unittest.TestCase):
    def test_mixed_report_is_validated_and_promoted_without_duplicate_unchanged_pngs(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            manga = base / "manga"
            source_dir = base / "merge"
            level1_dir = base / "level1"
            target = base / "TO_MERGED_NIVEL_II/1"
            target.mkdir(parents=True)
            (target / "previous-only.txt").write_text("old", encoding="utf-8")
            source_dir.mkdir()
            candidates = [f"page-{index + 1:03d}-{index + 2:03d}.png" for index in range(10)]
            images = []
            for index in range(18):
                path = source_dir / f"page-{index + 1:03d}-{index + 2:03d}.png"
                path.write_bytes(b"merge")
                images.append(path)
            level1_dir.mkdir()
            clean_artifacts = []
            level1_pages = []
            for image in images:
                ref = artifact_ref("clean", Path(image.name).stem + "_clean.png")
                (level1_dir / ref).parent.mkdir(parents=True, exist_ok=True)
                (level1_dir / ref).write_bytes(b"level1")
                clean_artifacts.append(ref)
                label = artifact_ref("mask", Path(image.name).stem + "_transparent.png")
                (level1_dir / label).parent.mkdir(parents=True, exist_ok=True)
                (level1_dir / label).write_bytes(b"labels")
                level1_pages.append({"source": image.name,
                                     "transparent_mask_artifact": label})
            (level1_dir / "json").mkdir()
            (level1_dir / "json/level1-balloon-report.json").write_text(
                json.dumps({"pages": level1_pages}), encoding="utf-8")
            level1_manifest = {"clean_artifacts": clean_artifacts, "source_artifacts": [p.name for p in images]}
            worker_jobs = []

            class SuccessfulWorker:
                returncode = 0

                def __init__(self, command, **_kwargs):
                    batch_manifest = Path(command[command.index("--batch-manifest") + 1])
                    job = json.loads(batch_manifest.read_text())[0]
                    worker_jobs.append(job)
                    staged = Path(job["output_dir"])
                    pages = []
                    for index, source in enumerate(candidates):
                        clean = artifact_ref("clean", Path(source).stem + "_clean.png") if index < 8 else None
                        level1_clean = artifact_ref("clean", Path(source).stem + "_clean.png")
                        mask = artifact_ref("mask", Path(source).stem + "_text_mask.png")
                        (staged / mask).parent.mkdir(parents=True, exist_ok=True)
                        (staged / mask).write_bytes(b"mask")
                        if clean:
                            (staged / clean).parent.mkdir(parents=True, exist_ok=True)
                            (staged / clean).write_bytes(b"level2")
                        source_path = Path(job["source_dir"]) / source
                        level1_path = Path(job["level1_dir"]) / level1_clean
                        level1_report = Path(job["level1_dir"]) / "json/level1-balloon-report.json"
                        level1_mask = Path(job["level1_dir"]) / artifact_ref(
                            "mask", Path(source).stem + "_transparent.png")
                        mask_path = staged / mask
                        pages.append({"source": source, "clean": clean, "level1_clean": level1_clean,
                                      "mask": mask, "mask_pixels": 2,
                                      "changed_pixels": 1 if clean else 0, "changed_outside_mask": 0,
                                      "source_sha256": sha256(source_path),
                                      "level1_sha256": sha256(level1_path),
                                      "result_sha256": sha256(staged / clean) if clean else sha256(level1_path),
                                      "mask_sha256": sha256(mask_path),
                                      "level1_report_sha256": sha256(level1_report),
                                      "level1_mask_sha256": sha256(level1_mask),
                                      "deferred_mask_sha256": None,
                                      "protection_source": job["protection_source"],
                                      "protected_occurrence_ids": [], "protected_types_applied": [],
                                      "protected_occurrences": 0, "protected_types": [],
                                      "protected_pixels": 0, "mask_pixels_before_protection": 2,
                                      "mask_pixels_after_protection": 2})
                    report = {"algorithm": ALGORITHM, "integrity_ok": True,
                              "source_level1_manifest_sha256": "a" * 64,
                              "pages_analyzed": 10, "merge_pages_total": 18,
                              "pages_with_text": 8, "mask_pixels": 20, "changed_pixels": 8,
                              "protected_occurrences": 0, "protected_pixels": 0,
                              "mask_pixels_before_protection": 20,
                              "mask_pixels_after_protection": 20, "protected_types": [],
                              "outcome": "visual_changes", "duration_seconds": 1,
                              "pages": pages}
                    report_path = Path(job["report"])
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.write_text(json.dumps(report), encoding="utf-8")

                def poll(self):
                    return 0

            with patch.object(level2, "validate_level2_selection") as validator, \
                 patch.object(level2, "python_for", return_value="/fake/python"), \
                 patch.object(level2, "query_merged_level2", return_value={"chapters": [{
                     "chapter": "1", "level2_candidate_pages": candidates}]}), \
                 patch.object(level2, "stage_chapter", side_effect=lambda _manga, stage, _chapter,
                              read_legacy=True: level1_dir if stage == LEVEL1 else target), \
                 patch.object(level2, "_stage_manifest", return_value=level1_manifest), \
                 patch.object(level2, "_stage_manifest_sha256", return_value="a" * 64), \
                 patch.object(level2.v3, "is_chapter_merged", return_value=True), \
                 patch.object(level2.v3, "merge_output_dir", return_value=source_dir), \
                 patch.object(level2.v3, "merge_artifact_files", return_value=images), \
                 patch.object(level2.subprocess, "Popen", side_effect=SuccessfulWorker), \
                 patch.object(level2, "mirror_stage_chapter", return_value=False) as mirror, \
                 patch("central_v2.backend.orchestration.textoff_merged.consolidated.rebuild_consolidated",
                       return_value={"outputs": 18, "level2_outputs_used": 8}) as rebuild, \
                 patch("central_v2.backend.orchestration.textoff_merged.final_consolidated.rebuild_final_baseline",
                       return_value={"pages": 18}):
                with patch.object(level2, "validate_protection_provenance",
                                  side_effect=ValueError("proveniência inválida")), \
                     patch.object(level2, "_promote_stage") as blocked_promotion:
                    rejected = level2.execute_merged_level2(
                        manga, ["1"], lambda *_args: None, provider="comix", manga_name="title",
                        reprocess=True)
                    self.assertEqual(rejected[0]["status"], "failed")
                    self.assertTrue((target / "previous-only.txt").exists())
                    blocked_promotion.assert_not_called()
                result = level2.execute_merged_level2(
                    manga, ["1"], lambda *_args: None, provider="comix", manga_name="title",
                    reprocess=True)

            self.assertEqual(result[0]["status"], "ok", result)
            self.assertEqual(validator.call_count, 2)
            validator.assert_called_with(manga, ["1"], reprocess=True)
            mirror.assert_called_once_with(manga, "auto_cleaner_transparencia_basica", "1")
            rebuild.assert_called_once_with(manga, "1")
            self.assertFalse((target / "previous-only.txt").exists())
            self.assertEqual(worker_jobs[0]["protected_occurrences"], {})
            manifest = json.loads((target / "json/clean-manifest.json").read_text())
            self.assertEqual(manifest["pages_total"], 10)
            self.assertEqual(manifest["analyzed_pages_total"], 10)
            self.assertEqual(manifest["outputs_total"], 8)
            self.assertEqual(len(manifest["unchanged_source_artifacts"]), 2)
            self.assertEqual(manifest["protected_occurrences"], 0)
            self.assertEqual(manifest["mask_pixels_before_protection"], 20)
            self.assertEqual(manifest["mask_pixels_after_protection"], 20)
            self.assertEqual(len(list((target / "clean").glob("*.png"))), 8)
            self.assertEqual(len(list((target / "mask").glob("*.png"))), 10)


if __name__ == "__main__":
    unittest.main()
