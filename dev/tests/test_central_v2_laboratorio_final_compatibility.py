"""Laboratory restoration restores the active lineage used by Reset and Artístico."""
import json
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import (
    laboratorio_final_apply, laboratorio_final_candidate, laboratorio_final_history,
    laboratorio_final_restore, laboratorio_final_review, special_page_restore,
)
from central_v2.backend.orchestration.textoff_merged.final_active_lineage import active_page_rows
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.orchestration.textoff_merged.special_styled_final import prepare_final
from central_v2.backend.orchestration.textoff_merged.special_degrade_input import selected_input
from central_v2.backend.orchestration.textoff_merged.special_page_restore_check import restored_block_reason
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for
import test_special_page_restore as reset_fixture
import test_special_styled_recovery as recovery_fixture
import test_special_styled_initial_composition as composition_fixture
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import write_manifest
from central_v2.backend.orchestration.textoff_merged.special_styled_initial_composition import compose_initial
from central_v2.backend.orchestration.textoff_merged.special_styled_recovery import recover_from_final_history


class LaboratoryCompatibilityTests(unittest.TestCase):
    setUp = reset_fixture.PageRestoreTests.setUp
    _image = reset_fixture.PageRestoreTests._image
    _final = reset_fixture.PageRestoreTests._final

    def apply_and_restore(self):
        source = self.manga / "IMG" / self.chapter / self.page
        self._image(source, 5)
        staging = Path(self.temp.name) / "laboratory-staging"
        mocked = patch.object(laboratorio_final_candidate, "STAGING", staging)
        mocked.start()
        self.addCleanup(mocked.stop)
        run_id = "a" * 32
        folder = staging / run_id
        (folder / "input").mkdir(parents=True)
        (folder / "input/source.png").write_bytes(source.read_bytes())
        result = folder / "result.png"
        self._image(result, 80)
        input_row = {"path": str(source), "sha256": sha256(source), "level": "LAB",
                     "chapter": self.chapter, "filename": self.page,
                     "manga": str(self.manga.resolve())}
        request = {"run_id": run_id, "treatment": "degrade", "source": input_row}
        manifest = {**request, "treatment": {"algorithm": treatment_for("degrade").algorithm},
                    "execution_status": "succeeded", "result_file": "result.png",
                    "validation": {"result_sha256": sha256(result)}}
        (folder / "request.json").write_text(json.dumps(request))
        (folder / "manifest.json").write_text(json.dumps(manifest))
        identity = {"provider": "comix", "manga": "Example", "chapter": self.chapter,
                    "page": self.page, "treatment": "degrade", "run_id": run_id}
        original = (self.final / self.page).read_bytes()
        proposal = laboratorio_final_review.inspect(identity, Path(self.temp.name))
        laboratorio_final_apply.apply({**identity, "version": proposal["version"],
                                       "confirmed": True}, Path(self.temp.name))
        history_identity = {key: identity[key] for key in ("provider", "manga", "chapter", "page")}
        history = laboratorio_final_history.inspect(history_identity, Path(self.temp.name))
        self.assertEqual(history["current"]["origin"], "LABORATORIO")
        with self.assertRaisesRegex(ValueError, "Restaure a página do Laboratório"):
            selected_input(self.manga, self.chapter, self.page)
        self.assertIn("Restaure a página do Laboratório", restored_block_reason(
            self.manga, "comix", self.chapter, self.page))
        revision = next(row for row in history["revisions"] if row["sha256"] == self.degrade["sha256"])
        laboratorio_final_restore.restore({**history_identity, "version": history["version"],
            "revision_id": revision["revision_id"], "confirmed": True}, Path(self.temp.name))
        self.assertEqual((self.final / self.page).read_bytes(), original)
        return revision

    def test_reset_uses_restored_pincel_lineage(self):
        self.apply_and_restore()
        payload = json.loads(self.final_manifest.read_text())
        rows = active_page_rows(payload, self.page, self.final)
        self.assertEqual([row["origin"] for row in rows],
                         ["AUTO_CLEANER_TRANSPARENCIA", "PINCEL_ARTISTICO", "PINCEL_DEGRADE"])
        proposal = special_page_restore.inspect(self.manga, "comix", self.chapter, self.page)
        self.assertEqual(proposal["invalidated_runs"], 2)
        result = special_page_restore.restore(self.manga, "comix", self.chapter, self.page,
                                              proposal, confirmed=True)
        self.assertEqual(result["status"], "restored")
        self.assertEqual(sha256(self.final / self.page), sha256(self.source))
        after = json.loads(self.final_manifest.read_text())
        self.assertEqual([row["origin"] for row in active_page_rows(after, self.page, self.final)],
                         ["AUTO_CLEANER_TRANSPARENCIA"])

    def test_artistico_can_prepare_over_restored_pincel(self):
        self.apply_and_restore()
        art_stage = Path(self.temp.name) / "new-artistic"
        output = art_stage / "clean/result.png"
        self._image(output, 70)
        staged = Path(self.temp.name) / "new-final"
        source = {"page": self.page, "sha256": sha256(self.final / self.page),
                  "selected_from": "PINCEL_DEGRADE", "consolidated_manifest_sha256": "base"}
        record = {"output": {"artifact": "clean/result.png", "sha256": sha256(output)},
                  "run_id": "new-art", "status": "processed"}
        prepare_final(self.manga, self.chapter, [{"source": source}], {self.page: record},
                      art_stage, staged)
        next_manifest = json.loads((staged / "json/final-manifest.json").read_text())
        self.assertEqual(next_manifest["pages"][self.page]["origin"], "PINCEL_ARTISTICO")
        self.assertEqual([row["origin"] for row in active_page_rows(next_manifest, self.page, staged)],
                         ["AUTO_CLEANER_TRANSPARENCIA", "PINCEL_ARTISTICO",
                          "PINCEL_DEGRADE", "PINCEL_ARTISTICO"])

    def test_corrupt_archived_revision_blocks_lineage_dependent_reset(self):
        revision = self.apply_and_restore()
        archived = self.final / "history" / revision["sha256"] / self.page
        self._image(archived, 99)
        with self.assertRaisesRegex(ValueError, "Revisão restaurada sem PNG"):
            special_page_restore.inspect(self.manga, "comix", self.chapter, self.page)


