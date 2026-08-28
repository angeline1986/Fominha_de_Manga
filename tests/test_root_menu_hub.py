import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image


ROOT_MENU_PATH = Path(__file__).resolve().parents[1] / "menu.py"
SPEC = importlib.util.spec_from_file_location("root_menu", ROOT_MENU_PATH)
root_menu = importlib.util.module_from_spec(SPEC)
sys.modules["root_menu"] = root_menu
SPEC.loader.exec_module(root_menu)


def write_image(path: Path) -> None:
    Image.new("RGB", (4, 4), "white").save(path)


class RootMenuHubTests(unittest.TestCase):
    def test_resolves_project_root_dynamically(self):
        self.assertEqual(root_menu.resolve_root_dir(), Path(__file__).resolve().parents[1])

    def test_resolves_mangago_output_inside_module(self):
        expected = Path(__file__).resolve().parents[1] / "mangago_downloader" / "output"
        self.assertEqual(root_menu.resolve_mangago_output_dir(), expected)

    def test_menu_does_not_use_absolute_user_path(self):
        source = ROOT_MENU_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", source)

    def test_build_mangago_web_command_prefers_module_venv_entrypoint(self):
        command, cwd, env = root_menu.build_mangago_web_command()

        self.assertEqual(cwd, Path(__file__).resolve().parents[1] / "mangago_downloader")
        self.assertIn("MANGAGO_LOG_LEVEL", env)
        self.assertTrue(command[0].endswith("mangago-downloader-web") or command[-1] == "webapp.server")

    def test_missing_mangago_module_is_controlled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(root_menu, "MANGAGO_DIR", Path(tmp) / "missing"):
                with self.assertRaises(FileNotFoundError):
                    root_menu.build_mangago_web_command()

    def test_missing_output_is_controlled(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "missing-output"
            with patch("builtins.print") as printed:
                root_menu.manual_pdf_flow(output_dir=output_dir)

        text = "\n".join(str(call.args[0]) for call in printed.call_args_list if call.args)
        self.assertIn("Nenhum output encontrado", text)

    def test_parse_selection_accepts_ranges_and_todos(self):
        self.assertEqual(root_menu.parse_selection("1,3,5-7,12", 10), [1, 3, 5, 6, 7])
        self.assertEqual(root_menu.parse_selection("todos", 3), [1, 2, 3])

    def test_invalid_menu_choice_reprompts_until_exit(self):
        answers = iter(["abc", "9", "0"])
        with patch("builtins.input", side_effect=lambda _: next(answers)):
            with patch("builtins.print"):
                choice = root_menu.ask_number("Escolha", {0, 1})

        self.assertEqual(choice, 0)

    def test_list_chapter_dirs_returns_only_chapters_with_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            manga = Path(tmp) / "Manga"
            empty = manga / "Ch. 1"
            full = manga / "Ch. 2"
            empty.mkdir(parents=True)
            full.mkdir()
            write_image(full / "page-001.jpg")

            chapters = root_menu.list_chapter_dirs(manga)

        self.assertEqual([chapter.name for chapter in chapters], ["Ch. 2"])

    def test_pdf_batch_uses_public_converter_facade(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "Manga" / "Ch. 1"
            chapter.mkdir(parents=True)
            write_image(chapter / "page-001.jpg")

            converter = MagicMock(return_value=str(chapter / "Ch. 1.pdf"))
            with patch.object(root_menu, "_import_convert_to_pdf", return_value=converter):
                summary = root_menu.run_pdf_batch([chapter])

        converter.assert_called_once_with(str(chapter))
        self.assertEqual(summary["generated"], [chapter])

    def test_pdf_batch_skips_existing_pdf_without_regenerate(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "Manga" / "Ch. 1"
            chapter.mkdir(parents=True)
            write_image(chapter / "page-001.jpg")
            (chapter / "Ch. 1.pdf").write_bytes(b"%PDF")

            converter = MagicMock()
            with patch.object(root_menu, "_import_convert_to_pdf", return_value=converter):
                summary = root_menu.run_pdf_batch([chapter], regenerate_existing=False)

        converter.assert_not_called()
        self.assertEqual(summary["skipped"], [chapter])

    def test_pdf_batch_continues_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "Manga" / "Ch. 1"
            second = Path(tmp) / "Manga" / "Ch. 2"
            first.mkdir(parents=True)
            second.mkdir(parents=True)

            def convert(chapter_dir):
                if chapter_dir.endswith("Ch. 1"):
                    raise RuntimeError("boom")
                return str(Path(chapter_dir) / f"{Path(chapter_dir).name}.pdf")

            with patch.object(root_menu, "_import_convert_to_pdf", return_value=convert):
                summary = root_menu.run_pdf_batch([first, second])

        self.assertEqual(summary["generated"], [second])
        self.assertEqual(summary["failed"][0][0], first)

    def test_back_option_returns_from_manual_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            manga = output / "Manga"
            chapter = manga / "Ch. 1"
            chapter.mkdir(parents=True)
            write_image(chapter / "page-001.jpg")

            with patch("builtins.input", return_value="0"):
                with patch.object(root_menu, "run_pdf_batch") as batch:
                    root_menu.manual_pdf_flow(output)

        batch.assert_not_called()

    def test_exit_option_leaves_main_menu(self):
        with patch("builtins.input", return_value="0"):
            with patch("builtins.print"):
                root_menu.main()


if __name__ == "__main__":
    unittest.main()
