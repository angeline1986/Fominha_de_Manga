import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from central_v2.backend.routes.router import dispatch_get


class CentralV2RouterTests(unittest.TestCase):
    def test_catalog_dispatch_uses_isolated_output_root(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp)

            for manga in ("Obra 10", "Obra 2", "Obra 1"):
                (output / "comix" / manga / "IMG").mkdir(parents=True)

            (output / "mangago" / "Mangago Teste" / "IMG").mkdir(parents=True)
            (output / "mangago" / "Sem IMG").mkdir(parents=True)

            response = dispatch_get(
                "/api/catalog",
                output_root=output,
            )

            self.assertIsNotNone(response)
            self.assertEqual(response.status, 200)
            self.assertEqual(
                json.loads(response.body),
                {
                    "comix": ["Obra 1", "Obra 2", "Obra 10"],
                    "mangago": ["Mangago Teste"],
                    "ridi": [],
                },
            )

    def test_unknown_route_is_not_dispatched(self):
        self.assertIsNone(dispatch_get("/nao-existe"))


class CentralV2StateRouterTest(unittest.TestCase):
    def test_state_dispatch_returns_structural_state(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            chapter = output / "comix" / "Smoke Manga" / "IMG" / "1"
            chapter.mkdir(parents=True)
            (chapter / "page-001.png").write_bytes(b"x")

            response = dispatch_get(
                "/api/state?provider=comix&manga=Smoke%20Manga",
                output_root=output,
            )

            self.assertIsNotNone(response)
            self.assertEqual(response.status, 200)

            payload = json.loads(response.body)
            self.assertEqual(payload["provider"], "comix")
            self.assertEqual(payload["manga"], "Smoke Manga")
            self.assertEqual(payload["chapters"], ["1"])
            self.assertEqual(payload["summary"]["chapters"], 1)

    def test_state_dispatch_requires_provider_and_manga(self):
        response = dispatch_get("/api/state")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, 400)
        self.assertEqual(
            json.loads(response.body),
            {"error": "provider e manga são obrigatórios"},
        )

    def test_state_dispatch_rejects_invalid_provider(self):
        response = dispatch_get(
            "/api/state?provider=invalid&manga=Smoke%20Manga"
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.status, 400)
        self.assertEqual(
            json.loads(response.body),
            {"error": "Provider inválido."},
        )


if __name__ == "__main__":
    unittest.main()
