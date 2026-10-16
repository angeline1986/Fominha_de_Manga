"""Request-local reuse must not hide changed manifests or stage authority."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration, manifests, stages


class QuerySnapshotTests(unittest.TestCase):
    def test_manifest_bytes_are_reused_and_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clean-manifest.json"
            path.write_text('{"value":1}', encoding="utf-8")
            with self.assertRaisesRegex(OSError, "Manifest alterado"):
                with manifests.manifest_snapshot():
                    first = manifests._read_document(path)
                    path.write_text('{"value":2}', encoding="utf-8")
                    self.assertEqual(manifests._read_document(path), first)
            with manifests.manifest_snapshot():
                self.assertEqual(manifests._read_document(path), b'{"value":2}')

    def test_registry_authority_is_reused_and_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text('{"stages":[]}', encoding="utf-8")
            with patch.object(artifact_migration, "REGISTRY_PATH", path):
                with self.assertRaisesRegex(OSError, "Registry.*alterado"):
                    with artifact_migration.registry_snapshot():
                        first = artifact_migration._read_registry(path)
                        path.write_text('{"stages":[{"stage_id":"new"}]}', encoding="utf-8")
                        self.assertIs(artifact_migration._read_registry(path), first)
                self.assertEqual(len(artifact_migration._read_registry(path)["stages"]), 1)

    def test_new_manifest_during_query_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "later.json"
            with self.assertRaisesRegex(OSError, "Manifest alterado"):
                with manifests.manifest_snapshot():
                    with self.assertRaises(FileNotFoundError):
                        manifests._read_document(path)
                    path.write_text("{}", encoding="utf-8")
                    with self.assertRaises(FileNotFoundError):
                        manifests._read_document(path)

    def test_stage_path_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manga = Path(directory) / "manga"
            with self.assertRaisesRegex(OSError, "Caminho de estágio alterado"):
                with stages.stage_path_snapshot():
                    path = stages.stage_chapter(manga, stages.LEVEL1, "1", read_legacy=False)
                    self.assertEqual(stages.stage_chapter(
                        manga, stages.LEVEL1, "1", read_legacy=False), path)
                    path.mkdir(parents=True)


if __name__ == "__main__":
    unittest.main()
