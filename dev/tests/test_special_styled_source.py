"""Check-bound input and preview for initial Artístico work."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA, manifest_path as check_path,
)
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import write_manifest
from central_v2.backend.orchestration.textoff_merged.special_styled_source import detection_input
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    manifest_path as special_path, rebuild_special_treatments,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.routes.special_treatments import styled_preview_image_response


class StyledSourceTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Example"
        (self.manga / "IMG/1").mkdir(parents=True)
        self.page, self.identity = "page-001.png", "styled-1"
        self.roi = {"x": 12, "y": 16, "width": 20, "height": 18}
        check = check_path(self.manga, "1")
        check.parent.mkdir(parents=True)
        check.write_text(json.dumps({"schema": SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": "1",
            "source_snapshot": {}, "approved_occurrences": [{
                "id": self.identity, "page": self.page, "tipo": "balao_estilizado",
                "box_normalized": {"left": .12, "top": .16, "width": .2, "height": .18},
                "box_pixels": self.roi}]}))
        rebuild_special_treatments(self.manga,
            {"provider": "comix", "obra": "Example", "capitulo": "1"}, "1")
        level = stage_chapter(self.manga, "TO_MERGED_NIVEL_I", "1")
        self.image = level / "clean/page-001_clean.png"
        self.image.parent.mkdir(parents=True)
        self.assertTrue(cv2.imwrite(str(self.image), np.full((64, 64, 3), 90, np.uint8)))
        manifest = level / "json/clean-manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"integrity_ok": True, "source_stage": "MERGE",
            "clean_artifacts": ["clean/page-001_clean.png"]}))
        consolidated = stage_chapter(self.manga, "TO_MERGED_CONSOLIDADO", "1")
        self.intermediate = consolidated / "json/clean-manifest.json"
        self.intermediate.parent.mkdir(parents=True)
        self.intermediate.write_text(json.dumps({"selections": [{
            "source": self.page, "selected_from": "TO_MERGED_NIVEL_I",
            "artifact": "clean/page-001_clean.png", "sha256": sha256(self.image)}]}))
        self.enterContext(patch(
            "central_v2.backend.orchestration.textoff_merged.special_styled_source.consolidated_is_current",
            return_value=True))

    def test_check_image_is_selected_with_real_sha_and_roi(self):
        source = detection_input(self.manga, "comix", "1", self.page, self.identity, self.roi)
        self.assertEqual(source["sha256"], sha256(self.image))
        self.assertEqual(source["path"], str(self.image.resolve()))
        self.assertEqual(source["level"], "MERGED_NIVEL_I")
        self.assertEqual((source["width"], source["height"]), (64, 64))
        self.assertEqual(source["consolidated_manifest_sha256"], sha256(self.intermediate))
        listed = query_special_treatments(self.manga, "comix", "estilizado")
        preview = listed["chapters"][0]["occurrences"][0]["preview"]
        self.assertEqual(preview["sha256"], sha256(self.image))
        response = styled_preview_image_response({"provider": ["comix"], "manga": ["Example"],
            "chapter": ["1"], "page": [self.page], "id": [self.identity],
            "sha256": [preview["sha256"]]}, self.root)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, self.image.read_bytes())

    def test_stale_check_or_image_has_no_final_fallback(self):
        self.image.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            detection_input(self.manga, "comix", "1", self.page, self.identity, self.roi)
        self.assertNotIn("preview", query_special_treatments(
            self.manga, "comix", "estilizado")["chapters"][0]["occurrences"][0])
        self.assertEqual(styled_preview_image_response({"provider": ["comix"],
            "manga": ["Example"], "chapter": ["1"], "page": [self.page],
            "id": [self.identity], "sha256": ["0" * 64]}, self.root).status, 404)

    def test_failed_occurrence_uses_the_same_check_image(self):
        special = special_path(self.manga, "1")
        payload = json.loads(special.read_text())
        payload["treatments"]["estilizado"][0]["status"] = "failed"
        special.write_text(json.dumps(payload))
        preview = query_special_treatments(self.manga, "comix", "estilizado")[
            "chapters"][0]["occurrences"][0]["preview"]
        self.assertEqual(preview["sha256"], sha256(self.image))
        response = styled_preview_image_response({"provider": ["comix"],
            "manga": ["Example"], "chapter": ["1"], "page": [self.page],
            "id": [self.identity], "sha256": [preview["sha256"]]}, self.root)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, self.image.read_bytes())

    def test_unapproved_roi_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ROI"):
            detection_input(self.manga, "comix", "1", self.page, self.identity,
                            {**self.roi, "x": 13})

    def test_shared_suave_preview_still_reads_the_current_final(self):
        special = special_path(self.manga, "1")
        payload = json.loads(special.read_text())
        payload["treatments"]["gradiente_suave"].append({
            "id": "smooth-1", "page": self.page, "treatment": "gradiente_suave",
            "status": "pending"})
        special.write_text(json.dumps(payload))
        final = stage_chapter(self.manga, "CONSOLIDADO_FINAL", "1")
        final.mkdir(parents=True)
        image = final / self.page
        image.write_bytes(self.image.read_bytes())
        write_manifest(final, {"schema": "textoff_consolidado_final_manifest_v1",
            "version": 1, "provider": "comix", "manga": "Example", "chapter": "1",
            "source_intermediate_manifest_sha256": sha256(self.intermediate),
            "page_count": 1, "pages": {self.page: {"page": self.page,
                "artifact": self.page, "sha256": sha256(image),
                "origin": "AUTO_CLEANER", "treatment": None}}, "history": []})
        response = styled_preview_image_response({"provider": ["comix"],
            "manga": ["Example"], "chapter": ["1"], "page": [self.page],
            "id": ["smooth-1"], "sha256": [sha256(image)]}, self.root)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, image.read_bytes())
