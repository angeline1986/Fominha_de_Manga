import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel1 import materialize_safe_intervals
from processamento.unificacao_imagens.auto_merge.planejamento_nivel1 import plan_level1
from processamento.unificacao_imagens.auto_merge.promocao_nivel1 import (
    promote_complete, write_stage_manifest,
)


class Level1PromotionTests(unittest.TestCase):
    def chapter(self, root, name, heights, bands=()):
        folder = root / "comix" / "Synthetic" / "IMG" / name
        folder.mkdir(parents=True)
        pages, source, offset = [], [], 0
        for index, height in enumerate(heights, 1):
            pixels = np.full((height, 32, 3), index * 25, dtype=np.uint8)
            for start, end in bands:
                low, high = max(start, offset), min(end, offset + height)
                if low < high:
                    pixels[low-offset:high-offset] = 255
            path = folder / f"page-{index:03d}.png"
            Image.fromarray(pixels).save(path)
            pages.append(path)
            source.append(pixels)
            offset += height
        infos, white_bands, total, _ = v3.analyze_chapter(pages)
        return folder, infos, white_bands, total, np.concatenate(source)

    def test_complete_stage_promotes_and_is_physically_recognized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chapter, infos, bands, total, source = self.chapter(root, "complete", [4000, 4000])
            plan = plan_level1(total, bands)
            stage = chapter.parent.parent / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter.name
            artifacts = materialize_safe_intervals(plan, infos, stage)
            manifest_path = write_stage_manifest(chapter, plan, artifacts)
            official = promote_complete(chapter, plan, artifacts)
            self.assertTrue(manifest_path.is_file())
            self.assertTrue(v3.is_chapter_merged(chapter))
            output = json_load(official / "merge-manifest.json")
            self.assertEqual(output["algorithm"], "merge_auto_level1_composition_v2")
            item = output["outputs"][0]
            with Image.open(official / item["file"]) as image:
                self.assertTrue(np.array_equal(np.asarray(image), source))

    def test_partial_plan_cannot_promote(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chapter, infos, bands, total, _ = self.chapter(
                root, "partial", [7000] * 4, [(6000, 6400), (20000, 20400)],
            )
            plan = plan_level1(total, bands)
            stage = chapter.parent.parent / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter.name
            artifacts = materialize_safe_intervals(plan, infos, stage)
            write_stage_manifest(chapter, plan, artifacts)
            with self.assertRaises(ValueError):
                promote_complete(chapter, plan, artifacts)
            self.assertFalse(v3.merge_output_dir(chapter).exists())

    def test_occupied_official_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chapter, infos, bands, total, _ = self.chapter(root, "occupied", [4000, 4000])
            plan = plan_level1(total, bands)
            stage = chapter.parent.parent / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter.name
            artifacts = materialize_safe_intervals(plan, infos, stage)
            write_stage_manifest(chapter, plan, artifacts)
            official = v3.merge_output_dir(chapter)
            official.mkdir(parents=True)
            sentinel = official / "keep.txt"
            sentinel.write_text("untouched")
            with self.assertRaises(FileExistsError):
                promote_complete(chapter, plan, artifacts)
            self.assertEqual(sentinel.read_text(), "untouched")


def json_load(path):
    import json
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
