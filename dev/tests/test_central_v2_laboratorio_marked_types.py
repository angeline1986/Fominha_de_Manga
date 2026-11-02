"""Laboratory exposes each treatment candidate marked in Auto-Cleaner Check."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from central_v2.backend.routes.router import dispatch_get
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA, manifest_path,
)
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL2, stage_root


class LaboratorioMarkedTypesTests(unittest.TestCase):
    def test_check_merge_and_glass_include_marked_treatments(self):
        kinds = ["outro", "residuo_degrade", "balao_estilizado",
                 "residuo_gradiente", "residuo_balao_solido_branco",
                 "balao_transparente", "texto_residual"]
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            manga = output / "ridi/obra"
            img = manga / "IMG/1"
            merge = manga / "FLUXO_SECUNDARIO/02_MERGE/1"
            glass = stage_root(manga, LEVEL2, read_legacy=False) / "1/clean"
            for folder in (img, merge, glass):
                folder.mkdir(parents=True)
            path = manifest_path(manga, "1")
            images = path.parent / "images"
            images.mkdir(parents=True)
            snapshots, occurrences = {}, []
            for index, kind in enumerate(kinds, 1):
                name = f"page-{index:03}.png"
                data = name.encode()
                (img / name).write_bytes(data)
                (merge / name).write_bytes(data)
                (glass / f"page-{index:03}_clean.png").write_bytes(data)
                (images / name).write_bytes(data)
                snapshots[name] = {"file": f"images/{name}",
                                   "sha256": hashlib.sha256(data).hexdigest()}
                occurrences.append({"page": name, "tipo": kind})
            path.write_text(json.dumps({"schema": SCHEMA, "version": 1,
                "provider": "ridi", "manga": "obra", "chapter": "1",
                "source_snapshot": {}, "image_snapshot": snapshots,
                "approved_occurrences": occurrences}))
            base = "/api/textoff/laboratorio/pages?provider=ridi&manga=obra&source="
            responses = {source: dispatch_get(base + source +
                ("&check_marked=1" if source == "merge" else ""), output)
                for source in ("check", "merge", "glass", "img")}
        for response in responses.values():
            self.assertEqual(response.status, 200, response.body)
        for source in ("check", "merge"):
            names = [row["name"] for row in json.loads(responses[source].body)["chapters"]["1"]]
            self.assertEqual(names, [f"page-{index:03}.png" for index in range(1, 6)])
        glass_names = [row["name"] for row in json.loads(responses["glass"].body)["chapters"]["1"]]
        self.assertEqual(glass_names, [f"page-{index:03}_clean.png" for index in range(1, 6)])
        self.assertEqual(len(json.loads(responses["img"].body)["chapters"]["1"]), 7)


if __name__ == "__main__":
    unittest.main()
