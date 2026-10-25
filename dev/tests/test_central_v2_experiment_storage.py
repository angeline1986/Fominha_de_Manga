"""New experiments stay with their work; earlier global runs remain readable."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256, write_json
from central_v2.backend.orchestration.textoff_special import execution
from central_v2.backend.orchestration.textoff_special.run_paths import run_folder, staging_root
from central_v2.backend.routes import laboratorio_recovery, laboratorio_tratamentos, textoff_special


class ExperimentStorageTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name).resolve()
        self.manga = self.output / "comix" / "Example"
        source = self.manga / "IMG" / "1" / "page.png"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source")
        self.source = source
        self.legacy = self.output / "old-runs"

    def _run(self, root, run_id, treatment):
        folder = root / run_id
        folder.mkdir(parents=True)
        result = folder / "result.png"
        result.write_bytes(run_id.encode())
        source = {"manga": str(self.manga), "path": str(self.source),
                  "chapter": "1", "filename": "page.png",
                  "sha256": sha256(self.source)}
        write_json(folder / "request.json", {"run_id": run_id, "source": source,
                                            "treatment": treatment})
        write_json(folder / "manifest.json", {"run_id": run_id, "source": source,
            "execution_status": "succeeded", "result_file": "result.png",
            "validation": {"result_sha256": sha256(result)}})
        return result

    def test_default_preview_writes_under_the_work(self):
        payload = {"treatment": "degrade", "level": "LAB", "chapter": "1",
                   "filename": "page.png", "expected_sha256": sha256(self.source),
                   "selections": [{"x": 1, "y": 1, "width": 2, "height": 2}]}
        source = {"path": str(self.source), "sha256": sha256(self.source),
                  "manga": str(self.manga), "level": "LAB", "chapter": "1",
                  "filename": "page.png", "predecessors": []}

        def worker(_key, request, _log):
            folder = request.parent
            result = folder / "result.png"
            result.write_bytes(b"new")
            write_json(folder / "worker-result.json", {
                "result_file": "result.png", "validation": {"result_sha256": sha256(result)}})

        with patch.object(execution, "python_for", return_value=Path("python")), \
             patch.object(execution, "run_worker", side_effect=worker):
            manifest = execution.preview(self.manga, payload, resolved_source=source)
        root = staging_root(self.manga, "textoff_especiais_v2")
        self.assertEqual(manifest["execution_status"], "succeeded")
        self.assertTrue((root / manifest["run_id"] / "manifest.json").is_file())

    def test_new_and_old_laboratory_images_remain_available(self):
        run_id = "a" * 32
        current = self._run(staging_root(self.manga, "textoff_laboratorio"), run_id,
                            "estilizado")
        legacy_id = "b" * 32
        old = self._run(self.legacy, legacy_id, "estilizado")
        with patch.object(laboratorio_tratamentos, "STAGING", self.legacy):
            query = {"run_id": [run_id], "provider": ["comix"], "manga": ["Example"]}
            self.assertEqual(laboratorio_tratamentos.result_image(
                query, output_root=self.output).body, current.read_bytes())
            self.assertEqual(laboratorio_tratamentos.result_image(
                {"run_id": [legacy_id]}, output_root=self.output).body, old.read_bytes())
            self.assertEqual(laboratorio_tratamentos.result_image(
                {**query, "manga": ["Other"]}, output_root=self.output).status, 404)

    def test_special_results_resolve_both_locations(self):
        run_id = "c" * 32
        current = self._run(staging_root(self.manga, "textoff_especiais_v2"), run_id,
                            "degrade")
        old_id = "d" * 32
        old = self._run(self.legacy, old_id, "degrade")
        with patch.object(textoff_special, "STAGING_ROOT", self.legacy):
            query = {"run_id": [run_id], "provider": ["comix"], "manga": ["Example"]}
            self.assertEqual(textoff_special.special_result_response(
                query, self.output).body, current.read_bytes())
            self.assertEqual(textoff_special.special_result_response(
                {"run_id": [old_id]}, self.output).body, old.read_bytes())
        self.assertEqual(run_folder(self.manga, "textoff_especiais_v2", old_id,
                                    legacy=self.legacy), old.parent)

    def test_recent_artistic_finds_new_run_and_returns_scoped_url(self):
        run_id = "e" * 32
        result = self._run(staging_root(self.manga, "textoff_laboratorio"), run_id,
                           "estilizado")
        Image.new("RGB", (4, 4), "blue").save(result)
        folder = result.parent
        snapshot = folder / "input" / "source.png"
        snapshot.parent.mkdir()
        snapshot.write_bytes(self.source.read_bytes())
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["validation"]["result_sha256"] = sha256(result)
        write_json(folder / "manifest.json", manifest)
        query = {key: [value] for key, value in {
            "provider": "comix", "manga": "Example", "chapter": "1",
            "page": "page.png", "source": "file", "path": "IMG/1/page.png"}.items()}
        response = laboratorio_recovery.recent_response(query, self.output)
        body = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertEqual(body["result"]["run_id"], run_id)
        self.assertIn("provider=comix", body["result"]["image_url"])
