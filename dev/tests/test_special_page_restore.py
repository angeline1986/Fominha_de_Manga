"""Page reset must use an authenticated automatic input and keep other pages."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import SCHEMA as CHECK_SCHEMA, manifest_path as check_path
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path, read_final_page
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import write_manifest
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import manifest_path as special_path, rebuild_special_treatments
from central_v2.backend.orchestration.textoff_merged.special_styled_input import pending_pages as styled_pending
from central_v2.backend.orchestration.textoff_merged.special_degrade_input import pending_pages as degrade_pending
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL2, stage_chapter
from central_v2.backend.orchestration.textoff_merged.special_page_restore import inspect, restore
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.routes.special_page_restore import get_response, post_response
from central_v2.backend.routes.textoff_merged_router import dispatch_textoff_merged_get, dispatch_textoff_merged_post


class PageRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Example"
        (self.manga / "IMG").mkdir(parents=True)
        self.chapter, self.page, self.other = "1", "page-001.png", "page-002.png"
        check = check_path(self.manga, self.chapter)
        check.parent.mkdir(parents=True)
        approved = []
        for index, kind in enumerate(["balao_estilizado"] * 4 + ["residuo_degrade"] * 2):
            approved.append({"id": f"roi-{index}", "page": self.page, "tipo": kind,
                "box_normalized": {"left": .1, "top": .1, "width": .2, "height": .2},
                "box_pixels": {"x": index, "y": 0, "width": 1, "height": 1}})
        approved.append({"id": "other-art", "page": self.other, "tipo": "balao_estilizado",
            "box_normalized": {"left": .1, "top": .1, "width": .2, "height": .2},
            "box_pixels": {"x": 0, "y": 0, "width": 1, "height": 1}})
        check.write_text(json.dumps({"schema": CHECK_SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": self.chapter,
            "source_snapshot": {}, "approved_occurrences": approved}))
        self.special, payload, _ = rebuild_special_treatments(self.manga,
            {"provider": "comix", "obra": "Example", "capitulo": self.chapter}, self.chapter)
        for rows in payload["treatments"].values():
            for row in rows:
                row.update(status="processed", result={"run_id": "old"})
        self.special.write_text(json.dumps(payload))
        level = stage_chapter(self.manga, LEVEL2, self.chapter, read_legacy=False)
        self.source = level / "clean/page-001_clean.png"
        self._image(self.source, 10)
        source_manifest = level / "json/clean-manifest.json"
        source_manifest.parent.mkdir(parents=True)
        source_manifest.write_text(json.dumps({"source_artifacts": [self.page],
            "clean_artifacts": ["clean/page-001_clean.png"]}))
        self.final = stage_chapter(self.manga, "CONSOLIDADO_FINAL", self.chapter, read_legacy=False)
        self._image(self.final / self.page, 30)
        self._image(self.final / self.other, 90)
        self.final_manifest = final_manifest_path(self.manga, self.chapter)
        self.auto = {"page": self.page, "artifact": self.page, "sha256": sha256(self.source),
            "origin": "AUTO_CLEANER_TRANSPARENCIA", "treatment": None, "input_sha256": None}
        self.art = {"page": self.page, "artifact": self.page, "sha256": "a" * 64,
            "origin": "PINCEL_ARTISTICO", "treatment": "estilizado",
            "input_sha256": sha256(self.source), "input_origin": "AUTO_CLEANER_TRANSPARENCIA",
            "input_manifest_sha256": "b" * 64, "run_id": "art-old", "status": "processed"}
        self.degrade = {"page": self.page, "artifact": self.page,
            "sha256": sha256(self.final / self.page), "origin": "PINCEL_DEGRADE",
            "treatment": "degrade", "input_sha256": self.art["sha256"],
            "input_origin": "PINCEL_ARTISTICO", "run_id": "deg-old", "status": "processed"}
        self._final([{"page": self.page, "superseded": row} for row in (self.auto, self.art)])

    def _image(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(cv2.imwrite(str(path), np.full((8, 8, 3), value, dtype=np.uint8)))

    def _final(self, history):
        write_manifest(self.final, {"schema": "textoff_consolidado_final_manifest_v1", "version": 1,
            "provider": "comix", "manga": "Example", "chapter": self.chapter,
            "source_intermediate_manifest_sha256": "baseline", "page_count": 2,
            "pages": {self.page: self.degrade, self.other: {"page": self.other,
                "artifact": self.other, "sha256": sha256(self.final / self.other),
                "origin": "AUTO_CLEANER", "treatment": None, "input_sha256": None}},
            "history": history})

    def test_restores_whole_page_and_marks_only_its_treatments_pending(self):
        proposal = inspect(self.manga, "comix", self.chapter, self.page)
        self.assertEqual(proposal["restored_sha256"], sha256(self.source))
        self.assertEqual(proposal["affected_occurrences"], 6)
        old_other = sha256(self.final / self.other)
        old_check = sha256(check_path(self.manga, self.chapter))
        previous = json.loads(self.special.read_text())
        other_row = next(row for row in previous["treatments"]["estilizado"] if row["page"] == self.other)
        target_rois = {row["id"]: row["box_pixels"] for rows in previous["treatments"].values()
                       for row in rows if row["page"] == self.page}
        result = restore(self.manga, "comix", self.chapter, self.page, proposal,
                         confirmed=True)
        self.assertEqual(result["status"], "restored")
        self.assertEqual(result["invalidated_runs"], 2)
        record, image, _ = read_final_page(self.manga, self.chapter, self.page)
        self.assertEqual(record["origin"], "AUTO_CLEANER_TRANSPARENCIA")
        self.assertEqual(sha256(image), sha256(self.source))
        self.assertEqual(sha256(self.final / self.other), old_other)
        self.assertEqual(sha256(check_path(self.manga, self.chapter)), old_check)
        updated = json.loads(self.special.read_text())
        self.assertEqual(next(row for row in updated["treatments"]["estilizado"]
                              if row["page"] == self.other), other_row)
        self.assertEqual({row["id"]: row["box_pixels"] for rows in updated["treatments"].values()
                          for row in rows if row["page"] == self.page}, target_rois)
        self.assertTrue(all(row["status"] == "pending" and "result" not in row
            for rows in updated["treatments"].values()
            for row in rows if row["page"] == self.page))
        invalidated = updated["page_restoration_history"][0]["invalidated_runs"]
        self.assertEqual({row["run_id"] for row in invalidated}, {"art-old", "deg-old"})
        self.assertTrue(all(row["status"] == "invalidated_by_page_restoration"
                            for row in invalidated))
        backup = self.manga / result["backup"]
        evidence = json.loads((backup / "backup.json").read_text())
        self.assertEqual(sha256(backup / "consolidado_final" / self.page), evidence["page_sha256"])
        self.assertEqual(sha256(backup / "consolidado_final/json/final-manifest.json"),
                         evidence["final_manifest_sha256"])
        _, rebuilt, _ = rebuild_special_treatments(self.manga,
            {"provider": "comix", "obra": "Example", "capitulo": self.chapter}, self.chapter)
        self.assertEqual(rebuilt["page_restoration_history"][0]["backup"], result["backup"])
        self.assertTrue(all(row["status"] == "pending" for rows in rebuilt["treatments"].values()
                            for row in rows if row["page"] == self.page))
        with self.assertRaisesRegex(ValueError, "Check indisponível"):
            styled_pending(self.manga, "comix", self.chapter)
        self.assertEqual(len(degrade_pending(self.manga, "comix", self.chapter)[3][self.page]), 2)

    def test_stale_sha_and_broken_lineage_block_without_publication(self):
        proposal = inspect(self.manga, "comix", self.chapter, self.page)
        self._image(self.final / self.page, 31)
        with self.assertRaises(ValueError):
            restore(self.manga, "comix", self.chapter, self.page, proposal, confirmed=True)
        self._image(self.final / self.page, 30)
        self.art["input_sha256"] = "0" * 64
        self._final([{"page": self.page, "superseded": row} for row in (self.auto, self.art)])
        with self.assertRaises(ValueError):
            inspect(self.manga, "comix", self.chapter, self.page)
        self.assertEqual(json.loads(self.special.read_text())["treatments"]["estilizado"][0]["status"], "processed")

    def test_preview_serves_both_verified_images_and_rejects_stale_version(self):
        query = {"provider": ["comix"], "manga": ["Example"], "chapter": [self.chapter],
                 "page": [self.page]}
        response = get_response(query, Path(self.temp.name))
        self.assertEqual(response.status, 200)
        proposal = json.loads(response.body)["proposal"]
        for side, path in (("current", self.final / self.page), ("restored", self.source)):
            image = get_response({**query, "version": [proposal["version"]], "side": [side]},
                                 Path(self.temp.name), image=True)
            self.assertEqual(image.status, 200)
            self.assertEqual(image.body, path.read_bytes())
        stale = get_response({**query, "version": ["wrong"], "side": ["restored"]},
                             Path(self.temp.name), image=True)
        self.assertEqual(stale.status, 400)

    def test_post_queues_only_a_confirmed_current_proposal(self):
        proposal = inspect(self.manga, "comix", self.chapter, self.page)
        payload = {"provider": "comix", "manga": "Example", "chapter": self.chapter,
                   "page": self.page, "proposal": proposal, "confirmed": True}
        with patch("central_v2.backend.routes.special_page_restore.submit",
                   return_value={"id": "job"}) as submit:
            accepted = post_response(payload, Path(self.temp.name))
            self.assertEqual(accepted.status, 202)
            self.assertEqual(json.loads(accepted.body)["job"]["id"], "job")
            submit.assert_called_once()
        payload["proposal"] = {**proposal, "current_sha256": "0" * 64}
        self.assertEqual(post_response(payload, Path(self.temp.name)).status, 400)

    def test_router_exposes_preview_and_confirmation_gate(self):
        path = "/api/textoff/special/restore-page"
        query = urlencode({"provider": "comix", "manga": "Example",
                           "chapter": self.chapter, "page": self.page})
        response = dispatch_textoff_merged_get(SimpleNamespace(path=path, query=query),
                                               Path(self.temp.name))
        self.assertEqual(response.status, 200)
        proposal = json.loads(response.body)["proposal"]
        rejected = dispatch_textoff_merged_post(path, {"provider": "comix", "manga": "Example",
            "chapter": self.chapter, "page": self.page, "proposal": proposal,
            "confirmed": False}, Path(self.temp.name))
        self.assertEqual(rejected.status, 400)

    def test_failure_during_publication_recovers_final_and_special(self):
        proposal = inspect(self.manga, "comix", self.chapter, self.page)
        before_final = sha256(self.final_manifest)
        before_page = sha256(self.final / self.page)
        before_special = sha256(self.special)
        from central_v2.backend.orchestration.textoff_merged import special_styled_transaction as tx
        original = tx.durable_replace
        calls = 0
        def fail_once(source, target):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("falha simulada")
            return original(source, target)
        with patch.object(tx, "durable_replace", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "falha simulada"):
                restore(self.manga, "comix", self.chapter, self.page, proposal, confirmed=True)
        self.assertEqual(sha256(self.final_manifest), before_final)
        self.assertEqual(sha256(self.final / self.page), before_page)
        self.assertEqual(sha256(self.special), before_special)
        self.assertFalse(list((self.manga / "SPECIAL_PAGE_RESTORE_BACKUPS" / self.chapter).glob("*")))

    def test_check_change_just_before_publication_blocks_reset(self):
        proposal = inspect(self.manga, "comix", self.chapter, self.page)
        before_final = sha256(self.final_manifest)
        before_special = sha256(self.special)
        from central_v2.backend.orchestration.textoff_merged import special_page_restore as reset
        original = reset.publish
        def race(manga, folder, entries, validate):
            check = check_path(self.manga, self.chapter)
            check.write_text(check.read_text() + "\n")
            return original(manga, folder, entries, validate)
        with patch.object(reset, "publish", side_effect=race):
            with self.assertRaises(ValueError):
                restore(self.manga, "comix", self.chapter, self.page, proposal, confirmed=True)
        self.assertEqual(sha256(self.final_manifest), before_final)
        self.assertEqual(sha256(self.special), before_special)

    def test_requires_explicit_confirmation_and_source_manifest(self):
        proposal = inspect(self.manga, "comix", self.chapter, self.page)
        with self.assertRaisesRegex(ValueError, "Confirmação explícita"):
            restore(self.manga, "comix", self.chapter, self.page, proposal)
        response = post_response({"provider": "comix", "manga": "Example",
            "chapter": self.chapter, "page": self.page, "proposal": proposal,
            "confirmed": False}, Path(self.temp.name))
        self.assertEqual(response.status, 400)
        self.source.unlink()
        with self.assertRaises(ValueError):
            inspect(self.manga, "comix", self.chapter, self.page)


if __name__ == "__main__":
    unittest.main()
