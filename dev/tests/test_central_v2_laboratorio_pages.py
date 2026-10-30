"""Laboratory page listing preserves image and symlink boundaries."""
import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from central_v2.backend.routes.router import dispatch_get
from central_v2.backend.routes.laboratorio_source import resolve_source
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA, manifest_path,
)
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL2, stage_root


class LaboratorioPagesTests(unittest.TestCase):
    def test_check_lists_only_saved_other_with_verified_review_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manga = output / "ridi" / "obra"
            (manga / "IMG" / "1").mkdir(parents=True)
            path = manifest_path(manga, "1")
            images = path.parent / "images"
            images.mkdir(parents=True)
            snapshots = {}
            for name in ("page-001.png", "page-002.png"):
                data = name.encode()
                (images / name).write_bytes(data)
                snapshots[name] = {"file": f"images/{name}",
                    "sha256": hashlib.sha256(data).hexdigest()}
            path.write_text(json.dumps({"schema": SCHEMA, "version": 1,
                "provider": "ridi", "manga": "obra", "chapter": "1",
                "source_snapshot": {}, "image_snapshot": snapshots,
                "approved_occurrences": [
                    {"page": "page-001.png", "tipo": "balao_transparente"},
                    {"page": "page-002.png", "tipo": "outro"},
                    {"page": "page-002.png", "tipo": "outro"}]}))
            query = "/api/textoff/laboratorio/pages?provider=ridi&manga=obra&source=check"
            listed = dispatch_get(query, output)
            image = dispatch_get(query.replace("/pages?", "/pages/image?")
                + "&chapter=1&page=page-002.png", output)
            resolved = resolve_source({"provider": "ridi", "manga": "obra",
                "source": "check", "chapter": "1", "page": "page-002.png"}, output)
            (images / "page-002.png").write_bytes(b"changed")
            changed = dispatch_get(query.replace("/pages?", "/pages/image?")
                + "&chapter=1&page=page-002.png", output)
        self.assertEqual(listed.status, 200)
        self.assertEqual([row["name"] for row in json.loads(listed.body)
            ["chapters"]["1"]], ["page-002.png"])
        self.assertEqual(image.status, 200)
        self.assertEqual(image.body, b"page-002.png")
        self.assertEqual(resolved[1].name, "page-002.png")
        self.assertEqual(changed.status, 404)

    def test_glass_lists_only_check_other_with_existing_clean_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manga = output / "ridi" / "obra"
            (manga / "IMG" / "1").mkdir(parents=True)
            clean = stage_root(manga, LEVEL2, read_legacy=False) / "1" / "clean"
            clean.mkdir(parents=True)
            for name in ("page-001_clean.png", "page-002_clean.png"):
                (clean / name).write_bytes(name.encode())
            path = manifest_path(manga, "1")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"schema": SCHEMA, "version": 1,
                "provider": "ridi", "manga": "obra", "chapter": "1",
                "source_snapshot": {}, "approved_occurrences": [
                    {"page": "page-002.png", "tipo": "outro"}]}))
            listed = dispatch_get("/api/textoff/laboratorio/pages?provider=ridi"
                "&manga=obra&source=glass", output)
            image = dispatch_get("/api/textoff/laboratorio/pages/image?provider=ridi"
                "&manga=obra&source=glass&chapter=1&page=page-002_clean.png", output)
            resolved = resolve_source({"provider": "ridi", "manga": "obra",
                "source": "glass", "chapter": "1", "page": "page-002_clean.png"}, output)
        self.assertEqual(listed.status, 200)
        self.assertEqual([row["name"] for row in json.loads(listed.body)
            ["chapters"]["1"]], ["page-002_clean.png"])
        self.assertEqual(image.body, b"page-002_clean.png")
        self.assertEqual(resolved[1].name, "page-002_clean.png")

    def test_merge_listing_contains_only_pages_saved_as_other_in_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manga = output / "ridi" / "obra"
            (manga / "IMG" / "1").mkdir(parents=True)
            chapter = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "1"
            chapter.mkdir(parents=True)
            for name in ("page-001.png", "page-002.png", "page-003.png"):
                (chapter / name).write_bytes(b"image")
            path = manifest_path(manga, "1")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"schema": SCHEMA, "version": 1,
                "provider": "ridi", "manga": "obra", "chapter": "1",
                "source_snapshot": {}, "approved_occurrences": [
                    {"page": "page-002.png", "tipo": "outro"},
                    {"page": "page-002.png", "tipo": "outro"},
                    {"page": "page-003.png", "tipo": "texto_residual"}]}))
            filtered = dispatch_get("/api/textoff/laboratorio/pages?provider=ridi"
                "&manga=obra&source=merge&check_other=1", output)
            unfiltered = dispatch_get("/api/textoff/laboratorio/pages?provider=ridi"
                "&manga=obra&source=merge", output)
        self.assertEqual(filtered.status, 200)
        self.assertEqual([row["name"] for row in json.loads(filtered.body)
            ["chapters"]["1"]], ["page-002.png"])
        self.assertEqual(len(json.loads(unfiltered.body)["chapters"]["1"]), 3)

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
