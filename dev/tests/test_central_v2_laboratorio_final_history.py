"""Verified final-page history can be previewed and restored without data loss."""
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from PIL import Image

from central_v2.backend.orchestration.textoff_merged import laboratorio_final_restore
from central_v2.backend.routes.router import dispatch_get, dispatch_post
from test_central_v2_laboratorio_final_apply import LaboratoryApplyTests


class LaboratoryHistoryTests(unittest.TestCase):
    setUp = LaboratoryApplyTests.setUp
    write_manifest = LaboratoryApplyTests.write_manifest
    make_run = LaboratoryApplyTests.make_run
    proposal = LaboratoryApplyTests.proposal
    apply = LaboratoryApplyTests.apply

    def history(self):
        identity = {key: self.identity[key] for key in ("provider", "manga", "chapter", "page")}
        response = dispatch_get("/api/textoff/laboratorio/final/history?" + urlencode(identity),
                                self.root)
        self.assertEqual(response.status, 200, response.body)
        return json.loads(response.body)

    def restore(self, history, revision, confirmed=True):
        payload = {key: self.identity[key] for key in ("provider", "manga", "chapter", "page")}
        return dispatch_post("/api/textoff/laboratorio/final/restore",
                             {**payload, "version": history["version"],
                              "revision_id": revision["revision_id"], "confirmed": confirmed},
                             self.root)

    def test_restores_old_page_and_preserves_every_revision(self):
        original = self.final.read_bytes()
        first = self.proposal()
        self.assertEqual(self.apply(first["version"]).status, 200)
        laboratory = self.final.read_bytes()
        history = self.history()
        self.assertEqual(len(history["revisions"]), 1)
        self.assertEqual(dispatch_get(history["current_image_url"], self.root).body, laboratory)
        self.assertEqual(dispatch_get(history["revisions"][0]["image_url"], self.root).body,
                         original)
        response = self.restore(history, history["revisions"][0])
        self.assertEqual(response.status, 200, response.body)
        self.assertEqual(self.final.read_bytes(), original)
        after = self.history()
        self.assertEqual(len(after["revisions"]), 2)
        self.assertEqual(after["current"]["origin"], "PINCEL_SUAVE")
        self.assertEqual(dispatch_get(after["revisions"][0]["image_url"], self.root).body,
                         laboratory)
        self.assertEqual(dispatch_get(history["current_image_url"], self.root).status, 404)
        self.assertEqual(dispatch_get(history["revisions"][0]["image_url"], self.root).status, 404)

    def test_repeated_corrections_and_restoration_keep_history(self):
        first = self.proposal()
        self.assertEqual(self.apply(first["version"]).status, 200)
        self.run_id = "b" * 32
        self.identity["run_id"] = self.run_id
        self.make_run("red")
        second = self.proposal()
        self.assertEqual(self.apply(second["version"]).status, 200)
        history = self.history()
        self.assertEqual(len(history["revisions"]), 2)
        earlier = history["revisions"][-1]
        self.assertEqual(self.restore(history, earlier).status, 200)
        self.assertEqual(len(self.history()["revisions"]), 3)
        rows = json.loads(self.manifest.read_text())["history"]
        self.assertEqual([row["reason"] for row in rows],
                         ["laboratorio_apply", "laboratorio_apply", "laboratorio_restore"])

    def test_invalid_archive_and_stale_or_unconfirmed_restore_are_rejected(self):
        first = self.proposal()
        self.assertEqual(self.apply(first["version"]).status, 200)
        history = self.history()
        revision = history["revisions"][0]
        before = self.manifest.read_bytes()
        self.assertEqual(self.restore(history, revision, False).status, 400)
        self.assertEqual(self.manifest.read_bytes(), before)
        archive = self.manifest.parent.parent / "history" / revision["sha256"] / "page.png"
        Image.new("RGB", (20, 30), "orange").save(archive)
        self.assertEqual(self.history()["revisions"], [])
        self.assertEqual(self.restore(history, revision).status, 400)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_restore_rejects_version_changed_after_comparison(self):
        first = self.proposal()
        self.assertEqual(self.apply(first["version"]).status, 200)
        history = self.history()
        self.run_id = "b" * 32
        self.identity["run_id"] = self.run_id
        self.make_run("red")
        second = self.proposal()
        self.assertEqual(self.apply(second["version"]).status, 200)
        before = self.manifest.read_bytes()
        self.assertEqual(self.restore(history, history["revisions"][0]).status, 409)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_failure_after_swap_rolls_back_restoration(self):
        first = self.proposal()
        self.assertEqual(self.apply(first["version"]).status, 200)
        history = self.history()
        image, manifest = self.final.read_bytes(), self.manifest.read_bytes()
        verify = laboratorio_final_restore._verify

        def fail_after_swap(folder, *args):
            if folder.name == "1":
                raise ValueError("Falha simulada após troca")
            return verify(folder, *args)

        with patch.object(laboratorio_final_restore, "_verify", side_effect=fail_after_swap):
            response = self.restore(history, history["revisions"][0])
        self.assertEqual(response.status, 400)
        self.assertEqual(self.final.read_bytes(), image)
        self.assertEqual(self.manifest.read_bytes(), manifest)


if __name__ == "__main__":
    unittest.main()
