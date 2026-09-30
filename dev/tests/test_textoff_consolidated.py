import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.consolidated import (
    consolidated_is_current, rebuild_consolidated,
)
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2


class TextoffConsolidatedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "manga"
        self.chapter = "1"
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1"
        merge.mkdir(parents=True)
        names = ["page-001-005.png", "page-005-010.png"]
        for name in names:
            (merge / name).write_bytes(b"merge:" + name.encode())
        (merge / "merge-manifest.json").write_text(json.dumps({
            "merged_images": 2, "source_total_height": 10,
            "outputs": [
                {"file": names[0], "global_start": 0, "global_end": 5},
                {"file": names[1], "global_start": 5, "global_end": 10},
            ],
        }), encoding="utf-8")
        self.sources = names
        self._write_stage(LEVEL1, [b"level1-a", b"level1-b"], None)

    def _write_stage(self, stage, contents, source_hash):
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / stage / self.chapter
        (folder / "clean").mkdir(parents=True, exist_ok=True)
        (folder / "json").mkdir(parents=True, exist_ok=True)
        clean_names = [Path(name).stem + "_clean.png" for name in self.sources]
        for name, content in zip(clean_names, contents):
            (folder / "clean" / name).write_bytes(content)
        manifest = {
            "source_stage": "MERGE" if stage == LEVEL1 else LEVEL1,
            "integrity_ok": True, "source_artifacts": self.sources,
            "clean_artifacts": [f"clean/{name}" for name in clean_names],
            "outputs_total": len(clean_names),
        }
        if stage == LEVEL2:
            manifest["source_level1_manifest_sha256"] = source_hash
        (folder / "json/clean-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")

    def test_falls_back_to_level1_until_valid_level2_exists(self):
        result = rebuild_consolidated(self.manga, self.chapter)
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/1"
        manifest = json.loads((folder / "json/clean-manifest.json").read_text())
        self.assertEqual(result["level2_outputs_used"], 0)
        self.assertEqual([item["selected_from"] for item in manifest["selections"]], [LEVEL1, LEVEL1])
        self.assertFalse((folder / "clean/page-001-005_clean.png").exists())
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))

    def test_prefers_valid_level2_and_invalidates_when_its_manifest_changes(self):
        level1_manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest.read_bytes()).hexdigest()
        self._write_stage(LEVEL2, [b"level2-a", b"level2-b"], source_hash)
        level2_manifest_path = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_II/1/json/clean-manifest.json"
        level2_manifest = json.loads(level2_manifest_path.read_text())
        level2_manifest["candidate_source_artifacts"] = self.sources
        level2_manifest["pages_total"] = 2
        level2_manifest["changed_artifacts"] = level2_manifest["clean_artifacts"]
        level2_manifest_path.write_text(json.dumps(level2_manifest), encoding="utf-8")
        result = rebuild_consolidated(self.manga, self.chapter)
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/1"
        manifest_path = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_II/1/json/clean-manifest.json"
        manifest = json.loads((folder / "json/clean-manifest.json").read_text())
        self.assertEqual(result["level2_outputs_used"], 2)
        self.assertEqual([item["selected_from"] for item in manifest["selections"]], [LEVEL2, LEVEL2])
        self.assertEqual((folder / "clean/page-005-010_clean.png").read_bytes(), b"level2-b")
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))
        manifest_path.write_text(manifest_path.read_text() + " ", encoding="utf-8")
        self.assertFalse(consolidated_is_current(self.manga, self.chapter))

    def test_keeps_only_changed_pages_in_level2_and_references_level1_for_rest(self):
        level1_manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1/json/clean-manifest.json"
        source_hash = hashlib.sha256(level1_manifest.read_bytes()).hexdigest()
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / LEVEL2 / self.chapter
        (folder / "clean").mkdir(parents=True)
        (folder / "json").mkdir()
        changed = "page-001-005_clean.png"
        (folder / "clean" / changed).write_bytes(b"level2-changed")
        (folder / "json/clean-manifest.json").write_text(json.dumps({
            "source_stage": LEVEL1, "integrity_ok": True,
            "source_level1_manifest_sha256": source_hash,
            "source_artifacts": self.sources, "candidate_source_artifacts": [self.sources[0]], "pages_total": 1,
            "clean_artifacts": [f"clean/{changed}"],
            "changed_artifacts": [f"clean/{changed}"], "outputs_total": 1,
        }), encoding="utf-8")

        result = rebuild_consolidated(self.manga, self.chapter)
        consolidated = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/1"
        self.assertEqual(result["level2_outputs_used"], 1)
        self.assertTrue((consolidated / "clean/page-001-005_clean.png").is_file())
        self.assertFalse((consolidated / "clean/page-005-010_clean.png").exists())
        self.assertTrue(consolidated_is_current(self.manga, self.chapter))


if __name__ == "__main__":
    unittest.main()
