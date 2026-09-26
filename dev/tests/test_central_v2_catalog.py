import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from central_v2.backend.state.catalog import build_catalog


class CentralV2CatalogTests(unittest.TestCase):
    def test_build_catalog_preserves_current_contract(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp)

            # Ordem proposital para validar ordenação natural.
            for manga in ("Manga 10", "Manga 2", "Manga 1"):
                (output / "comix" / manga / "IMG").mkdir(parents=True)

            (output / "mangago" / "Outra Obra" / "IMG").mkdir(parents=True)

            # Diretório de obra sem IMG não pertence ao catálogo.
            (output / "mangago" / "Sem IMG").mkdir(parents=True)

            # ridi propositalmente ausente.

            catalog = build_catalog(output)

            self.assertEqual(
                catalog,
                {
                    "comix": ["Manga 1", "Manga 2", "Manga 10"],
                    "mangago": ["Outra Obra"],
                    "ridi": [],
                },
            )


if __name__ == "__main__":
    unittest.main()
