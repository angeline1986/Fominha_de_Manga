import tempfile
import unittest
from pathlib import Path
import subprocess
from unittest.mock import patch

from central_v2.backend.routes.auto_merge_folder import open_auto_merge_folder_response


class AutoMergeFolderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.manga = self.output / "comix" / "Obra"
        self.manga.mkdir(parents=True)

    def test_opens_only_existing_stage_folder(self):
        stage = self.manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / "6"
        stage.mkdir(parents=True)
        payload = {"provider": "comix", "manga": "Obra", "chapter": "6", "level": 2}

        with patch("central_v2.backend.routes.auto_merge_folder.subprocess.Popen") as launch:
            response = open_auto_merge_folder_response(payload, self.output)

        self.assertEqual(response.status, 200)
        launch.assert_called_once_with(["open", str(stage.resolve())], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)

    def test_opens_level3_stage_folder(self):
        stage = self.manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / "6"
        stage.mkdir(parents=True)
        payload = {"provider": "comix", "manga": "Obra", "chapter": "6", "level": 3}
        with patch("central_v2.backend.routes.auto_merge_folder.subprocess.Popen") as launch:
            response = open_auto_merge_folder_response(payload, self.output)
        self.assertEqual(response.status, 200)
        launch.assert_called_once_with(["open", str(stage.resolve())], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)

    def test_rejects_path_traversal_and_missing_stage(self):
        payload = {"provider": "comix", "manga": "Obra", "chapter": "../IMG", "level": 1}
        response = open_auto_merge_folder_response(payload, self.output)
        self.assertEqual(response.status, 400)


if __name__ == "__main__":
    unittest.main()
