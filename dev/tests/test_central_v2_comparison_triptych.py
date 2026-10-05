import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import comparison
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2


class ComparisonTriptychTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "manga"
        self.originals = []
        for name in ("changed.png", "unchanged.png", "not-candidate.png"):
            source = self.manga / "IMG/1" / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(name.encode())
            self.originals.append(source)
        self.level1 = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / LEVEL1 / "1"
        self.level2 = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / LEVEL2 / "1"
        for source in self.originals:
            self._clean(self.level1, source.name, f"level1:{source.name}".encode())
        self._clean(self.level2, "changed.png", b"level2:changed")

    def _clean(self, folder, source, data):
        path = folder / "clean" / (Path(source).stem + "_clean" + Path(source).suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _patches(self, manifest):
        level1_manifest = {
            "integrity_ok": True,
            "source_artifacts": [path.name for path in self.originals],
            "clean_artifacts": [f"clean/{path.stem}_clean{path.suffix}" for path in self.originals],
        }
        return [
            patch.object(comparison, "_manifest_matches_merge", return_value=True),
            patch.object(comparison, "_listing_merge_artifacts", return_value=self.originals),
            patch.object(comparison, "_stage_manifest",
                         side_effect=lambda _manga, stage, _chapter: level1_manifest if stage == LEVEL1 else {}),
            patch.object(comparison, "_stage_manifest_sha256", return_value="level1-hash"),
            patch.object(comparison, "_valid_level2", return_value=(manifest, self.level2, "l2-hash")),
            patch.object(comparison, "_level2_chapter_status", return_value={
                "transparent_pages": ["changed.png", "unchanged.png"],
                "level2_status": "processed",
            }),
        ]

    def test_changed_unchanged_and_non_candidate_resolve_official_effective_images(self):
        manifest = {"candidate_source_artifacts": ["changed.png", "unchanged.png"],
                    "changed_source_artifacts": ["changed.png"],
                    "unchanged_source_artifacts": ["unchanged.png"]}
        patches = self._patches(manifest)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            pages = comparison.comparison_triplets(self.manga, "1")
        self.assertEqual([page["level2_status"] for page in pages], [
            "changed", "no_change", "not_candidate",
        ])
        self.assertEqual(pages[0]["level2"].read_bytes(), b"level2:changed")
        self.assertEqual(pages[1]["level2"], pages[1]["level1"])
        self.assertEqual(pages[2]["level2"], pages[2]["level1"])

    def test_missing_image_claimed_as_changed_is_not_hidden_by_fallback(self):
        (self.level2 / "clean/changed_clean.png").unlink()
        manifest = {"candidate_source_artifacts": ["changed.png"],
                    "changed_source_artifacts": ["changed.png"],
                    "unchanged_source_artifacts": []}
        patches = self._patches(manifest)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            with self.assertRaisesRegex(OSError, "obrigatória do Nível II"):
                comparison.comparison_triplets(self.manga, "1")

    def test_missing_original_and_level1_images_are_visible_failures(self):
        level1_manifest = {"integrity_ok": True, "source_artifacts": ["changed.png"],
                           "clean_artifacts": ["clean/changed_clean.png"]}
        with patch.object(comparison, "_stage_manifest", return_value=level1_manifest), \
             patch.object(comparison, "_listing_merge_artifacts", return_value=[]):
            with self.assertRaisesRegex(OSError, "original obrigatória"):
                comparison.comparison_triplets(self.manga, "1")
        with patch.object(comparison, "_stage_manifest", return_value=level1_manifest), \
             patch.object(comparison, "_listing_merge_artifacts", return_value=self.originals[:1]), \
             patch.object(comparison, "artifact_file", return_value=None):
            with self.assertRaisesRegex(OSError, "Nível I ausente"):
                comparison.comparison_triplets(self.manga, "1")


if __name__ == "__main__":
    unittest.main()
