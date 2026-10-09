"""Restoration may recover only a manifest-linked immutable treatment input."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for
from central_v2.backend.orchestration.textoff_merged.special_page_restore_source import restoration_source


class HistoricalRestoreSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Example"
        self.chapter, self.page, self.run = "1", "page-001.png", "abc123"
        self.folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/06_PINCEL/SUAVE/1"
        self.source = self.folder / "input" / self.run / self.page
        self.output = self.folder / "archive" / self.run / "clean/output.png"
        self.source.parent.mkdir(parents=True)
        self.output.parent.mkdir(parents=True)
        self.source.write_bytes(b"authentic-input")
        self.output.write_bytes(b"verified-output")
        self.manifest = self.folder / "json/suave-manifest.json"
        self.manifest.parent.mkdir(parents=True)
        self._write_manifest()

    def _write_manifest(self):
        record = {"provider": "comix", "manga": "Example", "chapter": self.chapter,
            "page": self.page, "treatment": "gradiente_suave", "run_id": self.run,
            "selected_from": "AUTO_CLEANER_TRANSPARENCIA",
            "input": {"path": "/historical/path/page.png", "sha256": sha256(self.source)},
            "input_artifact": {"artifact": f"input/{self.run}/{self.page}",
                               "sha256": sha256(self.source)},
            "consolidated_manifest": {"path": "/historical/manifest.json", "sha256": "a" * 64},
            "output": {"artifact": "clean/page-001_suave.png", "sha256": sha256(self.output)}}
        payload = {"schema": "textoff_pincel_suave_manifest_v1", "version": 1,
            "provider": "comix", "manga": "Example", "chapter": self.chapter,
            "treatment": "gradiente_suave",
            "algorithm": treatment_for("gradiente_suave").algorithm, "pages": {},
            "superseded_results": [{"pages": [{"page": self.page, "record": record,
                "archived_artifacts": [{"artifact": f"archive/{self.run}/clean/output.png",
                                        "sha256": sha256(self.output)}]}]}]}
        self.manifest.write_text(json.dumps(payload))
        self.first = {"origin": "PINCEL_SUAVE", "page": self.page, "artifact": self.page,
            "run_id": self.run, "input_origin": "AUTO_CLEANER_TRANSPARENCIA",
            "input_sha256": sha256(self.source), "input_manifest_sha256": "a" * 64,
            "sha256": sha256(self.output)}

    def test_resolves_snapshot_when_current_level2_is_absent(self):
        source, manifest, manifest_hash = restoration_source(
            self.manga, self.chapter, self.page, self.first)
        self.assertEqual(source.resolve(), self.source.resolve())
        self.assertEqual(manifest.resolve(), self.manifest.resolve())
        self.assertEqual(manifest_hash, sha256(self.manifest))

    def test_rejects_snapshot_with_changed_hash(self):
        self.source.write_bytes(b"different-input")
        with self.assertRaisesRegex(ValueError, "Snapshot histórico ausente ou com SHA divergente"):
            restoration_source(self.manga, self.chapter, self.page, self.first)

    def test_rejects_unlinked_page_or_run(self):
        for change in ({"page": "page-002.png"}, {"run_id": "unknown"},
                       {"input_manifest_sha256": "b" * 64}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                restoration_source(self.manga, self.chapter, self.page,
                                   {**self.first, **change})


if __name__ == "__main__":
    unittest.main()
