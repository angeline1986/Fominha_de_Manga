import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from central_v2.backend.routes.static import static_response


class CentralV2StaticTests(unittest.TestCase):
    def test_root_resolves_index_html(self):
        with TemporaryDirectory() as tmp:
            frontend = Path(tmp)
            (frontend / "index.html").write_text(
                "<h1>Central V2</h1>",
                encoding="utf-8",
            )

            response = static_response("/", frontend)

            self.assertIsNotNone(response)
            self.assertEqual(
                response.body,
                b"<h1>Central V2</h1>",
            )
            self.assertEqual(
                response.content_type,
                "text/html",
            )

    def test_asset_preserves_detected_content_type(self):
        with TemporaryDirectory() as tmp:
            frontend = Path(tmp)
            asset = frontend / "_app" / "app.js"
            asset.parent.mkdir()
            asset.write_text(
                "console.log('v2');",
                encoding="utf-8",
            )

            response = static_response(
                "/_app/app.js",
                frontend,
            )

            self.assertIsNotNone(response)
            self.assertEqual(
                response.content_type,
                "text/javascript",
            )

    def test_path_escape_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            frontend = root / "frontend"
            frontend.mkdir()
            (root / "secret.txt").write_text(
                "secret",
                encoding="utf-8",
            )

            response = static_response(
                "/../secret.txt",
                frontend,
            )

            self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
