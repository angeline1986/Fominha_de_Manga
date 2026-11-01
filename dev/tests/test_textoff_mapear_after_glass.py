"""Mapear keeps its pre-Glass input when Glass updates the consolidated output."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged.level3_source import (
    mapear_input_image, pre_glass_mapear_current,
)
from central_v2.backend.orchestration.textoff_merged.stages import (
    CONSOLIDATED, LEVEL1, LEVEL2, LEVEL3, stage_chapter,
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class MapearAfterGlassTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "obra"
        self.chapter = "2"
        self.filename = "page-001-002_clean.png"
        self.level1 = stage_chapter(self.manga, LEVEL1, self.chapter, read_legacy=False)
        self.level3 = stage_chapter(self.manga, LEVEL3, self.chapter, read_legacy=False)
        self.intermediate = stage_chapter(self.manga, CONSOLIDATED, self.chapter,
                                          read_legacy=False)
        self.image = self.level1 / "clean" / self.filename
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(b"before glass")
        self.write_json(self.level1 / "json/clean-manifest.json", {"integrity_ok": True})
        self.level1_hash = digest((self.level1 / "json/clean-manifest.json").read_bytes())
        self.manifest = {
            "source_consolidated_manifest_sha256": digest(b"pre-glass manifest"),
            "source_level1_manifest_sha256": self.level1_hash,
            "source_level2_manifest_sha256": None,
            "source_artifacts": [self.filename],
            "source_artifact_sha256": [digest(b"before glass")],
        }
        self.intermediate_manifest = {
            "source_level1_manifest_sha256": self.level1_hash,
            "source_level2_manifest_sha256": digest(b"glass manifest"),
            "source_combo_manifest_sha256": None,
            "clean_artifacts": [f"clean/{self.filename}"],
            "selections": [{"artifact": f"clean/{self.filename}",
                            "selected_from": LEVEL2, "sha256": digest(b"after glass")}],
        }
        self.write_json(self.level3 / "json/clean-manifest.json", self.manifest)
        self.write_json(self.intermediate / "json/clean-manifest.json",
                        self.intermediate_manifest)

    @staticmethod
    def write_json(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_pre_glass_mapear_stays_current_and_serves_the_image_it_analyzed(self):
        self.assertTrue(pre_glass_mapear_current(self.manga, self.chapter, self.manifest))
        with patch("central_v2.backend.orchestration.textoff_merged.level3_source.consolidated_image",
                   side_effect=AssertionError("Glass output must not replace Mapear input")):
            self.assertEqual(mapear_input_image(self.manga, self.chapter, self.filename),
                             self.image)

    def test_changed_level_one_image_invalidates_mapear(self):
        self.image.write_bytes(b"different input")
        self.assertFalse(pre_glass_mapear_current(self.manga, self.chapter, self.manifest))

    def test_combo_selection_invalidates_mapear(self):
        self.intermediate_manifest["selections"][0]["selected_from"] = "COMBO_TURBO"
        self.write_json(self.intermediate / "json/clean-manifest.json",
                        self.intermediate_manifest)
        self.assertFalse(pre_glass_mapear_current(self.manga, self.chapter, self.manifest))

    def test_mapear_run_after_glass_needs_its_exact_source(self):
        self.manifest["source_level2_manifest_sha256"] = digest(b"earlier glass")
        self.assertFalse(pre_glass_mapear_current(self.manga, self.chapter, self.manifest))


if __name__ == "__main__":
    unittest.main()
