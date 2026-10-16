"""Laboratory page listing preserves image and symlink boundaries."""
import json
from pathlib import Path
import tempfile
import unittest

from central_v2.backend.routes.router import dispatch_get


class LaboratorioPagesTests(unittest.TestCase):
    def test_listing_keeps_internal_images_and_rejects_external_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            chapter = output / "ridi" / "obra" / "IMG" / "1"
            chapter.mkdir(parents=True)
            (chapter / "page-001.png").write_bytes(b"image")
            (chapter / "page-002_old.png").write_bytes(b"old")
            (chapter / "notes.txt").write_text("not an image")
            (output / "ridi" / "obra" / "IMG" / "outside.png").write_bytes(b"outside")
            (chapter / "alias.jpg").symlink_to(chapter / "page-001.png")
            (chapter / "external.png").symlink_to(
                output / "ridi" / "obra" / "IMG" / "outside.png")

            listed = dispatch_get(
                "/api/textoff/laboratorio/pages?provider=ridi&manga=obra&source=img",
                output,
            )
            image = dispatch_get(
                "/api/textoff/laboratorio/pages/image?provider=ridi&manga=obra"
                "&chapter=1&page=page-001.png&source=img", output)
            escaped = dispatch_get(
                "/api/textoff/laboratorio/pages/image?provider=ridi&manga=obra"
                "&chapter=1&page=external.png&source=img", output)

        self.assertEqual(listed.status, 200)
        names = [row["name"] for row in json.loads(listed.body)["chapters"]["1"]]
        self.assertEqual(names, ["alias.jpg", "page-001.png"])
        self.assertEqual(image.status, 200)
        self.assertEqual(image.body, b"image")
        self.assertEqual(escaped.status, 404)


if __name__ == "__main__":
    unittest.main()
