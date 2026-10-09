"""Downstream writes retain their verified authorization mask."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged.special_write_proof import persist_write_mask
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class WriteProofTests(unittest.TestCase):
    def test_retains_exact_mask_and_rejects_tampered_preview(self):
        with TemporaryDirectory() as work:
            root = Path(work)
            mask = root / "previews" / "run1" / "treatment" / "authorized.png"
            mask.parent.mkdir(parents=True)
            self.assertTrue(cv2.imwrite(str(mask), np.array([[0, 255], [255, 0]], dtype=np.uint8)))
            run = {"run_id": "run1", "treatment": {"artifacts": {
                "authorized_mask": "authorized.png"}},
                "artifacts": {"treatment/authorized.png": sha256(mask)}}
            with patch("central_v2.backend.orchestration.textoff_merged.special_write_proof.STAGING_ROOT",
                       root / "previews"):
                proof = persist_write_mask(root / "stage", run, "page.png")
                self.assertEqual(sha256(root / "stage" / proof["artifact"]), proof["sha256"])
                run["artifacts"]["treatment/authorized.png"] = "f" * 64
                with self.assertRaisesRegex(ValueError, "divergente"):
                    persist_write_mask(root / "stage", run, "page.png")


if __name__ == "__main__":
    unittest.main()
