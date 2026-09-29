import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.textoff_merged import level2_process
from central_v2.backend.orchestration.textoff_merged.level2_process import process


class FakeLama:
    def __call__(self, source, mask):
        return Image.new("RGB", source.size, (245, 245, 245))


def _write_manifest(level1_dir: Path, pages: list[dict], names: list[str]) -> None:
    (level1_dir / "level1-balloon-report.json").write_text(
        json.dumps({"pages": pages}), encoding="utf-8")
    (level1_dir / "clean-manifest.json").write_text(json.dumps({
        "integrity_ok": True,
        "source_artifacts": names,
        "clean_artifacts": [Path(name).stem + "_clean.png" for name in names],
        "level1": {"algorithm": "textoff_level1_balloon_transparency_gate_v4"},
    }), encoding="utf-8")


class TextoffMergedLevel2MemoryTests(unittest.TestCase):
    def test_mps_model_is_reloaded_after_three_reconstructed_regions(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            source_dir, level1_dir, output_dir = base / "source", base / "level1", base / "level2"
            source_dir.mkdir()
            level1_dir.mkdir()
            pages, names = [], []
            for index in range(4):
                name = f"page-{index:03}-004.png"
                names.append(name)
                image = np.full((40, 40, 3), 230, dtype=np.uint8)
                Image.fromarray(image).save(source_dir / name)
                Image.fromarray(image).save(level1_dir / f"page-{index:03}-004_clean.png")
                Image.fromarray(np.ones((40, 40), dtype=np.uint16)).save(
                    level1_dir / f"page-{index:03}-004_transparent_balloons.png")
                deferred = np.zeros((40, 40), dtype=np.uint8)
                deferred[18:22, 18:22] = 255
                deferred_name = f"page-{index:03}-004_deferred.png"
                Image.fromarray(deferred).save(level1_dir / deferred_name)
                pages.append({
                    "source": name,
                    "transparent_mask_artifact": f"page-{index:03}-004_transparent_balloons.png",
                    "deferred_text_mask_artifact": deferred_name,
                    "transparent_components_deferred": 1,
                    "transparent_balloons": [{"balloon": 1, "mask_label": 1}],
                })
            _write_manifest(level1_dir, pages, names)

            with patch.object(level2_process, "_lama_model",
                              return_value=(FakeLama(), "test-model", "mps")) as model_factory, \
                 patch.object(level2_process, "_release_inference_cache"):
                report = process(source_dir, level1_dir, output_dir, output_dir / "report.json")

            self.assertEqual(model_factory.call_count, 2)
            self.assertEqual(report["pages_analyzed"], 4)
            self.assertEqual(report["pages_with_text"], 4)
            self.assertTrue(report["integrity_ok"])

    def test_distant_balloons_are_inpainted_as_separate_regions(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            source_dir, level1_dir, output_dir = base / "source", base / "level1", base / "level2"
            source_dir.mkdir()
            level1_dir.mkdir()
            name = "page-001-004.png"
            image = np.full((120, 120, 3), 230, dtype=np.uint8)
            Image.fromarray(image).save(source_dir / name)
            Image.fromarray(image).save(level1_dir / "page-001-004_clean.png")
            labels = np.zeros((120, 120), dtype=np.uint16)
            labels[5:45, 5:45] = 1
            labels[75:115, 75:115] = 2
            Image.fromarray(labels).save(level1_dir / "page-001-004_transparent_balloons.png")
            deferred = np.zeros((120, 120), dtype=np.uint8)
            deferred[20:23, 20:23] = 255
            deferred[90:93, 90:93] = 255
            Image.fromarray(deferred).save(level1_dir / "deferred.png")
            pages = [{
                "source": name,
                "transparent_mask_artifact": "page-001-004_transparent_balloons.png",
                "deferred_text_mask_artifact": "deferred.png",
                "transparent_components_deferred": 2,
                "transparent_balloons": [
                    {"balloon": 1, "mask_label": 1}, {"balloon": 2, "mask_label": 2},
                ],
            }]
            _write_manifest(level1_dir, pages, [name])

            with patch.object(level2_process, "_lama_model",
                              return_value=(FakeLama(), "test-model", "cpu")), \
                 patch.object(level2_process, "_inpaint",
                              wraps=level2_process._inpaint) as inpaint:
                report = process(source_dir, level1_dir, output_dir, output_dir / "report.json")

            self.assertTrue(report["integrity_ok"])
            self.assertEqual(inpaint.call_count, 2)
            for call in inpaint.call_args_list:
                mask = call.args[1]
                ys, xs = np.where(mask > 0)
                self.assertLess(int(ys.max() - ys.min()), 60)
                self.assertLess(int(xs.max() - xs.min()), 60)


if __name__ == "__main__":
    unittest.main()
