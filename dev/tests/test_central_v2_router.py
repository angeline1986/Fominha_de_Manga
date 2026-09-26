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


if __name__ == "__main__":
    unittest.main()
