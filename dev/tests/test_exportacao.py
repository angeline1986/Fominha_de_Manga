import tempfile
import unittest
from pathlib import Path

from processamento.exportacao import exportador


class ExportacaoTest(unittest.TestCase):
    def setUp(self):
        exportador._PLANS.clear()

    def manga(self, root):
        manga = root / "obra"
        final = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/1"
        pdf = manga / "FLUXO_SECUNDARIO/03_PDF_MERGE/1"
        final.mkdir(parents=True)
        pdf.mkdir(parents=True)
        (final / "page-001.png").write_bytes(b"image")
        (final / "page-001_mask.png").write_bytes(b"mask")
        (final / "page-001.txt").write_text("auxiliary")
        (final / "json").mkdir()
        (final / "json/final-manifest.json").write_text("{}")
        (final / ".DS_Store").write_bytes(b"x")
        (pdf / "1.pdf").write_bytes(b"pdf")
        return manga

    def test_exclusions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manga = self.manga(root)
            dest = root / "dest"
            dest.mkdir()
            plan = exportador.simulate_export(
                manga, str(dest), ["textoff_merged", "pdf_merge"]
            )
            self.assertEqual(plan["total_files"], 2)

    def test_preserves_extra_and_structure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manga = self.manga(root)
            dest = root / "dest"
            dest.mkdir()
            (dest / "keep.txt").write_text("keep")
            plan = exportador.simulate_export(
                manga, str(dest), ["textoff_merged", "pdf_merge"]
            )
            result = exportador.execute_plan(manga, plan["plan_id"])
            self.assertTrue((dest / "keep.txt").is_file())
            self.assertTrue((dest / "obra/raws_semi-clean/1/page-001.png").is_file())
            self.assertTrue((dest / "obra/Traducoes/1/1.pdf").is_file())
            self.assertEqual(result["copied"], 2)

    def test_source_change_invalidates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manga = self.manga(root)
            dest = root / "dest"
            dest.mkdir()
            plan = exportador.simulate_export(manga, str(dest), ["textoff_merged"])
            final = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/1"
            (final / "page-001.png").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "mudou desde a simulação"):
                exportador.execute_plan(manga, plan["plan_id"])

    def test_appledouble_excluded_in_simulation_and_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manga = self.manga(root)
            dest = root / "dest"
            dest.mkdir()
            pdf = manga / "FLUXO_SECUNDARIO/03_PDF_MERGE/1"
            final = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/1"
            for name in ("._1.pdf", "._1", "._.DS_Store"):
                (pdf / name).write_bytes(b"macos-metadata")
            (final / "._page-001.png").write_bytes(b"macos-metadata")
            plan = exportador.simulate_export(
                manga, str(dest), ["pdf_merge", "textoff_merged"]
            )
            self.assertEqual(plan["total_files"], 2)
            self.assertEqual(plan["new_files"], 2)
            self.assertIn("._*", plan["exclusions"])
            result = exportador.execute_plan(manga, plan["plan_id"])
            self.assertEqual(result["copied"], 2)
            self.assertFalse(any(p.name.startswith("._") for p in (dest / "obra").rglob("*")))

    def test_final_export_ignores_history_and_laboratory_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manga = self.manga(root)
            final = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/1"
            history = final / "history/old-hash"
            laboratory = final / "laboratorio/run-id"
            history.mkdir(parents=True)
            laboratory.mkdir(parents=True)
            (history / "page-001.png").write_bytes(b"old")
            (laboratory / "page-001.png").write_bytes(b"experimental")

            files = exportador.list_source_files(manga, "textoff_merged")["files"]
            self.assertEqual([row["path"] for row in files], ["1/page-001.png"])

            dest = root / "dest"
            dest.mkdir()
            plan = exportador.simulate_export(manga, str(dest), ["textoff_merged"])
            self.assertEqual(plan["total_files"], 1)
            result = exportador.execute_plan(manga, plan["plan_id"])
            self.assertEqual(result["copied"], 1)
            self.assertFalse((dest / "obra/raws_semi-clean/1/history").exists())
            self.assertFalse((dest / "obra/raws_semi-clean/1/laboratorio").exists())

    def test_cannot_select_archived_image_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manga = self.manga(root)
            final = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/1"
            history = final / "history/old-hash"
            history.mkdir(parents=True)
            (history / "page-001.png").write_bytes(b"old")
            dest = root / "dest"
            dest.mkdir()
            with self.assertRaisesRegex(ValueError, "indisponíveis"):
                exportador.simulate_export(
                    manga, str(dest), ["textoff_merged"],
                    {"textoff_merged": ["1/history/old-hash/page-001.png"]},
                )


if __name__ == "__main__":
    unittest.main()
