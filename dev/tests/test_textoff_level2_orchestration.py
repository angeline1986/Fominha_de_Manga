import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import level2
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.level2_vision import ALGORITHM
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2


class TextoffLevel2OrchestrationTests(unittest.TestCase):
    def test_mixed_report_is_validated_and_promoted_without_duplicate_unchanged_pngs(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            manga = base / "manga"
            source_dir = base / "merge"
            level1_dir = base / "level1"
            target = base / "TO_MERGED_NIVEL_II/1"
            source_dir.mkdir()
            candidates = [f"page-{index + 1:03d}-{index + 2:03d}.png" for index in range(10)]
            images = []
            for index in range(18):
                path = source_dir / f"page-{index + 1:03d}-{index + 2:03d}.png"
                path.write_bytes(b"merge")
                images.append(path)
            level1_dir.mkdir()
            clean_artifacts = []
            for image in images:
                ref = artifact_ref("clean", Path(image.name).stem + "_clean.png")
                (level1_dir / ref).parent.mkdir(parents=True, exist_ok=True)
                (level1_dir / ref).write_bytes(b"level1")
                clean_artifacts.append(ref)
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
                        pages.append({"source": source, "clean": clean, "level1_clean": level1_clean,
                                      "mask": mask, "mask_pixels": 2,
                                      "changed_pixels": 1 if clean else 0, "changed_outside_mask": 0})
                    report = {"algorithm": ALGORITHM, "integrity_ok": True,
                              "pages_analyzed": 10, "merge_pages_total": 18,
                              "pages_with_text": 8, "mask_pixels": 20, "changed_pixels": 8,
                              "outcome": "visual_changes", "duration_seconds": 1,
                              "pages": pages}
                    report_path = Path(job["report"])
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.write_text(json.dumps(report), encoding="utf-8")

                def poll(self):
                    return 0

            with patch.object(level2, "validate_level2_selection"), \
                 patch.object(level2, "python_for", return_value="/fake/python"), \
                 patch.object(level2, "query_merged_level2", return_value={"chapters": [{
                     "chapter": "1", "level2_candidate_pages": candidates}]}), \
                 patch.object(level2, "stage_chapter", side_effect=lambda _manga, stage, _chapter,
                              read_legacy=True: level1_dir if stage == LEVEL1 else target), \
                 patch.object(level2, "_stage_manifest", return_value=level1_manifest), \
                 patch.object(level2, "_stage_manifest_sha256", return_value="level1-hash"), \
                 patch.object(level2.v3, "is_chapter_merged", return_value=True), \
                 patch.object(level2.v3, "merge_output_dir", return_value=source_dir), \
                 patch.object(level2.v3, "merge_artifact_files", return_value=images), \
                 patch.object(level2.subprocess, "Popen", side_effect=SuccessfulWorker), \
                 patch("central_v2.backend.orchestration.textoff_merged.consolidated.rebuild_consolidated",
                       return_value={"outputs": 18, "level2_outputs_used": 8}):
                result = level2.execute_merged_level2(
                    manga, ["1"], lambda *_args: None, provider="comix", manga_name="title")

            self.assertEqual(result[0]["status"], "ok", result)
            self.assertEqual(worker_jobs[0]["protected_occurrences"], {})
            manifest = json.loads((target / "json/clean-manifest.json").read_text())
            self.assertEqual(manifest["pages_total"], 10)
            self.assertEqual(manifest["analyzed_pages_total"], 10)
            self.assertEqual(manifest["outputs_total"], 8)
            self.assertEqual(len(manifest["unchanged_source_artifacts"]), 2)
            self.assertEqual(manifest["protected_occurrences"], 0)
            self.assertEqual(manifest["mask_pixels_before_protection"], 0)
            self.assertEqual(manifest["mask_pixels_after_protection"], 0)
            self.assertEqual(len(list((target / "clean").glob("*.png"))), 8)
            self.assertEqual(len(list((target / "mask").glob("*.png"))), 10)


if __name__ == "__main__":
    unittest.main()
