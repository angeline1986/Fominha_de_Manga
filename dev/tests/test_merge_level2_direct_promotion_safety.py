import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from interface_web import processing_web as web
from processamento.unificacao_imagens.image_stitcher import is_chapter_merged


class MergeLevel2DirectPromotionSafetyTests(unittest.TestCase):
    def _png(self, path, color, height):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (20, height), color).save(path, "PNG")

    def _sha256(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _chapter(self, root):
        manga = Path(root) / "Manga"
        chapter = manga / "IMG" / "6"
        chapter.mkdir(parents=True)
        self._png(chapter / "page-001.png", "red", 100)
        self._png(chapter / "page-002.png", "blue", 100)
        return manga, chapter

    def _write_stage_manifests(self, manga, chapter, l2_start=100, l2_end=200):
        auto_dir = web.amdir(manga, chapter.name)
        l2_dir = web.l2dir(manga, chapter.name)
        auto_dir.mkdir(parents=True)
        l2_dir.mkdir(parents=True)

        self._png(auto_dir / "auto-001.png", "red", 100)
        self._png(l2_dir / "level2-001.png", "blue", l2_end - l2_start)

        auto_manifest = {
            "schema_version": 1,
            "algorithm": "auto_merge_level1_resolved_segments",
            "chapter": chapter.name,
            "source_dir": str(chapter),
            "output_dir": str(auto_dir),
            "total_height": 200,
            "artifacts": [{
                "file": "auto-001.png",
                "global_start": 0,
                "global_end": 100,
                "height": 100,
                "source_stage": "auto_merge",
            }],
            "pending_segments": [{
                "id": 2,
                "global_start": 100,
                "global_end": 200,
                "height": 100,
            }],
            "coverage": {"auto_segments": [[0, 100]]},
        }
        (auto_dir / "auto-merge-manifest.json").write_text(
            json.dumps(auto_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        l2_manifest = {
            "schema_version": 2,
            "algorithm": "merge_level2_residual_v2",
            "chapter": chapter.name,
            "source_dir": str(chapter),
            "output_dir": str(l2_dir),
            "total_height": 200,
            "source_auto_merge_manifest": "auto-merge-manifest.json",
            "artifacts": [{
                "file": "level2-001.png",
                "global_start": l2_start,
                "global_end": l2_end,
                "height": l2_end - l2_start,
                "source_stage": "level2",
            }],
            "pending_segments": [],
            "coverage": {"level2_segments": [[l2_start, l2_end]]},
            "safety": {
                "level1_artifacts_duplicated": False,
                "level1_artifacts_modified": False,
            },
        }
        (l2_dir / "merge-level2-manifest.json").write_text(
            json.dumps(l2_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        part = {"level2_validated": True, "total_height": 200, "pending_segments": []}
        return auto_dir, l2_dir, part

    def test_direct_promotion_preserves_level2_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)
            auto_dir, l2_dir, part = self._write_stage_manifests(manga, chapter)
            auto_bytes = (auto_dir / "auto-001.png").read_bytes()
            l2_bytes = (l2_dir / "level2-001.png").read_bytes()

            ok, msg = web._promote_level2_complete(chapter, part)
            self.assertTrue(ok, msg)
            self.assertTrue(is_chapter_merged(chapter))

            merge_dir = manga / "FLUXO_SECUNDARIO" / "MERGE" / "6"
            manifest = json.loads((merge_dir / "merge-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["algorithm"], "merge_auto_level2_composition_v2")
            self.assertEqual(
                [(x["global_start"], x["global_end"], x["source_stage"]) for x in manifest["outputs"]],
                [(0, 100, "auto_merge"), (100, 200, "level2")],
            )
            outputs = manifest["outputs"]
            self.assertEqual((merge_dir / outputs[0]["file"]).read_bytes(), auto_bytes)
            self.assertEqual((merge_dir / outputs[1]["file"]).read_bytes(), l2_bytes)

    def test_direct_promotion_rejects_gap(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)
            _, _, part = self._write_stage_manifests(manga, chapter, l2_start=110, l2_end=200)
            ok, msg = web._promote_level2_complete(chapter, part)
            self.assertFalse(ok)
            self.assertIn("lacuna", msg.lower())
            self.assertFalse(is_chapter_merged(chapter))
            self.assertFalse((manga / "FLUXO_SECUNDARIO" / "MERGE" / "6").exists())

    def test_direct_promotion_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)
            _, _, part = self._write_stage_manifests(manga, chapter, l2_start=90, l2_end=200)
            ok, msg = web._promote_level2_complete(chapter, part)
            self.assertFalse(ok)
            self.assertIn("sobreposição", msg.lower())
            self.assertFalse(is_chapter_merged(chapter))
            self.assertFalse((manga / "FLUXO_SECUNDARIO" / "MERGE" / "6").exists())

    def test_direct_promotion_rejects_missing_level2_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)
            _, l2_dir, part = self._write_stage_manifests(manga, chapter)
            (l2_dir / "level2-001.png").unlink()
            ok, msg = web._promote_level2_complete(chapter, part)
            self.assertFalse(ok)
            self.assertIn("ausente", msg.lower())
            self.assertFalse(is_chapter_merged(chapter))
            self.assertFalse((manga / "FLUXO_SECUNDARIO" / "MERGE" / "6").exists())


if __name__ == "__main__":
    unittest.main()
