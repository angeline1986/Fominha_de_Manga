"""Review proposals bind a verified Laboratory PNG to one final page."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from central_v2.backend.orchestration.textoff_merged import laboratorio_final_candidate
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.routes.router import dispatch_get, dispatch_post


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manga = self.root / "ridi" / "obra"
        self.source = self.manga / "IMG" / "1" / "page.png"
        self.source.parent.mkdir(parents=True)
        Image.new("RGB", (20, 30), "white").save(self.source)
        self.final_path = final_manifest_path(self.manga, "1")
        self.final_path.parent.mkdir(parents=True)
        self.final_image = self.final_path.parent.parent / "page.png"
        Image.new("RGB", (20, 30), "blue").save(self.final_image)
        self.write_final()
        self.staging = self.root / "staging"
        change = patch.object(laboratorio_final_candidate, "STAGING", self.staging)
        change.start()
        self.addCleanup(change.stop)
        self.run_id = "a" * 32
        self.payload = {"provider": "ridi", "manga": "obra", "chapter": "1",
                        "page": "page.png", "treatment": "degrade", "run_id": self.run_id}
        self.make_run()

    def write_final(self):
        self.final_path.write_text(json.dumps({
            "schema": "textoff_consolidado_final_manifest_v1", "version": 1,
            "provider": "ridi", "manga": "obra", "chapter": "1",
            "source_intermediate_manifest_sha256": "baseline",
            "pages": {"page.png": {"page": "page.png", "artifact": "page.png",
                                    "sha256": digest(self.final_image), "origin": "PINCEL_SUAVE"}},
            "history": []}), encoding="utf-8")

    def make_run(self, *, size=(20, 30), treatment="degrade"):
        folder = self.staging / self.run_id
        (folder / "input").mkdir(parents=True, exist_ok=True)
        (folder / "input/source.png").write_bytes(self.source.read_bytes())
        result = folder / "result.png"
        Image.new("RGB", size, "green").save(result)
        source = {"path": str(self.source), "sha256": digest(self.source),
                  "level": "LAB", "chapter": "1", "filename": "page.png",
                  "manga": str(self.manga.resolve()), "predecessors": []}
        request = {"run_id": self.run_id, "treatment": treatment, "source": source}
        manifest = {**request, "treatment": {"algorithm": treatment_for(treatment).algorithm},
                    "execution_status": "succeeded",
                    "result_file": "result.png", "validation": {"result_sha256": digest(result)},
                    "visual_review_status": "pending", "promotion_allowed": False}
        (folder / "request.json").write_text(json.dumps(request), encoding="utf-8")
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return folder

    def proposal(self, **changes):
        return dispatch_post("/api/textoff/laboratorio/final/proposal",
                             {**self.payload, **changes}, self.root)

    def test_proposal_and_versioned_images_do_not_change_final(self):
        before_image, before_manifest = self.final_image.read_bytes(), self.final_path.read_bytes()
        response = self.proposal()
        self.assertEqual(response.status, 200)
        reviewed = json.loads(response.body)
        self.assertEqual((reviewed["width"], reviewed["height"]), (20, 30))
        self.assertEqual(reviewed["current_origin"], "PINCEL_SUAVE")
        self.assertEqual(dispatch_get(reviewed["current_image_url"], self.root).body, before_image)
        self.assertEqual(dispatch_get(reviewed["candidate_image_url"], self.root).body,
                         (self.staging / self.run_id / "result.png").read_bytes())
        self.assertEqual((self.final_image.read_bytes(), self.final_path.read_bytes()),
                         (before_image, before_manifest))

    def test_stale_review_refuses_both_images(self):
        reviewed = json.loads(self.proposal().body)
        Image.new("RGB", (20, 30), "red").save(self.final_image)
        self.write_final()
        self.assertEqual(dispatch_get(reviewed["current_image_url"], self.root).status, 404)
        self.assertEqual(dispatch_get(reviewed["candidate_image_url"], self.root).status, 404)

    def test_manifest_only_change_also_invalidates_review(self):
        reviewed = json.loads(self.proposal().body)
        manifest = json.loads(self.final_path.read_text())
        manifest["updated_at"] = "nova revisão"
        self.final_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(dispatch_get(reviewed["candidate_image_url"], self.root).status, 404)

    def test_artistic_and_smooth_results_use_same_review_contract(self):
        for treatment in ("estilizado", "gradiente_suave"):
            with self.subTest(treatment=treatment):
                self.make_run(treatment=treatment)
                response = self.proposal(treatment=treatment)
                self.assertEqual(response.status, 200)

    def test_glass_clean_file_resolves_its_official_final_page(self):
        clean = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
                 / "05_AUTO_CLEANER_TRANSPARENCIA/BASICA/1/clean/page_clean.png")
        clean.parent.mkdir(parents=True)
        clean.write_bytes(self.source.read_bytes())
        run = self.make_run(treatment="estilizado")
        request_path = run / "request.json"
        manifest_path = run / "manifest.json"
        request = json.loads(request_path.read_text())
        request["source"].update({"path": str(clean), "sha256": digest(clean),
                                  "chapter": "clean", "filename": "page_clean.png"})
        manifest = json.loads(manifest_path.read_text())
        manifest["source"] = request["source"]
        request_path.write_text(json.dumps(request), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        payload = {"chapter": "clean", "page": "page_clean.png", "treatment": "estilizado"}
        response = self.proposal(**payload)
        self.assertEqual(response.status, 200)
        reviewed = json.loads(response.body)
        self.assertEqual((reviewed["chapter"], reviewed["page"]), ("1", "page.png"))
        self.assertEqual(dispatch_get(reviewed["current_image_url"], self.root).status, 200)
        self.assertEqual(dispatch_get(reviewed["candidate_image_url"], self.root).status, 200)
        self.assertEqual(self.proposal(chapter="2", **{k: v for k, v in payload.items()
                                                     if k != "chapter"}).status, 400)
        applied = dispatch_post("/api/textoff/laboratorio/final/apply", {
            **self.payload, **payload, "chapter": reviewed["chapter"],
            "page": reviewed["page"], "version": reviewed["version"],
            "confirmed": True}, self.root)
        self.assertEqual(applied.status, 200, applied.body)
        self.assertEqual(digest(self.final_image), reviewed["candidate_sha256"])

    def test_rejects_wrong_page_tampering_and_dimensions(self):
        self.assertEqual(self.proposal(page="other.png").status, 400)
        result = self.staging / self.run_id / "result.png"
        result.write_bytes(b"tampered")
        self.assertEqual(self.proposal().status, 400)
        self.make_run(size=(21, 30))
        self.assertEqual(self.proposal().status, 400)

    def test_rejects_manifest_with_another_treatment_algorithm(self):
        folder = self.make_run()
        path = folder / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["treatment"]["algorithm"] = treatment_for("estilizado").algorithm
        path.write_text(json.dumps(manifest))
        self.assertEqual(self.proposal().status, 400)

    def test_rejects_foreign_run_and_invalid_request(self):
        self.assertEqual(self.proposal(run_id="../" + self.run_id).status, 400)
        folder = self.make_run()
        request_path = folder / "request.json"
        request = json.loads(request_path.read_text())
        request["source"]["manga"] = str(self.root / "ridi" / "outra")
        request_path.write_text(json.dumps(request), encoding="utf-8")
        self.assertEqual(self.proposal().status, 400)
        self.assertEqual(self.proposal(unexpected=True).status, 400)

    def test_solid_preview_is_supported_with_its_own_manifest(self):
        folder = self.root / "_laboratorio_solidos_previews" / self.run_id
        folder.mkdir(parents=True)
        image = folder / "preview.png"
        Image.new("RGB", (20, 30), "yellow").save(image)
        (folder / "manifest.json").write_text(json.dumps({
            "schema": "laboratorio_solidos_preview_v1", "preview_only": True,
            "provider": "ridi", "manga": "obra", "chapter": "1", "page": "page.png",
            "source_sha256": digest(self.source), "preview_sha256": digest(image)}), encoding="utf-8")
        response = self.proposal(treatment="solidos")
        self.assertEqual(response.status, 200)
        reviewed = json.loads(response.body)
        self.assertEqual(dispatch_get(reviewed["candidate_image_url"], self.root).body,
                         image.read_bytes())


if __name__ == "__main__":
    unittest.main()
