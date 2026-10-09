"""Fail-closed recovery of historical Artístico inputs and outputs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import write_manifest
from central_v2.backend.orchestration.textoff_merged.special_styled_recovery import recover_from_final_history
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL2, stage_chapter
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class StyledHistoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Example"
        self.chapter, self.page = "1", "page-001.png"
        self.source = self._image(stage_chapter(self.manga, LEVEL2, self.chapter, read_legacy=False) / "clean" /
                                  "page-001_clean.png", (20, 30, 40, 255))
        self.source_manifest = self.source.parents[1] / "json" / "clean-manifest.json"
        self.source_manifest.parent.mkdir(parents=True, exist_ok=True)
        self.source_manifest.write_text(json.dumps({"source_artifacts": [self.page],
            "clean_artifacts": ["clean/page-001_clean.png"]}))
        self.art_output = self._image(Path(self.temp.name) / "art.png", (30, 40, 50, 255))
        degrade = stage_chapter(self.manga, "PINCEL_DEGRADE", self.chapter, read_legacy=False)
        self.snapshot = self._image(degrade / "input/run1" / self.page, (30, 40, 50, 255))
        self.output = self._image(degrade / "clean/page-001_degrade.png", (50, 60, 70, 255))
        degrade_manifest = degrade / "json/degrade-manifest.json"
        degrade_manifest.parent.mkdir(parents=True, exist_ok=True)
        degrade_manifest.write_text(json.dumps({"pages": {self.page: {
            "run_id": "degrade1", "input_artifact": {
                "artifact": f"input/run1/{self.page}", "sha256": sha256(self.snapshot)},
            "output": {"artifact": "clean/page-001_degrade.png", "sha256": sha256(self.output)}}}}))
        art_record = {"page": self.page, "artifact": self.page, "origin": "PINCEL_ARTISTICO",
            "sha256": sha256(self.art_output), "input_sha256": sha256(self.source),
            "input_origin": "AUTO_CLEANER_TRANSPARENCIA",
            "input_manifest_sha256": sha256(self.source_manifest), "run_id": "art1"}
        current = {"page": self.page, "artifact": self.page, "origin": "PINCEL_DEGRADE",
            "sha256": sha256(self.output), "input_sha256": sha256(self.art_output),
            "input_origin": "PINCEL_ARTISTICO", "run_id": "degrade1"}
        final = stage_chapter(self.manga, "CONSOLIDADO_FINAL", self.chapter, read_legacy=False)
        final.mkdir(parents=True)
        self._image(final / self.page, (50, 60, 70, 255))
        write_manifest(final, {"schema": "textoff_consolidado_final_manifest_v1", "version": 1,
            "provider": "comix", "manga": "Example", "chapter": self.chapter,
            "source_intermediate_manifest_sha256": "base", "page_count": 1,
            "pages": {self.page: current}, "history": [{"page": self.page, "superseded": art_record}]})

    def _image(self, path, color):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(cv2.imwrite(str(path), np.full((4, 5, 4), color, dtype=np.uint8)))
        return path

    def test_recovers_only_exact_manifest_linked_artifacts(self):
        result = recover_from_final_history(self.manga, self.chapter, self.page)
        self.assertEqual(Path(result["path"]).resolve(), self.source.resolve())
        self.assertEqual(result["sha256"], sha256(self.source))
        self.assertEqual(Path(result["prior_output"]).resolve(), self.snapshot.resolve())
        self.assertEqual(result["prior_output_sha256"], sha256(self.snapshot))
        self.assertEqual(len(result["proofs"]), 3)

    def test_missing_previous_output_blocks_recovery(self):
        self.snapshot.unlink()
        with self.assertRaisesRegex(ValueError, "Saída Artística anterior ausente"):
            recover_from_final_history(self.manga, self.chapter, self.page)

    def test_source_hash_divergence_blocks_recovery(self):
        self._image(self.source, (99, 99, 99, 255))
        with self.assertRaisesRegex(ValueError, "Hash do artefato de entrada"):
            recover_from_final_history(self.manga, self.chapter, self.page)


if __name__ == "__main__":
    unittest.main()
