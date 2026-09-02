import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from interface_web import processing_web as pw
from processamento.unificacao_imagens import image_stitcher as v3


class Level3DirectPromotionTests(unittest.TestCase):
    def make_case(self, root, residual=None):
        manga = Path(root) / "manga"
        ch = manga / "IMG" / "6"
        ch.mkdir(parents=True)
        Image.new("RGB", (8, 220), (255, 255, 255)).save(ch / "page-001.png")

        auto = pw.amdir(manga, ch.name)
        l2 = pw.l2dir(manga, ch.name)
        l3 = pw.l3dir(manga, ch.name)
        auto.mkdir(parents=True)
        l2.mkdir(parents=True)
        l3.mkdir(parents=True)

        Image.new("RGB", (8, 80), (255, 0, 0)).save(auto / "auto-001.png")
        Image.new("RGB", (8, 20), (255, 255, 0)).save(l2 / "level2-001.png")
        Image.new("RGB", (8, 60), (0, 255, 0)).save(l3 / "safe-001.png")
        Image.new("RGB", (8, 60), (0, 0, 255)).save(l3 / "safe-002.png")

        auto_manifest = {
            "schema_version": 1,
            "algorithm": "auto_merge_level1_resolved_segments",
            "chapter": ch.name,
            "source_dir": str(ch),
            "output_dir": str(auto),
            "total_height": 220,
            "artifacts": [{"file": "auto-001.png", "global_start": 0, "global_end": 80, "height": 80}],
            "pending_segments": [{"id": 2, "global_start": 80, "global_end": 220, "height": 140}],
            "coverage": {"auto_segments": [[0, 80]]},
        }
        (auto / "auto-merge-manifest.json").write_text(
            json.dumps(auto_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        pending = [{"id": 3, "global_start": 100, "global_end": 220, "height": 120}]
        l2_manifest = {
            "schema_version": 2,
            "algorithm": "merge_level2_residual_v2",
            "chapter": ch.name,
            "source_dir": str(ch),
            "output_dir": str(l2),
            "total_height": 220,
            "source_auto_merge_manifest": "auto-merge-manifest.json",
            "artifacts": [{"file": "level2-001.png", "global_start": 80, "global_end": 100, "height": 20}],
            "pending_segments": pending,
            "coverage": {"level2_segments": [[80, 100]]},
            "safety": {"level1_artifacts_duplicated": False, "level1_artifacts_modified": False},
        }
        l2_path = l2 / "merge-level2-manifest.json"
        l2_path.write_text(json.dumps(l2_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        l2_hash = hashlib.sha256(l2_path.read_bytes()).hexdigest()

        l3_manifest = {
            "schema_version": 1,
            "algorithm": "merge_level3_structural_safe_v1",
            "chapter": ch.name,
            "source_dir": str(ch),
            "output_dir": str(l3),
            "total_height": 220,
            "source_level2_manifest": "merge-level2-manifest.json",
            "source_level2_sha256": l2_hash,
            "safe_artifacts": [
                {"file": "safe-001.png", "global_start": 100, "global_end": 160, "height": 60, "source_stage": "level3"},
                {"file": "safe-002.png", "global_start": 160, "global_end": 220, "height": 60, "source_stage": "level3"},
            ],
            "residual_pending_segments": residual or [],
            "diagnostics": [],
            "safety": {"level2_passed_artifacts_modified": False, "forced_cut": False, "inconclusive_local_search_allowed": False},
        }
        (l3 / "merge-level3-manifest.json").write_text(
            json.dumps(l3_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        part = {"level2_validated": True, "total_height": 220, "pending_segments": pending, "resolved_segments": []}
        return manga, ch, part, auto, l2, l3

    def test_promotes_level2_and_level3_without_review(self):
        with tempfile.TemporaryDirectory() as td:
            _, ch, part, auto, l2, l3 = self.make_case(td)
            expected_bytes = [
                (auto / "auto-001.png").read_bytes(),
                (l2 / "level2-001.png").read_bytes(),
                (l3 / "safe-001.png").read_bytes(),
                (l3 / "safe-002.png").read_bytes(),
            ]
            ok, msg = pw._promote_level3_complete(ch, part)
            self.assertTrue(ok, msg)
            official = v3.merge_output_dir(ch)
            manifest = json.loads((official / "merge-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["algorithm"], "merge_auto_level2_level3_composition_v2")
            self.assertEqual(
                [(x["global_start"], x["global_end"], x["source_stage"]) for x in manifest["outputs"]],
                [(0, 80, "auto_merge"), (80, 100, "level2"), (100, 160, "level3"), (160, 220, "level3")],
            )
            self.assertIsNone(manifest["composition"]["review_manifest"])
            self.assertEqual(manifest["composition"]["scope"], "level3_all_safe")
            for output, expected in zip(manifest["outputs"], expected_bytes):
                self.assertEqual((official / output["file"]).read_bytes(), expected)
            self.assertTrue(v3.is_chapter_merged(ch))

    def test_refuses_direct_promotion_when_residual_exists(self):
        with tempfile.TemporaryDirectory() as td:
            residual = [{"global_start": 160, "global_end": 220, "height": 60}]
            _, ch, part, _, _, _ = self.make_case(td, residual=residual)
            ok, msg = pw._promote_level3_complete(ch, part)
            self.assertFalse(ok)
            self.assertIn("residual", msg.lower())
            self.assertFalse(v3.merge_output_dir(ch).exists())

    def test_refuses_stale_level3_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            _, ch, part, _, l2, _ = self.make_case(td)
            p = l2 / "merge-level2-manifest.json"
            payload = json.loads(p.read_text(encoding="utf-8"))
            payload["test_mutation"] = True
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            ok, msg = pw._promote_level3_complete(ch, part)
            self.assertFalse(ok)
            self.assertIn("desatualizado", msg.lower())
            self.assertFalse(v3.merge_output_dir(ch).exists())


if __name__ == "__main__":
    unittest.main()
