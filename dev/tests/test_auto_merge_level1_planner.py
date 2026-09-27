import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel1 import materialize_safe_intervals
from processamento.unificacao_imagens.auto_merge.planejamento_nivel1 import plan_level1


class Level1PlannerTests(unittest.TestCase):
    def chapter(self, root, name, heights, bands=()):
        folder = root / name
        folder.mkdir()
        pages = []
        full = []
        offset = 0
        for index, height in enumerate(heights, 1):
            pixels = np.full((height, 32, 3), index * 30, dtype=np.uint8)
            for start, end in bands:
                low, high = max(start, offset), min(end, offset + height)
                if low < high:
                    pixels[low-offset:high-offset] = 255
            path = folder / f"page-{index:03d}.png"
            Image.fromarray(pixels).save(path)
            pages.append(path)
            full.append(pixels)
            offset += height
        infos, white_bands, total, _ = v3.analyze_chapter(pages)
        return folder, infos, white_bands, total, np.concatenate(full)

    def test_safe_short_chapter_is_a_complete_single_interval(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, bands, total, _ = self.chapter(Path(temporary), "complete", [4000, 4000])
            plan = plan_level1(total, bands)
        self.assertEqual(plan.status, "complete")
        self.assertEqual([(x.start, x.end, x.status) for x in plan.intervals], [(0, 8000, "safe")])

    def test_oversized_region_is_pending_and_planner_resumes_after_safe_band(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, bands, total, _ = self.chapter(
                Path(temporary), "partial", [7000] * 4, [(6000, 6400), (20000, 20400)],
            )
            plan = plan_level1(total, bands)
        self.assertEqual(plan.status, "partial")
        self.assertEqual(
            [(x.start, x.end, x.status) for x in plan.intervals],
            [(0, 6200, "safe"), (6200, 20200, "pending"), (20200, 28000, "safe")],
        )

    def test_no_safe_boundary_leaves_whole_oversized_source_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, bands, total, _ = self.chapter(Path(temporary), "blocked", [7000, 7000])
            plan = plan_level1(total, bands)
        self.assertEqual(plan.status, "unresolved")
        self.assertEqual([(x.start, x.end, x.status) for x in plan.intervals], [(0, 14000, "pending")])

    def test_materializer_writes_only_safe_intervals_with_exact_source_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, infos, bands, total, source = self.chapter(
                root, "partial", [7000] * 4, [(6000, 6400), (20000, 20400)],
            )
            plan = plan_level1(total, bands)
            output = root / "stage"
            artifacts = materialize_safe_intervals(plan, infos, output)
            self.assertEqual([(x["global_start"], x["global_end"]) for x in artifacts], [(0, 6200), (20200, 28000)])
            for item in artifacts:
                with Image.open(output / item["file"]) as image:
                    self.assertTrue(np.array_equal(np.asarray(image), source[item["global_start"]:item["global_end"]]))

    def test_materializer_refuses_existing_stage_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, infos, bands, total, _ = self.chapter(root, "complete", [4000, 4000])
            plan = plan_level1(total, bands)
            output = root / "stage"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("untouched")
            with self.assertRaises(FileExistsError):
                materialize_safe_intervals(plan, infos, output)
            self.assertEqual(sentinel.read_text(), "untouched")

    def test_materializer_claims_stage_directory_exclusively(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, infos, bands, total, _ = self.chapter(root, "complete", [4000, 4000])
            plan = plan_level1(total, bands)
            output = root / "stage"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                materialize_safe_intervals(plan, infos, output)
            self.assertEqual(list(output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
