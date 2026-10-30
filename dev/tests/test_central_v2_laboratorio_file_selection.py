"""A selected work image can feed every Laboratory treatment safely."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.routes.laboratorio_degrade import _resolve as resolve_degrade
from central_v2.backend.routes.laboratorio_pages import response as pages_response
from central_v2.backend.routes.laboratorio_solidos import (
    execute as execute_solids, image_response as solid_image,
)
from central_v2.backend.routes.laboratorio_source import resolve_source
from central_v2.backend.routes.laboratorio_tratamentos import _execute as execute_treatment


class LaboratoryFileSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.work = self.output / "comix" / "obra"
        self.clean = self.work / "BASICA" / "10" / "clean" / "page-001.png"
        self.original = self.work / "IMG" / "1" / "original.png"
        self.merge = self.work / "FLUXO_SECUNDARIO" / "02_MERGE" / "1" / "merge.png"
        for path in (self.clean, self.original, self.merge):
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (30, 30), "white").save(path)
        self.payload = {"provider": "comix", "manga": "obra", "source": "file",
                        "chapter": "clean", "page": "page-001.png",
                        "path": "BASICA/10/clean/page-001.png",
                        "selections": [{"x": 1, "y": 1, "width": 15, "height": 15}]}

    def test_browser_image_is_selectable_by_the_treatments(self):
        listing = pages_response({"provider": ["comix"], "manga": ["obra"],
                                  "browse": ["1"], "path": ["BASICA/10/clean"]}, self.output)
        entries = json.loads(listing.body)["entries"]
        self.assertEqual(entries[0]["path"], self.payload["path"])
        preview = pages_response({"provider": ["comix"], "manga": ["obra"],
                                  "browse_image": ["1"], "path": [self.payload["path"]]},
                                 self.output, image=True)
        self.assertEqual(preview.status, 200)
        self.assertEqual(preview.body, self.clean.read_bytes())

        manga, source, request = resolve_degrade(self.payload, self.output)
        self.assertEqual(manga, self.work.resolve())
        self.assertEqual(source["path"], str(self.clean.resolve()))
        self.assertEqual(request["filename"], self.clean.name)
        captured = []

        def fake_preview(manga, request, **options):
            captured.append((manga, request, options["resolved_source"]))
            return {"execution_status": "succeeded", "run_id": "a" * 32}

        with patch("central_v2.backend.routes.laboratorio_tratamentos.preview", fake_preview):
            for treatment in ("estilizado", "gradiente_suave"):
                self.assertEqual(execute_treatment(self.payload, self.output, treatment).status, 200)
        self.assertEqual([row[1]["treatment"] for row in captured],
                         ["estilizado", "gradiente_suave"])
        self.assertTrue(all(row[2]["path"] == str(self.clean.resolve()) for row in captured))

        with patch("central_v2.backend.routes.laboratorio_solidos._filter",
                   return_value=(Image.new("RGB", (30, 30)),
                                 Image.new("L", (30, 30)), [])):
            solids = execute_solids(self.payload, self.output)
            self.assertEqual(solids.status, 200)
            body = json.loads(solids.body)
            run_id = body["run_id"]
            folder = self.work / "FLUXO_SECUNDARIO/05_Lab_Retoques/textoff_laboratorio" / run_id
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["source_path"], self.payload["path"])
            query = parse_qs(urlparse(body["image_url"]).query)
            self.assertEqual(query["provider"], ["comix"])
            self.assertEqual(query["manga"], ["obra"])
            self.assertEqual(solid_image(query, self.output).body,
                             (folder / "preview.png").read_bytes())
            self.assertEqual(solid_image({"run_id": [run_id]}, self.output).status, 404)
            self.assertFalse((self.output / "_laboratorio_solidos_previews" / run_id).exists())

    def test_legacy_solids_image_remains_readable_only_for_its_work(self):
        run_id = "b" * 32
        folder = self.output / "_laboratorio_solidos_previews" / run_id
        folder.mkdir(parents=True)
        preview = folder / "preview.png"
        Image.new("RGB", (30, 30), "white").save(preview)
        (folder / "manifest.json").write_text(json.dumps({
            "schema": "laboratorio_solidos_preview_v1", "preview_only": True,
            "provider": "comix", "manga": "obra",
            "preview_sha256": sha256(preview)}))
        self.assertEqual(solid_image({"run_id": [run_id]}, self.output).body,
                         preview.read_bytes())
        query = {"run_id": [run_id], "provider": ["comix"], "manga": ["obra"]}
        self.assertEqual(solid_image(query, self.output).body, preview.read_bytes())
        (self.output / "comix/other/IMG").mkdir(parents=True)
        self.assertEqual(solid_image({**query, "manga": ["other"]}, self.output).status, 404)

    def test_selected_path_cannot_escape_the_work(self):
        outside = self.output / "outside.png"
        Image.new("RGB", (30, 30)).save(outside)
        (self.clean.parent / "external.png").symlink_to(outside)
        for path, page in (("../outside.png", "outside.png"),
                           ("BASICA/10/clean/external.png", "external.png"),
                           ("BASICA/10/clean/../../IMG/1/original.png", "original.png")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                resolve_source({**self.payload, "path": path, "page": page}, self.output)

    def test_existing_img_and_merge_sources_remain_available(self):
        for kind, page in (("img", self.original), ("merge", self.merge)):
            with self.subTest(kind=kind):
                payload = {**self.payload, "source": kind, "chapter": "1", "page": page.name}
                self.assertEqual(resolve_source(payload, self.output)[1], page.resolve())


if __name__ == "__main__":
    unittest.main()
