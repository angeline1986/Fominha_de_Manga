"""Artístico Check routing, current-final input, persistence, review, and retry safety."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA as CHECK_SCHEMA, manifest_path as check_path,
)
from central_v2.backend.orchestration.textoff_merged.final_consolidated import (
    final_manifest_path, read_final_page,
)
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import write_manifest
from central_v2.backend.orchestration.textoff_merged.special_styled_execution import execute_styled
from central_v2.backend.orchestration.textoff_merged.special_styled_review import review_pairs
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    manifest_path as special_path, rebuild_special_treatments,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for
from central_v2.backend.routes.textoff_comparison import comparison_response


class StyledExecutionTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Candy YumYum (Yaoi)"
        (self.manga / "IMG/1").mkdir(parents=True)
        self.page, self.check = "page-001.png", check_path(self.manga, "1")
        self.check.parent.mkdir(parents=True)
        occurrence = {"id": "styled-1", "page": self.page, "tipo": "balao_estilizado",
            "box_normalized": {"left": .2, "top": .2, "width": .3, "height": .3},
            "box_pixels": {"x": 20, "y": 20, "width": 30, "height": 30},
            "origin": "MANUAL", "origins": ["MANUAL"]}
        self.check.write_text(json.dumps({"schema": CHECK_SCHEMA, "version": 1,
            "provider": "comix", "manga": self.manga.name, "chapter": "1",
            "source_snapshot": {}, "approved_occurrences": [occurrence]}))
        self.special, _, _ = rebuild_special_treatments(self.manga,
            {"provider": "comix", "obra": self.manga.name, "capitulo": "1"}, "1")
        self.final = stage_chapter(self.manga, "CONSOLIDADO_FINAL", "1", read_legacy=False)
        self.final.mkdir(parents=True)
        image = self.final / self.page
        self.original = np.full((64, 64, 3), 20, dtype=np.uint8)
        self.assertTrue(cv2.imwrite(str(image), self.original))
        write_manifest(self.final, {"schema": "textoff_consolidado_final_manifest_v1", "version": 1,
            "provider": "comix", "manga": self.manga.name, "chapter": "1",
            "source_intermediate_manifest_sha256": "intermediate", "page_count": 1,
            "pages": {self.page: {"page": self.page, "artifact": self.page,
                "sha256": sha256(image), "origin": "AUTO_CLEANER", "treatment": None,
                "input_sha256": None}}, "history": []})

    def _preview(self, _manga, payload):
        self.assertEqual(payload["treatment"], "estilizado")
        self.assertEqual(payload["level"], "CONSOLIDADO_FINAL")
        self.assertEqual(payload["expected_sha256"], sha256(self.final / self.page))
        folder = self.root / "staging" / "styled123" / "treatment"
        folder.mkdir(parents=True, exist_ok=True)
        result, report = folder / "01_local_heal.png", folder / "roi_report.json"
        changed = self.original.copy()
        changed[25, 25] = (70, 80, 90)
        self.assertTrue(cv2.imwrite(str(result), changed))
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[20:50, 20:50] = 255
        mask_path = folder / "roi_authorized_mask.png"
        self.assertTrue(cv2.imwrite(str(mask_path), mask))
        report.write_text('{"algorithm":"textoff_special_roi_styled_v1"}')
        return {"execution_status": "succeeded", "run_id": "styled123",
            "source": {"sha256": payload["expected_sha256"]},
            "treatment": {"algorithm": treatment_for("estilizado").algorithm,
                          "artifacts": {"authorized_mask": mask_path.name}},
            "artifacts": {"treatment/roi_authorized_mask.png": sha256(mask_path)},
            "result_file": "treatment/01_local_heal.png",
            "validation": {"result_sha256": sha256(result), "changed_pixels": 4}}

    def test_persists_existing_algorithm_promotes_final_and_reviews_historical_pair(self):
        before, check_hash = (self.final / self.page).read_bytes(), sha256(self.check)
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_execution.preview",
                   side_effect=self._preview), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_output.STAGING_ROOT",
                   self.root / "staging"):
            result = execute_styled(self.manga, "comix", ["1"], lambda *_: None)
        self.assertEqual(result[0]["status"], "processed", result)
        stage = stage_chapter(self.manga, "PINCEL_ARTISTICO", "1", read_legacy=False)
        record = json.loads((stage / "json/artistico-manifest.json").read_text())["pages"][self.page]
        row, output, _ = read_final_page(self.manga, "1", self.page)
        self.assertEqual(row["origin"], "PINCEL_ARTISTICO")
        self.assertEqual(tuple(cv2.imread(str(output))[25, 25]), (70, 80, 90))
        self.assertEqual(record["input"]["sha256"], sha256_bytes(before))
        self.assertEqual(sha256(stage / record["output"]["artifact"]), record["output"]["sha256"])
        pair = review_pairs(self.manga, "comix", "1")[0]
        self.assertEqual(pair["before"].read_bytes(), before)
        self.assertEqual(tuple(cv2.imread(str(pair["after"]))[25, 25]), (70, 80, 90))
        self.assertEqual(sha256(self.check), check_hash)

    def test_reexecution_failure_preserves_all_operational_state(self):
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_execution.preview",
                   side_effect=self._preview), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_output.STAGING_ROOT",
                   self.root / "staging"):
            execute_styled(self.manga, "comix", ["1"], lambda *_: None)
        final_before = (self.final / self.page).read_bytes()
        manifest_before = final_manifest_path(self.manga, "1").read_bytes()
        special_before = self.special.read_bytes()
        art_stage = stage_chapter(self.manga, "PINCEL_ARTISTICO", "1", read_legacy=False)
        art_before = (art_stage / "json/artistico-manifest.json").read_bytes()
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_execution.preview",
                   return_value={"execution_status": "failed", "error": "worker failure"}):
            failed = execute_styled(self.manga, "comix", ["1"], lambda *_: None,
                reexecute=True, selections={"1": [{"page": self.page, "id": "styled-1"}]})
        self.assertEqual(failed[0]["status"], "failed")
        self.assertEqual((self.final / self.page).read_bytes(), final_before)
        self.assertEqual(final_manifest_path(self.manga, "1").read_bytes(), manifest_before)
        self.assertEqual(self.special.read_bytes(), special_before)
        self.assertEqual((art_stage / "json/artistico-manifest.json").read_bytes(), art_before)
        self.assertFalse(list((self.manga / ".central_v2_special_transactions").glob("*")))

    def test_shared_comparison_serves_historical_pair_and_blocks_hash_mismatch(self):
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_execution.preview",
                   side_effect=self._preview), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_output.STAGING_ROOT",
                   self.root / "staging"):
            execute_styled(self.manga, "comix", ["1"], lambda *_: None)
        chapter = query_special_treatments(self.manga, "comix", "estilizado")["chapters"][0]
        self.assertTrue(chapter["review_available"])
        base = {"comparisonMode": ["artistico"], "scope": ["artistico"],
                "step": ["artistico"], "provider": ["comix"],
                "manga": [self.manga.name], "chapter": ["1"]}
        listing = comparison_response(base, self.root)
        self.assertEqual(listing.status, 200)
        page = json.loads(listing.body)["pages"][0]
        for side, expected in (("before", (20, 20, 20)),
                               ("after", (70, 80, 90))):
            response = comparison_response({**base, "side": [side], "page": ["0"],
                                            "version": [page["version"]]}, self.root,
                                           image=True)
            self.assertEqual(response.status, 200)
            decoded = cv2.imdecode(np.frombuffer(response.body, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(tuple(decoded[25, 25]), expected)
        stage = stage_chapter(self.manga, "PINCEL_ARTISTICO", "1", read_legacy=False)
        (stage / "clean/page-001_artistico.png").write_bytes(b"tampered")
        blocked = comparison_response({**base, "side": ["after"], "page": ["0"],
                                       "version": [page["version"]]}, self.root, image=True)
        self.assertEqual(blocked.status, 404)


def sha256_bytes(content):
    import hashlib
    return hashlib.sha256(content).hexdigest()
