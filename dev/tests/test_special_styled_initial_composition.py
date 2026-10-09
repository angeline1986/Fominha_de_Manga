"""Initial Artístico writes are limited to verified masks and proven ancestry."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.special_styled_initial_composition import compose_initial
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter


class InitialCompositionTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix/Example"
        self.page = "page-001.png"
        self.source = self.root / "detection.png"
        self.current = self.root / "current.png"
        self.folder = self.root / "run"
        (self.folder / "treatment").mkdir(parents=True)
        self.original = np.full((48, 48, 3), 20, np.uint8)
        self._save(self.source, self.original)
        after = self.original.copy(); after[25, 25] = (70, 80, 90)
        self.technical = self.folder / "treatment/01_local_heal.png"
        self._save(self.technical, after)
        mask = np.zeros((48, 48), np.uint8); mask[20:30, 20:30] = 255
        self.mask = self.folder / "treatment/roi_authorized_mask.png"
        self._save(self.mask, mask)
        self.detection = {"path": str(self.source), "sha256": sha256(self.source)}
        self.run = {"run_id": "run1", "run_dir": str(self.folder),
            "result_file": "treatment/01_local_heal.png",
            "validation": {"result_sha256": sha256(self.technical)},
            "artifacts": {"treatment/roi_authorized_mask.png": sha256(self.mask)}}
        self.final = stage_chapter(self.manga, "CONSOLIDADO_FINAL", "1")
        self.final.mkdir(parents=True)

    def _save(self, path, image):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(cv2.imwrite(str(path), image))

    def _final(self, rows):
        manifest = self.final / "json/final-manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"pages": {self.page: rows[-1]},
            "history": [{"page": self.page, "superseded": row} for row in rows[:-1]]}))

    def test_only_effective_authorized_pixel_is_composed(self):
        self._save(self.current, self.original)
        record = {"sha256": sha256(self.current), "origin": "AUTO_CLEANER"}
        self._final([record])
        destination = self.root / "composed.png"
        result = compose_initial(self.manga, "1", self.page, self.detection,
                                 self.current, record, self.run, destination)
        self.assertEqual(result["effective_write_pixels"], 1)
        self.assertEqual(result["conflict_pixels"], 0)
        self.assertEqual(tuple(cv2.imread(str(destination))[25, 25]), (70, 80, 90))
        self.assertEqual(int(np.count_nonzero(cv2.imread(str(
            self.folder / "initial_effective_write_mask.png"), 0))), 1)

    def test_verified_suave_overlap_blocks_publication(self):
        current = self.original.copy(); current[25, 25] = (35, 40, 45)
        self._save(self.current, current)
        smooth = stage_chapter(self.manga, "PINCEL_SUAVE", "1")
        output = smooth / "clean/page-001_suave.png"
        self._save(output, current)
        write_mask = smooth / "authorship/s1/page-001-write.png"
        mask = np.zeros((48, 48), np.uint8); mask[25, 25] = 255
        self._save(write_mask, mask)
        (smooth / "json").mkdir(parents=True)
        (smooth / "json/suave-manifest.json").write_text(json.dumps({"pages": {
            self.page: {"run_id": "s1", "output": {"artifact": "clean/page-001_suave.png",
                "sha256": sha256(output)}, "write_mask": {
                    "artifact": "authorship/s1/page-001-write.png",
                    "sha256": sha256(write_mask)}}}}))
        prior = {"sha256": sha256(self.source), "origin": "AUTO_CLEANER"}
        record = {"sha256": sha256(self.current), "origin": "PINCEL_SUAVE",
                  "input_sha256": prior["sha256"], "run_id": "s1"}
        self._final([prior, record])
        destination = self.root / "blocked.png"
        with self.assertRaisesRegex(ValueError, "1 pixels em conflito"):
            compose_initial(self.manga, "1", self.page, self.detection,
                            self.current, record, self.run, destination)
        self.assertFalse(destination.exists())
        report = json.loads((self.folder / "initial_composition.json").read_text())
        self.assertEqual(report["conflict_pixels"], 1)
