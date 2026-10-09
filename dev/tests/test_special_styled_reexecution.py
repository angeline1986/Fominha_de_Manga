"""End-to-end Artístico reexecution against temporary, hash-verified artifacts."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
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
from central_v2.backend.orchestration.textoff_merged.special_styled_execution import (
    execute_styled, validate_styled_reexecution,
)
from central_v2.backend.orchestration.textoff_merged.special_styled_output import (
    MANIFEST, SCHEMA, STAGE,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    manifest_path as special_path, rebuild_special_treatments,
)
from central_v2.backend.orchestration.textoff_merged.special_styled_plan import build_plan
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for


class StyledReexecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Example"
        self.chapter, self.page = "1", "page-001.png"
        self.check = check_path(self.manga, self.chapter)
        self.check.parent.mkdir(parents=True)
        roi = {"x": 2, "y": 2, "width": 4, "height": 4}
        decision = {"id": "approved-art", "page": self.page, "tipo": "balao_estilizado",
            "box_normalized": {"left": .1, "top": .1, "width": .2, "height": .2},
            "box_pixels": roi, "origin": "MANUAL", "origins": ["MANUAL"]}
        degrade = {"id": "approved-degrade", "page": self.page, "tipo": "residuo_degrade",
            "box_normalized": {"left": .5, "top": .5, "width": .2, "height": .2},
            "box_pixels": {"x": 8, "y": 8, "width": 4, "height": 4},
            "origin": "MANUAL", "origins": ["MANUAL"]}
        self.check.write_text(json.dumps({"schema": CHECK_SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": self.chapter,
            "source_snapshot": {},
            "approved_occurrences": [decision, degrade]}))
        self.special, payload, _ = rebuild_special_treatments(self.manga,
            {"provider": "comix", "obra": "Example", "capitulo": self.chapter}, self.chapter)
        payload["treatments"]["estilizado"][0]["status"] = "processed"
        payload["treatments"]["degrade"][0]["status"] = "processed"
        payload["treatments"]["degrade"][0]["result"] = {"kept": True}
        self.special.write_text(json.dumps(payload))
        self.source = self._image(self.root / "source.png",
            np.full((16, 16, 4), (10, 20, 30, 255), dtype=np.uint8))
        self.prior = cv2.imread(str(self.source), cv2.IMREAD_UNCHANGED)
        self.prior[2, 2] = (70, 80, 90, 255)
        self.prior_path = self._image(self.root / "prior.png", self.prior)
        self.art = stage_chapter(self.manga, STAGE, self.chapter, read_legacy=False)
        input_ref = f"input/old/{self.page}"
        output_ref, report_ref = "clean/page-001_artistico.png", "json/page-001_artistico_report.json"
        self._image(self.art / input_ref, cv2.imread(str(self.source), cv2.IMREAD_UNCHANGED))
        self._image(self.art / output_ref, self.prior)
        report = self.art / report_ref
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}")
        self.source_manifest = self.root / "source-manifest.json"
        self.source_manifest.write_text("authentic input manifest")
        self.final = stage_chapter(self.manga, "CONSOLIDADO_FINAL", self.chapter, read_legacy=False)
        self.final.mkdir(parents=True)
        self._image(self.final / self.page, self.prior)
        self.final_manifest = final_manifest_path(self.manga, self.chapter)
        write_manifest(self.final, {"schema": "textoff_consolidado_final_manifest_v1", "version": 1,
            "provider": "comix", "manga": "Example", "chapter": self.chapter,
            "source_intermediate_manifest_sha256": "baseline", "page_count": 1,
            "pages": {self.page: {"page": self.page, "artifact": self.page,
                "sha256": sha256(self.final / self.page), "origin": "PINCEL_ARTISTICO",
                "treatment": "estilizado", "input_sha256": sha256(self.source),
                "input_origin": "AUTO_CLEANER"}}, "history": []})
        record = {"provider": "comix", "manga": "Example", "chapter": self.chapter,
            "page": self.page, "treatment": "estilizado", "algorithm": treatment_for("estilizado").algorithm,
            "status": "processed", "occurrence_ids": ["approved-art"], "rois": [{"x": 2, "y": 2,
                "width": 4, "height": 4}], "selected_from": "AUTO_CLEANER",
            "input": {"path": str(self.source), "sha256": sha256(self.source)},
            "input_artifact": {"artifact": input_ref, "sha256": sha256(self.source)},
            "consolidated_manifest": {"path": str(self.source_manifest),
                "sha256": sha256(self.source_manifest)},
            "output": {"artifact": output_ref, "sha256": sha256(self.art / output_ref)},
            "report": {"artifact": report_ref, "sha256": sha256(report)}, "run_id": "oldrun"}
        write_mask = np.zeros((16, 16), dtype=np.uint8)
        write_mask[2:6, 2:6] = 255
        changed_mask = np.zeros_like(write_mask)
        changed_mask[2, 2] = 255
        write_path = self._image(self.art / "authorship/oldrun/approved-write.png", write_mask)
        changed_path = self._image(self.art / "authorship/oldrun/approved-changed.png", changed_mask)
        technical_path = self._image(self.art / "authorship/oldrun/technical.png", self.prior)
        record["occurrences"] = {"approved-art": {"roi": roi, "run_id": "oldrun",
            "status": "verified", "input_sha256": sha256(self.source),
            "technical_sha256": sha256(technical_path),
            "technical_output": {"artifact": str(technical_path.relative_to(self.art)),
                                 "sha256": sha256(technical_path)},
            "write_mask": {"artifact": str(write_path.relative_to(self.art)),
                           "sha256": sha256(write_path)},
            "changed_mask": {"artifact": str(changed_path.relative_to(self.art)),
                             "sha256": sha256(changed_path)}}}
        art_manifest = self.art / "json" / MANIFEST
        art_manifest.parent.mkdir(parents=True, exist_ok=True)
        art_manifest.write_text(json.dumps({"schema": SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": self.chapter,
            "treatment": "estilizado", "algorithm": treatment_for("estilizado").algorithm,
            "pages": {self.page: record}}))

    def _image(self, path, image):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(cv2.imwrite(str(path), image))
        return path

    def _preview(self, staging, run_id="newrun", value=(100, 110, 120, 255)):
        run_dir = staging / run_id / "treatment"
        run_dir.mkdir(parents=True)
        technical = cv2.imread(str(self.source), cv2.IMREAD_UNCHANGED)
        technical[2, 3] = value
        result = self._image(run_dir / "technical.png", technical)
        mask = np.zeros((16, 16), dtype=np.uint8)
        mask[2:6, 2:6] = 255
        mask_path = self._image(run_dir / "authorized.png", mask)
        (run_dir / "roi_report.json").write_text("{\"ok\":true}")
        return {"execution_status": "succeeded", "run_id": run_id,
            "source": {"sha256": sha256(self.source)},
            "treatment": {"algorithm": treatment_for("estilizado").algorithm,
                "artifacts": {"authorized_mask": "authorized.png"}},
            "artifacts": {"treatment/authorized.png": sha256(mask_path)},
            "result_file": "treatment/technical.png",
            "validation": {"result_sha256": sha256(result), "changed_pixels": 1}}

    def _selection(self):
        return [{"chapter": self.chapter, "page": self.page, "id": "approved-art",
                 "expected_sha256": sha256(self.final / self.page)}]

    def test_reexecutes_from_verified_history_and_preserves_rgba(self):
        staging = self.root / "staging"
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_output.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.preview",
                   side_effect=lambda _manga, _payload, **_kwargs: self._preview(staging)):
            result = execute_styled(self.manga, "comix", [self.chapter], lambda *_: None,
                reexecute=True, selections={self.chapter: [{"page": self.page,
                    "id": "approved-art", "expected_sha256": self._selection()[0]["expected_sha256"]}]})
        self.assertEqual(result[0]["status"], "processed", result)
        final_record, final_image, _ = read_final_page(self.manga, self.chapter, self.page)
        self.assertEqual(final_record["origin"], "PINCEL_ARTISTICO")
        self.assertEqual(cv2.imread(str(final_image), cv2.IMREAD_UNCHANGED).shape[2], 4)
        final_pixels = cv2.imread(str(final_image), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(final_pixels[2, 2], cv2.imread(str(self.source), cv2.IMREAD_UNCHANGED)[2, 2])
        np.testing.assert_array_equal(final_pixels[2, 3], (100, 110, 120, 255))
        manifest = json.loads((self.art / "json" / MANIFEST).read_text())
        record = manifest["pages"][self.page]
        self.assertEqual(record["input"]["sha256"], sha256(self.source))
        self.assertEqual(sha256(self.art / record["technical_output"]["artifact"],),
                         record["technical_output"]["sha256"])
        special = json.loads(self.special.read_text())["treatments"]
        artistic = special["estilizado"][0]
        self.assertEqual((artistic["id"], artistic["tipo"], artistic["box_pixels"]),
                         ("approved-art", "balao_estilizado",
                          {"x": 2, "y": 2, "width": 4, "height": 4}))
        self.assertEqual((special["degrade"][0]["id"], special["degrade"][0]["tipo"],
                          special["degrade"][0]["box_pixels"], special["degrade"][0]["result"]),
                         ("approved-degrade", "residuo_degrade",
                          {"x": 8, "y": 8, "width": 4, "height": 4}, {"kept": True}))

    def test_missing_output_and_divergent_hash_block_before_publication(self):
        validate_styled_reexecution(self.manga, "comix", [self.chapter], self._selection())
        output = self.art / "clean/page-001_artistico.png"
        original = output.read_bytes()
        output.unlink()
        chapter = query_special_treatments(self.manga, "comix", "estilizado")["chapters"][0]
        self.assertTrue(chapter["reexecution_blocked"])
        self.assertIn("Resultado Artístico anterior ausente", chapter["reexecution_block_reason"])
        with self.assertRaisesRegex(ValueError, "Resultado Artístico anterior ausente"):
            validate_styled_reexecution(self.manga, "comix", [self.chapter], self._selection())
        output.write_bytes(original)
        prior = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
        prior[0, 0] = (1, 2, 3, 255)
        self._image(output, prior)
        with self.assertRaisesRegex(ValueError, "Resultado Artístico anterior ausente ou com hash divergente"):
            validate_styled_reexecution(self.manga, "comix", [self.chapter], self._selection())
        self.assertFalse((self.manga / ".central_v2_special_transactions").exists())

    def test_legacy_without_occurrence_authorship_and_stale_sha_block(self):
        art_path = self.art / "json" / MANIFEST
        payload = json.loads(art_path.read_text())
        payload["pages"][self.page].pop("occurrences")
        art_path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "Autoria histórica Artístico insuficiente"):
            validate_styled_reexecution(self.manga, "comix", [self.chapter], self._selection())
        self.assertFalse((self.manga / ".central_v2_special_transactions").exists())
        payload["pages"][self.page]["occurrences"] = {
            "approved-art": {"roi": {"x": 2, "y": 2, "width": 4, "height": 4},
                "run_id": "oldrun", "status": "verified", "input_sha256": sha256(self.source),
                "technical_sha256": sha256(self.art / "authorship/oldrun/technical.png"),
                "technical_output": {"artifact": "authorship/oldrun/technical.png",
                    "sha256": sha256(self.art / "authorship/oldrun/technical.png")},
                "write_mask": {"artifact": "authorship/oldrun/approved-write.png",
                               "sha256": sha256(self.art / "authorship/oldrun/approved-write.png")},
                "changed_mask": {"artifact": "authorship/oldrun/approved-changed.png",
                                 "sha256": sha256(self.art / "authorship/oldrun/approved-changed.png")}}}
        art_path.write_text(json.dumps(payload))
        stale = self._selection()
        stale[0]["expected_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "SHA do Consolidado alterado"):
            validate_styled_reexecution(self.manga, "comix", [self.chapter], stale)

    def test_worker_failure_keeps_prior_occurrence_and_artifacts_intact(self):
        final_before = (self.final / self.page).read_bytes()
        final_manifest_before = self.final_manifest.read_bytes()
        special_before = self.special.read_bytes()
        art_before = (self.art / "json" / MANIFEST).read_bytes()
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.preview",
                   return_value={"execution_status": "failed", "error": "worker stopped"}):
            result = execute_styled(self.manga, "comix", [self.chapter], lambda *_: None,
                reexecute=True, selections={self.chapter: [{"page": self.page,
                    "id": "approved-art", "expected_sha256": self._selection()[0]["expected_sha256"]}]})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual((self.final / self.page).read_bytes(), final_before)
        self.assertEqual(self.final_manifest.read_bytes(), final_manifest_before)
        self.assertEqual(self.special.read_bytes(), special_before)
        self.assertEqual((self.art / "json" / MANIFEST).read_bytes(), art_before)
        self.assertEqual(json.loads(special_before)["treatments"]["estilizado"][0]["status"],
                         "processed")

    def test_sha_change_just_before_publication_blocks_transaction(self):
        original_page = (self.final / self.page).read_bytes()
        special_before = self.special.read_bytes()
        art_before = (self.art / "json" / MANIFEST).read_bytes()
        staging = self.root / "staging"

        def concurrent_change(_manga, _folder, _entries, validate):
            changed = cv2.imread(str(self.final / self.page), cv2.IMREAD_UNCHANGED)
            changed[0, 0] = (1, 2, 3, 255)
            self._image(self.final / self.page, changed)
            try:
                validate()
            finally:
                (self.final / self.page).write_bytes(original_page)

        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_output.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.preview",
                   side_effect=lambda *_args, **_kwargs: self._preview(staging)), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.publish",
                   side_effect=concurrent_change):
            result = execute_styled(self.manga, "comix", [self.chapter], lambda *_: None,
                reexecute=True, selections={self.chapter: [{"page": self.page,
                    "id": "approved-art", "expected_sha256": sha256(self.final / self.page)}]})
        self.assertEqual(result[0]["status"], "failed", result)
        self.assertIn("Snapshot ou artefato Artístico mudou", result[0]["error"])
        self.assertEqual((self.final / self.page).read_bytes(), original_page)
        self.assertEqual(self.special.read_bytes(), special_before)
        self.assertEqual((self.art / "json" / MANIFEST).read_bytes(), art_before)

    def test_plan_only_marks_selected_occurrence_pending(self):
        payload = json.loads(self.special.read_text())
        other = dict(payload["treatments"]["estilizado"][0])
        other["id"] = "other-art"
        other["check_decision"] = {"id": "other-art", "page": self.page}
        other["box_pixels"] = {"x": 10, "y": 2, "width": 4, "height": 4}
        other["result"] = {"run_id": "untouched"}
        payload["treatments"]["estilizado"].append(other)
        self.special.write_text(json.dumps(payload))
        check = json.loads(self.check.read_text())
        approved = dict(check["approved_occurrences"][0])
        approved["id"] = "other-art"
        approved["box_pixels"] = other["box_pixels"]
        check["approved_occurrences"].append(approved)
        self.check.write_text(json.dumps(check))
        plan = build_plan(self.manga, "comix", self.chapter, [
            {"page": self.page, "id": "approved-art"}])
        rows = {row["id"]: row for row in plan["payload"]["treatments"]["estilizado"]}
        self.assertEqual(rows["approved-art"]["status"], "pending")
        self.assertEqual(rows["other-art"]["status"], "processed")
        self.assertEqual(rows["other-art"]["result"], {"run_id": "untouched"})

    def test_three_balloons_reexecute_only_b_and_repeat_from_original(self):
        extra = [("A", 8, (40, 50, 60, 255)), ("C", 12, (80, 90, 100, 255))]
        check = json.loads(self.check.read_text())
        special = json.loads(self.special.read_text())
        art_path = self.art / "json" / MANIFEST
        art = json.loads(art_path.read_text())
        record = art["pages"][self.page]
        old = cv2.imread(str(self.source), cv2.IMREAD_UNCHANGED)
        old[2, 2] = (70, 80, 90, 255)
        for identity, x, color in extra:
            decision = dict(check["approved_occurrences"][0])
            decision.update(id=identity, box_pixels={"x": x, "y": 2, "width": 2, "height": 2})
            check["approved_occurrences"].append(decision)
            row = dict(special["treatments"]["estilizado"][0])
            row.update(id=identity, box_pixels=decision["box_pixels"],
                       check_decision={"id": identity, "page": self.page},
                       result={"run_id": f"old-{identity}"})
            special["treatments"]["estilizado"].append(row)
            write = np.zeros((16, 16), dtype=np.uint8)
            write[2:4, x:x + 2] = 255
            changed = np.zeros_like(write)
            changed[2, x] = 255
            refs = {}
            for kind, mask in (("write", write), ("changed", changed)):
                path = self._image(self.art / f"authorship/oldrun/{identity}-{kind}.png", mask)
                refs[f"{kind}_mask"] = {"artifact": str(path.relative_to(self.art)),
                                        "sha256": sha256(path)}
            record["occurrences"][identity] = {"roi": decision["box_pixels"],
                "run_id": "oldrun", "status": "verified", "input_sha256": sha256(self.source),
                "technical_sha256": sha256(self.art / "authorship/oldrun/technical.png"),
                "technical_output": {"artifact": "authorship/oldrun/technical.png",
                    "sha256": sha256(self.art / "authorship/oldrun/technical.png")}, **refs}
            record["occurrence_ids"].append(identity)
            record["rois"].append(decision["box_pixels"])
            old[2, x] = color
        self.check.write_text(json.dumps(check))
        special["source_check"]["sha256"] = sha256(self.check)
        self.special.write_text(json.dumps(special))
        self._image(self.art / record["output"]["artifact"], old)
        self._image(self.art / "authorship/oldrun/technical.png", old)
        record["output"]["sha256"] = sha256(self.art / record["output"]["artifact"])
        for proof in record["occurrences"].values():
            proof["technical_sha256"] = sha256(self.art / "authorship/oldrun/technical.png")
            proof["technical_output"]["sha256"] = proof["technical_sha256"]
        art_path.write_text(json.dumps(art))
        self._image(self.final / self.page, old)
        final_payload = json.loads(self.final_manifest.read_text())
        final_payload["pages"][self.page]["sha256"] = sha256(self.final / self.page)
        write_manifest(self.final, final_payload)
        before_special = {row["id"]: row for row in special["treatments"]["estilizado"]}
        before_proofs = {identity: record["occurrences"][identity] for identity in ("A", "C")}
        staging = self.root / "staging"
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_output.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.preview",
                   side_effect=lambda *_args, **_kwargs: self._preview(staging)):
            first = execute_styled(self.manga, "comix", [self.chapter], lambda *_: None,
                reexecute=True, selections={self.chapter: [{"page": self.page,
                    "id": "approved-art", "expected_sha256": sha256(self.final / self.page)}]})
        self.assertEqual(first[0]["status"], "processed", first)
        actual = cv2.imread(str(self.final / self.page), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(actual[2, 2], cv2.imread(str(self.source), cv2.IMREAD_UNCHANGED)[2, 2])
        for identity, x, color in extra:
            np.testing.assert_array_equal(actual[2, x], color)
        updated = json.loads(self.special.read_text())["treatments"]["estilizado"]
        for row in updated:
            if row["id"] in {"A", "C"}:
                self.assertEqual(row, before_special[row["id"]])
        after_art = json.loads(art_path.read_text())["pages"][self.page]
        for identity in ("A", "C"):
            self.assertEqual(after_art["occurrences"][identity], before_proofs[identity])
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_output.STAGING_ROOT", staging), \
             patch("central_v2.backend.orchestration.textoff_merged.special_styled_reexecution.preview",
                   side_effect=lambda *_args, **_kwargs: self._preview(staging, "thirdrun", (9, 8, 7, 255))):
            second = execute_styled(self.manga, "comix", [self.chapter], lambda *_: None,
                reexecute=True, selections={self.chapter: [{"page": self.page,
                    "id": "approved-art", "expected_sha256": sha256(self.final / self.page)}]})
        self.assertEqual(second[0]["status"], "processed", second)
        actual = cv2.imread(str(self.final / self.page), cv2.IMREAD_UNCHANGED)
        np.testing.assert_array_equal(actual[2, 3], (9, 8, 7, 255))
        np.testing.assert_array_equal(actual[2, 2], cv2.imread(str(self.source), cv2.IMREAD_UNCHANGED)[2, 2])


if __name__ == "__main__":
    unittest.main()
