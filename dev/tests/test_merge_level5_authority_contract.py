import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from interface_web import processing_web as pw


class MergeLevel5AuthorityContractTest(unittest.TestCase):
    """Caracteriza autoridade/integração IV → V → MERGE/Review.

    Estes testes protegem contratos existentes. Não definem algoritmo de corte
    do Level V; essa responsabilidade pertence a test_merge_level5_contract.py.
    """

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _image(self, path, height):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, height), "white").save(path, "PNG")

    def _artifact(self, directory, name, start, end, stage):
        self._image(directory / name, end - start)
        return {
            "file": name,
            "global_start": start,
            "global_end": end,
            "height": end - start,
            "source_stage": stage,
        }

    def _make_case(self, root, *, level5_residual=True):
        root = Path(root)

        manga = root / "manga"
        ch = manga / "IMG" / "6"
        ch.mkdir(parents=True)

        # Fonte atual: 220 px de altura total.
        self._image(ch / "page-001.png", 220)

        auto_dir = pw.amdir(manga, ch.name)
        l2_dir = pw.l2dir(manga, ch.name)
        l3_dir = pw.l3dir(manga, ch.name)
        l4_dir = pw.l4dir(manga, ch.name)
        l5_dir = pw.l5dir(manga, ch.name)

        auto = {
            "schema_version": 1,
            "algorithm": "auto_merge_level1_resolved_segments",
            "chapter": ch.name,
            "total_height": 220,
            "artifacts": [
                self._artifact(
                    auto_dir, "page-001-auto.png", 0, 80, "auto_merge"
                )
            ],
            "pending_segments": [
                {
                    "global_start": 80,
                    "global_end": 220,
                    "height": 140,
                }
            ],
        }
        self._write_json(auto_dir / "auto-merge-manifest.json", auto)

        l2 = {
            "schema_version": 1,
            "algorithm": "merge_level2_bounded_safe_path_v1",
            "chapter": ch.name,
            "total_height": 220,
            "artifacts": [
                self._artifact(
                    l2_dir, "page-001-level2.png", 80, 100, "level2"
                )
            ],
            "pending_segments": [
                {
                    "global_start": 100,
                    "global_end": 220,
                    "height": 120,
                }
            ],
        }
        l2_path = l2_dir / "merge-level2-manifest.json"
        self._write_json(l2_path, l2)

        l3 = {
            "schema_version": 1,
            "algorithm": "merge_level3_structural_safe_v1",
            "chapter": ch.name,
            "total_height": 220,
            "source_level2_manifest": "merge-level2-manifest.json",
            "source_level2_sha256": hashlib.sha256(
                l2_path.read_bytes()
            ).hexdigest(),
            "safe_artifacts": [
                self._artifact(
                    l3_dir, "page-001-level3.png", 100, 130, "level3"
                )
            ],
            "residual_pending_segments": [
                {
                    "global_start": 130,
                    "global_end": 220,
                    "height": 90,
                }
            ],
        }
        l3_path = l3_dir / "merge-level3-manifest.json"
        self._write_json(l3_path, l3)

        l4 = {
            "schema_version": 1,
            "algorithm": "merge_level4_directed_structural_safe_v1",
            "chapter": ch.name,
            "total_height": 220,
            "source_level3_manifest": "merge-level3-manifest.json",
            "source_level3_sha256": hashlib.sha256(
                l3_path.read_bytes()
            ).hexdigest(),
            "safe_artifacts": [
                self._artifact(
                    l4_dir, "page-001-level4.png", 130, 160, "level4"
                )
            ],
            "residual_pending_segments": [
                {
                    "global_start": 160,
                    "global_end": 220,
                    "height": 60,
                }
            ],
            "diagnostics": [],
            "safety": {
                "level3_safe_artifacts_modified": False,
                "forced_cut": False,
                "unsafe_candidate_accepted": False,
                "inconclusive_candidate_accepted": False,
                "global_safe_composition_only": True,
            },
        }
        l4_path = l4_dir / "merge-level4-manifest.json"
        self._write_json(l4_path, l4)

        l5_safe_end = 190 if level5_residual else 220
        l5 = {
            "schema_version": 1,
            "algorithm": "merge_level5_global_structural_safe_v1",
            "chapter": ch.name,
            "total_height": 220,
            "source_level4_manifest": "merge-level4-manifest.json",
            "source_level4_sha256": hashlib.sha256(
                l4_path.read_bytes()
            ).hexdigest(),
            "safe_artifacts": [
                self._artifact(
                    l5_dir,
                    "page-001-level5.png",
                    160,
                    l5_safe_end,
                    "level5",
                )
            ],
            "residual_pending_segments": (
                [
                    {
                        "global_start": 190,
                        "global_end": 220,
                        "height": 30,
                        "status": "failed",
                        "validation": "review_required",
                        "reason": "partial_safe_prefix_remaining",
                        "level5_decision": "PARTIAL_SAFE",
                    }
                ]
                if level5_residual
                else []
            ),
            "diagnostics": [],
            "safety": {
                "level4_safe_artifacts_modified": False,
                "forced_cut": False,
                "unsafe_candidate_accepted": False,
                "inconclusive_candidate_accepted": False,
                "global_safe_composition_only": True,
                "exhaustive_fallback": True,
            },
        }
        l5_path = l5_dir / "merge-level5-manifest.json"
        self._write_json(l5_path, l5)

        failure = {
            "level2_status": "validated",
            "partition": {
                "level2_validated": True,
                "total_height": 220,
                "pending_segments": [
                    {
                        "global_start": 100,
                        "global_end": 220,
                        "height": 120,
                    }
                ],
            },
        }

        return {
            "manga": manga,
            "ch": ch,
            "failure": failure,
            "l3_path": l3_path,
            "l4_path": l4_path,
            "l5_path": l5_path,
        }

    def test_level5_residual_is_authoritative_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self._make_case(tmp, level5_residual=True)

            pending, error, source = pw._level5_review_pending(
                case["ch"], case["failure"]
            )

            self.assertIsNone(error)
            self.assertEqual(source, "level5")
            self.assertEqual(
                [(x["global_start"], x["global_end"]) for x in pending],
                [(190, 220)],
            )

    def test_level5_stale_source_level4_sha_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self._make_case(tmp, level5_residual=True)

            l4 = json.loads(case["l4_path"].read_text(encoding="utf-8"))
            l4["diagnostics"] = [{"changed": True}]
            self._write_json(case["l4_path"], l4)

            pending, error, source = pw._level5_review_pending(
                case["ch"], case["failure"]
            )

            self.assertIsNone(pending)
            self.assertEqual(source, "level5")
            self.assertIn("desatualizado", error)
            self.assertIn("Level IV", error)

    def test_level5_gap_in_level4_residual_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self._make_case(tmp, level5_residual=True)

            l5 = json.loads(case["l5_path"].read_text(encoding="utf-8"))
            l5["safe_artifacts"][0]["global_end"] = 180
            l5["safe_artifacts"][0]["height"] = 20
            self._write_json(case["l5_path"], l5)

            pending, error, source = pw._level5_review_pending(
                case["ch"], case["failure"]
            )

            self.assertIsNone(pending)
            self.assertEqual(source, "level5")
            self.assertIn("recompõe exatamente", error)

    def test_level5_complete_promotes_to_official_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self._make_case(tmp, level5_residual=False)

            ok, message = pw._promote_level5_complete(case["ch"])

            self.assertTrue(ok, message)

            final_dir = pw.v3.merge_output_dir(case["ch"])
            manifest_path = final_dir / "merge-manifest.json"
            self.assertTrue(manifest_path.is_file())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["algorithm"],
                "merge_auto_level2_level3_level4_level5_composition_v1",
            )
            self.assertEqual(manifest["status"], "approved")
            self.assertTrue(manifest["validation"]["ok"])
            self.assertEqual(
                manifest["composition"]["level5_manifest"],
                "merge-level5-manifest.json",
            )
            self.assertEqual(
                manifest["composition"]["scope"],
                "level5_all_safe",
            )

    def test_level5_with_residual_cannot_promote_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self._make_case(tmp, level5_residual=True)

            ok, message = pw._promote_level5_complete(case["ch"])

            self.assertFalse(ok)
            self.assertIn("residual pendente", message)
            self.assertFalse(
                (pw.v3.merge_output_dir(case["ch"]) / "merge-manifest.json").exists()
            )

    def test_review_receives_only_authoritative_level5_residual(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self._make_case(tmp, level5_residual=True)
            captured = {}

            class FakeReview:
                class ReviewSourceLimitError(Exception):
                    pass

                @staticmethod
                def generate_candidate(
                    manga,
                    ch,
                    max_source_images=8,
                    pending_segments=None,
                    **kwargs,
                ):
                    captured["pending_segments"] = pending_segments
                    return True, "generated", ch

            job = SimpleNamespace(
                message="",
                progress=0,
                progress_value=0.0,
                progress_detail="",
            )

            with patch.object(pw, "reviewmod", return_value=FakeReview), patch.object(
                pw, "read_merge_failure", return_value=case["failure"]
            ):
                pw.do_review_generate(
                    job,
                    case["manga"],
                    [case["ch"]],
                    max_source_images=8,
                )

            self.assertEqual(
                [
                    (x["global_start"], x["global_end"])
                    for x in captured["pending_segments"]
                ],
                [(190, 220)],
            )


if __name__ == "__main__":
    unittest.main()