class RestoredArtisticRecoveryTests(unittest.TestCase):
    setUp = recovery_fixture.StyledHistoryRecoveryTests.setUp
    _image = recovery_fixture.StyledHistoryRecoveryTests._image

    def test_recovers_the_restored_current_artistic_output(self):
        manifest_path = final_manifest_path(self.manga, self.chapter)
        final = manifest_path.parent.parent
        payload = json.loads(manifest_path.read_text())
        art = payload["history"][0]["superseded"]
        degrade = payload["pages"][self.page]
        archive = final / "history" / art["sha256"] / self.page
        archive.parent.mkdir(parents=True)
        archive.write_bytes(self.art_output.read_bytes())
        payload["history"][0].update(archived_artifact=archive.relative_to(final).as_posix(),
                                     archived_sha256=art["sha256"])
        lab = {"page": self.page, "artifact": self.page, "origin": "LABORATORIO",
               "sha256": "b" * 64}
        payload["history"].extend([
            {"page": self.page, "superseded": degrade, "reason": "laboratorio_apply"},
            {"page": self.page, "superseded": lab, "reason": "laboratorio_restore",
             "restored_revision_id": hashlib.sha256(f"0:{art['sha256']}".encode()).hexdigest()}])
        payload["pages"][self.page] = {**art, "restoration_id": "restore-art"}
        (final / self.page).write_bytes(self.art_output.read_bytes())
        write_manifest(final, payload)
        recovered = recover_from_final_history(self.manga, self.chapter, self.page)
        self.assertEqual(Path(recovered["prior_output"]).resolve(), (final / self.page).resolve())
        self.assertEqual(recovered["prior_output_sha256"], art["sha256"])


class RestoredInitialCompositionTests(unittest.TestCase):
    setUp = composition_fixture.InitialCompositionTests.setUp
    _save = composition_fixture.InitialCompositionTests._save

    def test_initial_artistico_ignores_abandoned_laboratory_branch(self):
        self._save(self.current, self.original)
        auto = {"page": self.page, "artifact": self.page,
                "sha256": sha256(self.current), "origin": "AUTO_CLEANER"}
        abandoned = {"sha256": "b" * 64, "origin": "LABORATORIO"}
        archive = self.final / "history" / auto["sha256"] / self.page
        archive.parent.mkdir(parents=True)
        archive.write_bytes(self.current.read_bytes())
        revision = hashlib.sha256(f"0:{auto['sha256']}".encode()).hexdigest()
        manifest = self.final / "json/final-manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"pages": {self.page: {**auto, "restoration_id": "r1"}},
            "history": [{"page": self.page, "superseded": auto,
                         "reason": "laboratorio_apply",
                         "archived_artifact": archive.relative_to(self.final).as_posix(),
                         "archived_sha256": auto["sha256"]},
                        {"page": self.page, "superseded": abandoned,
                         "reason": "laboratorio_restore", "restored_revision_id": revision}]}))
        result = compose_initial(self.manga, "1", self.page, self.detection, self.current,
                                 {**auto, "restoration_id": "r1"}, self.run,
                                 self.root / "composed-after-restore.png")
        self.assertEqual(result["downstream_write_pixels"], 0)


if __name__ == "__main__":
    unittest.main()
