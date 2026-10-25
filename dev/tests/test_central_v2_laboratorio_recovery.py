"""A saved Artístico result is recoverable only for its unchanged source."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.routes import laboratorio_recovery as recovery


class RecoveryTests(unittest.TestCase):
    def test_recovers_verified_result_without_rerunning_and_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manga = root / "comix/obra"
            source_path = manga / "images/page.png"
            source_path.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), "white").save(source_path)
            run_id = "a" * 32
            folder = root / "staging" / run_id
            result = folder / "treatment/result.png"
            result.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), "blue").save(result)
            snapshot = folder / "input/source.png"
            snapshot.parent.mkdir()
            snapshot.write_bytes(source_path.read_bytes())
            source = {"path": str(source_path), "sha256": sha256(source_path),
                "manga": str(manga), "chapter": "images", "filename": "page.png"}
            (folder / "request.json").write_text(json.dumps({
                "run_id": run_id, "treatment": "estilizado", "source": source}))
            (folder / "manifest.json").write_text(json.dumps({
                "run_id": run_id, "source": source, "execution_status": "succeeded",
                "result_file": "treatment/result.png",
                "validation": {"result_sha256": sha256(result)}}))
            query = {key: [value] for key, value in {
                "provider": "comix", "manga": "obra", "chapter": "images",
                "page": "page.png", "source": "file", "path": "images/page.png"}.items()}
            with patch.object(recovery, "STAGING", root / "staging"), patch.object(
                    recovery, "resolve_source", return_value=(manga, source_path,
                    "images", "page.png")):
                found = recovery.recent_response(query, root)
                self.assertEqual(found.status, 200)
                self.assertEqual(json.loads(found.body)["result"]["run_id"], run_id)
                Image.new("RGB", (8, 8), "red").save(source_path)
                stale = recovery.recent_response(query, root)
                self.assertIsNone(json.loads(stale.body)["result"])

    def test_recovers_legacy_solids_preview_for_the_same_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manga = root / "comix/obra"
            source = manga / "clean/page_clean.png"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), "white").save(source)
            run_id = "b" * 32
            folder = root / "_laboratorio_solidos_previews" / run_id
            folder.mkdir(parents=True)
            preview = folder / "preview.png"
            Image.new("RGB", (8, 8), "green").save(preview)
            meta = {"schema": "laboratorio_solidos_preview_v1",
                "preview_only": True, "provider": "comix", "manga": "obra",
                "chapter": "clean", "page": "page_clean.png",
                "source_sha256": sha256(source), "preview_sha256": sha256(preview)}
            manifest = folder / "manifest.json"
            manifest.write_text(json.dumps(meta))
            query = {key: [value] for key, value in {
                "provider": "comix", "manga": "obra", "chapter": "clean",
                "page": "page_clean.png", "source": "file",
                "path": "clean/page_clean.png"}.items()}
            with patch.object(recovery, "STAGING", root / "empty"), patch.object(
                    recovery, "resolve_source", return_value=(manga, source,
                    "clean", "page_clean.png")):
                recovered = json.loads(recovery.recent_response(query, root).body)
                self.assertEqual(recovered["solids_result"]["run_id"], run_id)
                meta["source_path"] = "other/page_clean.png"
                manifest.write_text(json.dumps(meta))
                mismatched = json.loads(recovery.recent_response(query, root).body)
                self.assertIsNone(mismatched["solids_result"])


if __name__ == "__main__":
    unittest.main()
