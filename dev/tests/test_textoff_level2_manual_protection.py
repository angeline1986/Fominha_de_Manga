"""Regional manual authority for TextOff Merged Level II masks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from central_v2.backend.orchestration.textoff_merged.level2_manual_protection import (
    LEVEL1_REVIEW_STEP, PROTECTED_FROM_LEVEL2, load_level1_protection,
    protect_level2_masks, protection_mask,
)
from central_v2.backend.orchestration.textoff_merged.level2_process import process
from central_v2.backend.orchestration.textoff_merged import level2_batch


def occurrence(kind, box=(.25, .25, .25, .25), key="occ"):
    left, top, width, height = box
    return {"id": key, "tipo": kind, "box_normalized": {
        "left": left, "top": top, "width": width, "height": height}}


class ManualProtectionTests(unittest.TestCase):
    def test_catalog_authority_filters_types_step_page_and_context(self):
        with tempfile.TemporaryDirectory() as temp:
            manga = Path(temp) / "ridi" / "work"
            manifest = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/RESIDUE_OCCURRENCES/1/residue-occurrences-manifest.json"
            manifest.parent.mkdir(parents=True)
            rows = [occurrence(kind, key=kind) for kind in (
                "residuo_degrade", "residuo_gradiente", "texto_residual",
                "residuo_transparencia", "fragmento_balao", "outro")]
            payload = {"schema": "textoff_residue_occurrence_manifest_v1",
                "documento": {"provider": "ridi", "obra": "work", "capitulo": "1", "step": "1"},
                "pages": {"page.png": {"steps": {"1": {"ocorrencias": rows},
                    "2": {"ocorrencias": [occurrence("residuo_degrade")]}}},
                    "other.png": {"steps": {"1": {"ocorrencias": [occurrence("residuo_gradiente")]}}}}}
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            selected = load_level1_protection(manga, "ridi", "work", "1")
            self.assertEqual(LEVEL1_REVIEW_STEP, "1")
            self.assertEqual(PROTECTED_FROM_LEVEL2, {"residuo_degrade", "residuo_gradiente"})
            self.assertEqual([item["tipo"] for item in selected["page.png"]],
                             ["residuo_degrade", "residuo_gradiente"])
            self.assertNotIn("other-page.png", selected)
            self.assertEqual(load_level1_protection(manga, "ridi", "work", "2"), {})
            with self.assertRaisesRegex(ValueError, "estrutura incompatível"):
                load_level1_protection(manga, "comix", "other", "1")

    def test_missing_catalog_and_non_protecting_types_leave_mask_unchanged(self):
        automatic = np.zeros((20, 20), dtype=np.uint8); automatic[8:12, 8:12] = 255
        unchanged, summary = protect_level2_masks([automatic], [], automatic.shape)
        np.testing.assert_array_equal(unchanged[0], automatic)
        self.assertEqual(summary["mask_pixels_before_protection"], 16)
        self.assertEqual(summary["mask_pixels_after_protection"], 16)
        for kind in ("texto_residual", "residuo_transparencia", "fragmento_balao", "outro"):
            unchanged, summary = protect_level2_masks([automatic], [occurrence(kind)], automatic.shape)
            np.testing.assert_array_equal(unchanged[0], automatic)
            self.assertEqual(summary["protected_occurrences"], 0)

    def test_degrade_and_gradient_remove_only_intersected_pixels(self):
        automatic = np.zeros((20, 20), dtype=np.uint8)
        automatic[2:6, 2:6] = 255; automatic[14:18, 14:18] = 255
        for kind in ("residuo_degrade", "residuo_gradiente"):
            protected, summary = protect_level2_masks(
                [automatic], [occurrence(kind, (.1, .1, .2, .2)),
                              occurrence("residuo_transparencia", (.7, .7, .1, .1))], automatic.shape)
            self.assertEqual(np.count_nonzero(protected[0][2:6, 2:6]), 0)
            self.assertGreater(np.count_nonzero(protected[0][14:18, 14:18]), 0)
            self.assertGreater(summary["protected_pixels"], 0)

    def test_batch_runner_forwards_only_preselected_protection_data_to_worker(self):
        job = {"chapter": "1", "source_dir": "/merge", "level1_dir": "/level1",
               "output_dir": "/stage", "report": "/report.json", "candidate_pages": ["page.png"],
               "protected_occurrences": {"page.png": [occurrence("residuo_degrade")]}}
        with patch.object(level2_batch, "process", return_value={"integrity_ok": True}) as worker:
            level2_batch.process_batch([job])
        self.assertEqual(worker.call_args.kwargs["protected_occurrences"], job["protected_occurrences"])

    def test_protection_is_applied_after_expansion_and_normalized_edges_clip(self):
        seed = np.zeros((24, 24), dtype=np.uint8); seed[12, 12] = 255
        expanded = cv2.dilate(seed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        protected = protection_mask(seed.shape, [occurrence("residuo_degrade", (0, 0, 1, 1))])
        result, summary = protect_level2_masks([expanded], [occurrence("residuo_degrade", (0, 0, 1, 1))], seed.shape)
        self.assertEqual(int(np.count_nonzero(result[0])), 0)
        self.assertEqual(summary["no_change_reason"], "manual_protection_removed_all_level2_mask")
        self.assertEqual(int(np.count_nonzero(protected)), seed.size)
        edge = protection_mask(seed.shape, [occurrence("residuo_gradiente", (0, 0, 1 / 24, 1 / 24))])
        self.assertEqual(np.argwhere(edge > 0).tolist(), [[0, 0]])

    def test_partial_protection_keeps_remaining_level2_work_and_full_protection_skips_inpaint(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._level1_fixture(Path(temp))
            partial = occurrence("residuo_degrade", (.25, .25, .1, .1))
            captured = []
            def fake_inpaint(rgb, mask, model):
                captured.append(mask.copy())
                output = rgb.copy(); output[mask > 0] = 0
                return output
            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._inpaint", side_effect=fake_inpaint):
                no_catalog = process(*paths, runtime={"model": object(), "device": "cpu"},
                                     candidate_pages={"page.png"})
            self.assertTrue(captured)
            self.assertEqual(no_catalog["mask_pixels_before_protection"],
                             no_catalog["mask_pixels_after_protection"])
            with Image.open(paths[2] / "mask/page_text_mask.png") as saved_mask:
                baseline_mask = np.asarray(saved_mask).copy()
            captured.clear()
            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._inpaint", side_effect=fake_inpaint):
                wrong_page = process(*paths, runtime={"model": object(), "device": "cpu"},
                                     candidate_pages={"page.png"},
                                     protected_occurrences={"different-page.png": [partial]})
            self.assertEqual(wrong_page["mask_pixels_before_protection"],
                             wrong_page["mask_pixels_after_protection"])
            with Image.open(paths[2] / "mask/page_text_mask.png") as saved_mask:
                np.testing.assert_array_equal(np.asarray(saved_mask), baseline_mask)
            self.assertTrue(captured)
            captured.clear()
            runtime = {"model": object(), "device": "cpu", "model_inferences": 0}
            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._inpaint", side_effect=fake_inpaint):
                report = process(*paths, runtime=runtime, candidate_pages={"page.png"},
                                 protected_occurrences={"page.png": [partial]})
            self.assertTrue(captured)
            self.assertEqual(np.count_nonzero(captured[0][6:9, 6:9]), 0)
            self.assertGreater(np.count_nonzero(captured[0]), 0)
            self.assertEqual(report["pages"][0]["mask_pixels_before_protection"],
                             report["pages"][0]["mask_pixels"] + report["pages"][0]["protected_pixels"])

            captured.clear()
            full = occurrence("residuo_gradiente", (0, 0, 1, 1))
            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._inpaint", side_effect=fake_inpaint):
                unchanged = process(*paths, runtime={"model": object(), "device": "cpu"},
                                    candidate_pages={"page.png"}, protected_occurrences={"page.png": [full]})
            self.assertEqual(captured, [])
            self.assertEqual(unchanged["outcome"], "no_visual_change")
            self.assertIsNone(unchanged["pages"][0]["clean"])
            self.assertEqual(unchanged["pages"][0]["no_change_reason"],
                             "manual_protection_removed_all_level2_mask")
            self.assertEqual(unchanged["mask_pixels_after_protection"], 0)

    @staticmethod
    def _level1_fixture(root):
        source_dir, level1 = root / "merge", root / "level1"
        (level1 / "clean").mkdir(parents=True); (level1 / "mask").mkdir()
        (level1 / "json").mkdir()
        source_dir.mkdir()
        image = np.full((24, 24, 3), 200, dtype=np.uint8)
        Image.fromarray(image).save(source_dir / "page.png")
        Image.fromarray(image).save(level1 / "clean/page_clean.png")
        labels = np.ones((24, 24), dtype=np.uint8)
        deferred = np.zeros((24, 24), dtype=np.uint8); deferred[12, 12] = 255
        Image.fromarray(labels).save(level1 / "mask/labels.png")
        Image.fromarray(deferred).save(level1 / "mask/deferred.png")
        (level1 / "json/level1-balloon-report.json").write_text(json.dumps({"pages": [{
            "source": "page.png", "transparent_balloons": [{"balloon": 1, "mask_label": 1}],
            "transparent_components_deferred": 1, "transparent_mask_artifact": "mask/labels.png",
            "deferred_text_mask_artifact": "mask/deferred.png"}]}), encoding="utf-8")
        (level1 / "json/clean-manifest.json").write_text(json.dumps({
            "integrity_ok": True, "level1": {"algorithm": "textoff_level1_balloon_transparency_gate_v4"},
            "clean_artifacts": ["clean/page_clean.png"]}), encoding="utf-8")
        return source_dir, level1, root / "output", root / "report.json"


if __name__ == "__main__":
    unittest.main()
