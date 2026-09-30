"""Input provenance and path boundary tests for special previews."""
import tempfile
import unittest
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256, write_json
from central_v2.backend.orchestration.textoff_special.inputs import resolve_input, validate_selections


class SpecialInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "manga"
        self.stage = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
        self.folder = self.stage / "MERGED_NIVEL_I/3"
        (self.folder / "clean").mkdir(parents=True)
        (self.folder / "json").mkdir()
        self.source = self.folder / "clean/page_clean.png"
        self.source.write_bytes(b"image fixture")
        self.manifest = self.folder / "json/clean-manifest.json"
        self.payload = {"integrity_ok": True, "source_stage": "MERGE",
                        "clean_artifacts": ["clean/page_clean.png"]}
        write_json(self.manifest, self.payload)

    def resolve(self, **kwargs):
        args = dict(manga=self.manga, level="MERGED_NIVEL_I", chapter="3",
                    filename="page_clean.png", expected_sha256=sha256(self.source))
        return resolve_input(**{**args, **kwargs})

    def test_registered_image_is_bound_to_manifest_and_bytes(self):
        source = self.resolve()
        self.assertEqual(source["path"], str(self.source.resolve()))
        self.assertEqual(source["predecessors"][0]["sha256"], sha256(self.manifest))

    def test_stale_bytes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "OBSOLETA"):
            self.resolve(expected_sha256="0" * 64)

    def test_unregistered_image_and_ambiguous_entries_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "ausente"):
            self.resolve(filename="other.png")
        self.payload["clean_artifacts"].append("page_clean.png")
        write_json(self.manifest, self.payload)
        with self.assertRaisesRegex(ValueError, "ambígua"):
            self.resolve()

    def test_paths_cannot_escape_through_names_or_symlinks(self):
        with self.assertRaises(ValueError):
            self.resolve(chapter="../3")
        outside = Path(self.temp.name) / "outside.png"
        outside.write_bytes(b"external image")
        self.source.unlink()
        self.source.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "fora"):
            self.resolve()

    def test_level2_requires_current_level1_predecessor(self):
        folder = self.stage / "MERGED_NIVEL_II/3"
        (folder / "clean").mkdir(parents=True)
        (folder / "json").mkdir()
        (folder / "clean/page_clean.png").write_bytes(self.source.read_bytes())
        payload = {**self.payload, "source_stage": "MERGED_NIVEL_I",
                   "source_level1_manifest_sha256": sha256(self.manifest)}
        write_json(folder / "json/clean-manifest.json", payload)
        self.resolve(level="MERGED_NIVEL_II")
        self.manifest.write_text(self.manifest.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "predecessor"):
            self.resolve(level="MERGED_NIVEL_II")

    def test_invalid_roi_values_fail_before_processing(self):
        for value in [None, [], [{}], [{"x": float("nan"), "y": 0, "width": 1, "height": 1}],
                      [{"x": True, "y": 0, "width": 1, "height": 1}],
                      [{"x": 0, "y": 0, "width": 0, "height": 1}]]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_selections(value)


if __name__ == "__main__":
    unittest.main()
