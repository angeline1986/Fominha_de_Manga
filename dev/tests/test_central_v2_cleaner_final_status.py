"""The Check counts current, verified final pages and applied Laboratory work."""
import json
from pathlib import Path
import tempfile
import unittest

from central_v2.backend.orchestration.textoff_merged.cleaner_final_status import current_final_status
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class CleanerFinalStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Example"
        self.manifest = final_manifest_path(self.manga, "1")
        self.manifest.parent.mkdir(parents=True)
        self.folder = self.manifest.parent.parent

    def write(self, origins, history=None):
        pages = {}
        for number, (origin, extra) in enumerate(origins.values()):
            name = f"page-{number}.png"
            image = self.folder / name
            image.write_bytes(f"image {number}".encode())
            pages[name] = {"page": name, "artifact": name, "sha256": sha256(image),
                           "origin": origin, **extra}
        payload = {"schema": "textoff_consolidado_final_manifest_v1", "version": 1,
                   "provider": "comix", "manga": "Example", "chapter": "1",
                   "pages": pages, "history": history or []}
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        return pages

    def test_glass_brush_and_applied_laboratory_are_counted(self):
        self.write({"glass": ("AUTO_CLEANER_TRANSPARENCIA", {}),
                    "art": ("PINCEL_ARTISTICO", {}),
                    "lab": ("LABORATORIO", {"visual_review": "confirmed",
                                           "run_id": "run", "laboratory_snapshot": "laboratorio/run/page.png"}),
                    "manual": ("MANUAL_LAB_REPLACEMENT", {"status": "processed",
                                  "source_run_id": "old", "source_artifact": "treatment/result.png"})})
        self.assertEqual(current_final_status(self.manga, "1"),
                         (True, {"artistic", "laboratory"}))

    def test_restored_laboratory_history_is_not_current(self):
        self.write({"restored": ("AUTO_CLEANER", {})},
                   history=[{"superseded": {"origin": "LABORATORIO"}}])
        self.assertEqual(current_final_status(self.manga, "1"), (False, set()))

    def test_unconfirmed_or_tampered_page_is_not_counted(self):
        pages = self.write({"lab": ("LABORATORIO", {"visual_review": "pending",
                                      "run_id": "run", "laboratory_snapshot": "snapshot"})})
        self.assertEqual(current_final_status(self.manga, "1"), (False, set()))
        page = next(iter(pages))
        pages[page]["visual_review"] = "confirmed"
        self.manifest.write_text(json.dumps({**json.loads(self.manifest.read_text()),
                                              "pages": pages}), encoding="utf-8")
        (self.folder / page).write_bytes(b"tampered")
        self.assertEqual(current_final_status(self.manga, "1"), (False, set()))
