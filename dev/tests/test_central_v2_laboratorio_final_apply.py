"""Laboratory publication preserves prior bytes and rolls back on failure."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from central_v2.backend.orchestration.textoff_merged import (
    final_consolidated, laboratorio_final_apply, laboratorio_final_candidate,
)
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for
from central_v2.backend.orchestration.combo_turbo import publication_candidates
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import read_manifest
from central_v2.backend.orchestration.textoff_merged.special_styled_final import prepare_final
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter
from central_v2.backend.routes.router import dispatch_post
from processamento.exportacao.exportador import list_source_files


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LaboratoryApplyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manga = self.root / "ridi/obra"
        self.source = self.manga / "IMG/1/page.png"
        self.source.parent.mkdir(parents=True)
        Image.new("RGB", (20, 30), "white").save(self.source)
        self.manifest = final_manifest_path(self.manga, "1")
        self.manifest.parent.mkdir(parents=True)
        self.final = self.manifest.parent.parent / "page.png"
        self.other = self.manifest.parent.parent / "other.png"
        Image.new("RGB", (20, 30), "blue").save(self.final)
        Image.new("RGB", (20, 30), "black").save(self.other)
        self.write_manifest()
        self.staging = self.root / "staging"
        mocked = patch.object(laboratorio_final_candidate, "STAGING", self.staging)
        mocked.start()
        self.addCleanup(mocked.stop)
        self.run_id = "a" * 32
        self.identity = {"provider": "ridi", "manga": "obra", "chapter": "1",
                         "page": "page.png", "treatment": "degrade", "run_id": self.run_id}
        self.make_run("green")

    def write_manifest(self):
        rows = {name: {"page": name, "artifact": name, "sha256": sha(path),
                       "origin": "PINCEL_SUAVE"}
                for name, path in (("page.png", self.final), ("other.png", self.other))}
        self.manifest.write_text(json.dumps({
            "schema": "textoff_consolidado_final_manifest_v1", "version": 1,
            "provider": "ridi", "manga": "obra", "chapter": "1",
            "source_intermediate_manifest_sha256": "baseline", "page_count": 2,
            "pages": rows, "history": []}), encoding="utf-8")

    def make_run(self, color):
        folder = self.staging / self.run_id
        (folder / "input").mkdir(parents=True, exist_ok=True)
        (folder / "input/source.png").write_bytes(self.source.read_bytes())
        image = folder / "result.png"
        Image.new("RGB", (20, 30), color).save(image)
        source = {"path": str(self.source), "sha256": sha(self.source),
                  "level": "LAB", "chapter": "1", "filename": "page.png",
                  "manga": str(self.manga.resolve())}
        request = {"run_id": self.run_id, "treatment": "degrade", "source": source}
        manifest = {**request, "treatment": {"algorithm": treatment_for("degrade").algorithm},
                    "execution_status": "succeeded", "result_file": "result.png",
                    "validation": {"result_sha256": sha(image)},
                    "visual_review_status": "pending", "promotion_allowed": False}
        (folder / "request.json").write_text(json.dumps(request), encoding="utf-8")
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return image

    def proposal(self):
        response = dispatch_post("/api/textoff/laboratorio/final/proposal",
                                 self.identity, self.root)
        self.assertEqual(response.status, 200)
        return json.loads(response.body)

    def test_final_v1_contract_uses_root_png_and_verified_manifest_artifact(self):
        folder = self.manifest.parent.parent
        self.assertEqual(folder, self.manga /
            "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/1")
        payload = read_manifest(self.manifest, self.manga, "1")
        self.assertEqual((payload["schema"], payload["version"], payload["page_count"]),
            ("textoff_consolidado_final_manifest_v1", 1, 2))
        for page, row in payload["pages"].items():
            self.assertEqual(row["artifact"], page)
            self.assertEqual(row["sha256"], sha(folder / page))
        exported = list_source_files(self.manga, "textoff_merged")
        self.assertEqual([row["path"] for row in exported["files"]],
            ["1/other.png", "1/page.png"])
        self.final.write_bytes(b"alterado")
        with self.assertRaisesRegex(ValueError, "Página final inválida"):
            read_manifest(self.manifest, self.manga, "1")

    def apply(self, version, confirmed=True):
        return dispatch_post("/api/textoff/laboratorio/final/apply",
                             {**self.identity, "version": version, "confirmed": confirmed}, self.root)

    def test_applies_only_one_page_with_history_and_provenance(self):
        original, other = self.final.read_bytes(), self.other.read_bytes()
        reviewed = self.proposal()
        response = self.apply(reviewed["version"])
        self.assertEqual(response.status, 200, response.body)
        self.assertEqual(sha(self.final), reviewed["candidate_sha256"])
        self.assertEqual(self.other.read_bytes(), other)
        manifest = json.loads(self.manifest.read_text())
        row = manifest["pages"]["page.png"]
        self.assertEqual((row["origin"], row["treatment"], row["run_id"]),
                         ("LABORATORIO", "degrade", self.run_id))
        self.assertEqual(row["source_artifact"], "result.png")
        self.assertEqual(sha(self.manifest.parent.parent / row["laboratory_snapshot"]),
                         reviewed["candidate_sha256"])
        history = manifest["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual((self.manifest.parent.parent / history[0]["archived_artifact"]).read_bytes(),
                         original)
        self.assertEqual(history[0]["superseded"]["sha256"], reviewed["current_sha256"])
        duplicate = self.proposal()
        self.assertEqual(self.apply(duplicate["version"]).status, 400)
        self.assertEqual(len(json.loads(self.manifest.read_text())["history"]), 1)

    def test_repeat_correction_retains_both_prior_versions(self):
        first = self.proposal()
        self.assertEqual(self.apply(first["version"]).status, 200)
        self.run_id = "b" * 32
        self.identity["run_id"] = self.run_id
        self.make_run("red")
        second = self.proposal()
        self.assertEqual(self.apply(second["version"]).status, 200)
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(len(manifest["history"]), 2)
        self.assertEqual([item["archived_sha256"] for item in manifest["history"]],
                         [first["current_sha256"], first["candidate_sha256"]])
        for item in manifest["history"]:
            self.assertEqual(sha(self.manifest.parent.parent / item["archived_artifact"]),
                             item["archived_sha256"])

    def test_stale_review_and_missing_confirmation_do_not_write(self):
        reviewed = self.proposal()
        before = self.manifest.read_bytes()
        self.assertEqual(self.apply(reviewed["version"], confirmed=False).status, 400)
        Image.new("RGB", (20, 30), "yellow").save(self.final)
        self.write_manifest()
        current = self.manifest.read_bytes()
        self.assertEqual(self.apply(reviewed["version"]).status, 409)
        self.assertNotEqual(before, current)
        self.assertEqual(self.manifest.read_bytes(), current)

    def test_publish_failure_restores_original_chapter(self):
        reviewed = self.proposal()
        before_image, before_manifest = self.final.read_bytes(), self.manifest.read_bytes()
        verify = laboratorio_final_apply._verify
        def fail_after_swap(folder, manga, proposal, archive, snapshot):
            if folder.name == "1":
                raise ValueError("Falha simulada após troca")
            return verify(folder, manga, proposal, archive, snapshot)
        with patch.object(laboratorio_final_apply, "_verify", side_effect=fail_after_swap):
            response = self.apply(reviewed["version"])
        self.assertEqual(response.status, 400)
        self.assertEqual(self.final.read_bytes(), before_image)
        self.assertEqual(self.manifest.read_bytes(), before_manifest)
        self.assertFalse((self.manifest.parent.parent / "history").exists())

    def test_rebuild_and_combo_keep_laboratory_page(self):
        reviewed = self.proposal()
        self.assertEqual(self.apply(reviewed["version"]).status, 200)
        expected = self.final.read_bytes()
        intermediate = stage_chapter(self.manga, "TO_MERGED_CONSOLIDADO", "1")
        (intermediate / "json").mkdir(parents=True)
        selections = [{"source": name, "selected_from": LEVEL1,
                       "artifact": f"clean/{name}"} for name in ("page.png", "other.png")]
        logical = intermediate / "json/clean-manifest.json"
        logical.write_text(json.dumps({"selections": selections}), encoding="utf-8")
        with patch.object(final_consolidated, "consolidated_is_current", return_value=True):
            final_consolidated.rebuild_final_baseline(self.manga, "1")
        self.assertEqual(self.final.read_bytes(), expected)
        self.assertEqual(json.loads(self.manifest.read_text())["pages"]["page.png"]["origin"],
                         "LABORATORIO")
        combo_final = self.root / "combo-final"
        previous = json.loads(self.manifest.read_text())
        publication_candidates._write_final(self.manga, "1", self.root / "combo-stage",
                                            intermediate, {"selections": selections},
                                            combo_final, previous)
        self.assertEqual((combo_final / "page.png").read_bytes(), expected)
        self.assertEqual(json.loads((combo_final / "json/final-manifest.json").read_text())
                         ["pages"]["page.png"]["origin"], "LABORATORIO")

    def test_artistico_cannot_replace_laboratory_page_without_restoration(self):
        reviewed = self.proposal()
        self.assertEqual(self.apply(reviewed["version"]).status, 200)
        runs = [{"source": {"page": "page.png", "sha256": sha(self.final)}}]
        records = {"page.png": {"output": {"artifact": "clean/result.png"}}}
        with self.assertRaisesRegex(ValueError, "Restaure a página do Laboratório"):
            prepare_final(self.manga, "1", runs, records, self.root / "artistico",
                          self.root / "artistico-final")


if __name__ == "__main__":
    unittest.main()
