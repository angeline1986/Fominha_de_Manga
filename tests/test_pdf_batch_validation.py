import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

import menu
from pdf_batch_validation import (
    count_pdf_pages,
    list_supported_images,
    validate_chapter_images,
    validate_pdf_output,
)


def write_image(path: Path, size=(8, 8), mode="RGB") -> None:
    image = Image.new(mode, size, (255, 255, 255, 0) if mode == "RGBA" else "white")
    image.save(path)


def write_pdf(path: Path, pages: int = 1) -> None:
    objects = "\n".join(f"{index} 0 obj << /Type /Page >> endobj" for index in range(1, pages + 1))
    path.write_bytes(("%PDF-1.4\n" + objects + "\n%%EOF").encode("ascii"))


class PdfBatchValidationTests(unittest.TestCase):
    def test_chapter_without_images_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "Ch. 1"
            chapter.mkdir()

            result = validate_chapter_images(chapter)

        self.assertFalse(result.ok)
        self.assertIn("Nenhuma imagem", result.errors[0])

    def test_page_sequence_one_two_three_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            for number in (1, 2, 3):
                write_image(chapter / f"page-{number:03d}.png")

            result = validate_chapter_images(chapter)

        self.assertTrue(result.ok)
        self.assertEqual([path.name for path in result.image_files], ["page-001.png", "page-002.png", "page-003.png"])

    def test_page_sequence_detects_middle_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "page-001.png")
            write_image(chapter / "page-002.png")
            write_image(chapter / "page-004.png")

            result = validate_chapter_images(chapter)

        self.assertFalse(result.ok)
        self.assertIn("page-003", "; ".join(result.errors))

    def test_page_sequence_detects_missing_first_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "page-002.png")
            write_image(chapter / "page-003.png")

            result = validate_chapter_images(chapter)

        self.assertFalse(result.ok)
        self.assertIn("page-001", "; ".join(result.errors))

    def test_natural_sort_preserves_page_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            for name in ("page-010.jpg", "page-002.jpg", "page-001.jpg"):
                write_image(chapter / name)

            ordered = list_supported_images(chapter)

        self.assertEqual([path.name for path in ordered], ["page-001.jpg", "page-002.jpg", "page-010.jpg"])

    def test_corrupted_image_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            (chapter / "page-001.png").write_bytes(b"not an image")

            result = validate_chapter_images(chapter)

        self.assertFalse(result.ok)
        self.assertIn("Imagem ilegível", "; ".join(result.errors))

    def test_incompatible_pdf_dimension_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "page-001.png", size=(1280, 3))

            result = validate_chapter_images(chapter)

        self.assertFalse(result.ok)
        self.assertIn("limites do PDF", "; ".join(result.errors))

    def test_regression_page_069_1280_by_3_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "page-069.png", size=(1280, 3))

            result = validate_chapter_images(chapter)

        self.assertFalse(result.ok)
        self.assertIn("page-069.png", "; ".join(result.errors))

    def test_short_but_valid_image_is_not_rejected_arbitrarily(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "page-001.png", size=(1280, 41))

            result = validate_chapter_images(chapter)

        self.assertTrue(result.ok, result.errors)

    def test_in_progress_marker_blocks_pdf_generation(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            manga = Path(tmp) / "Manga"
            chapter = manga / "IMG" / "Ch. 1"
            chapter.mkdir(parents=True)

            write_image(chapter / "page-001.png")
            (chapter / ".download-in-progress.json").write_text(
                json.dumps({
                    "status": "downloading",
                    "expected_pages": 3,
                }),
                encoding="utf-8",
            )

            converter = MagicMock()

            with patch.object(
                menu,
                "_import_convert_to_pdf",
                return_value=converter,
            ):
                summary = menu.run_pdf_batch([chapter])

            report = (
                manga
                / "reports"
                / "Ch. 1.validation.json"
            )

            converter.assert_not_called()
            self.assertEqual(
                summary["validation_failed"][0][0],
                chapter,
            )
            self.assertTrue(report.is_file())

            payload = json.loads(
                report.read_text(encoding="utf-8")
            )
            self.assertEqual(
                payload["issue_type"],
                "download_not_completed",
            )

    def test_complete_marker_uses_expected_page_count(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            manga = Path(tmp) / "Manga"
            chapter = manga / "IMG" / "Ch. 1"
            chapter.mkdir(parents=True)

            write_image(chapter / "page-001.png")
            write_image(chapter / "page-002.png")

            (chapter / ".download-complete.json").write_text(
                json.dumps({
                    "status": "completed",
                    "expected_pages": 3,
                }),
                encoding="utf-8",
            )

            converter = MagicMock()

            with patch.object(
                menu,
                "_import_convert_to_pdf",
                return_value=converter,
            ):
                summary = menu.run_pdf_batch([chapter])

            report = (
                manga
                / "reports"
                / "Ch. 1.validation.json"
            )

            converter.assert_not_called()
            self.assertEqual(
                summary["validation_failed"][0][0],
                chapter,
            )

            payload = json.loads(
                report.read_text(encoding="utf-8")
            )
            self.assertEqual(
                payload["issue_type"],
                "image_validation_failed",
            )
            self.assertEqual(
                payload["images"]["expected"],
                3,
            )
            self.assertEqual(
                payload["images"]["found"],
                2,
            )

    def test_legacy_chapter_without_markers_remains_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "Ch. 1"
            chapter.mkdir()

            write_image(chapter / "page-001.png")
            pdf = chapter / "Ch. 1.pdf"

            def convert(chapter_dir):
                write_pdf(pdf)
                return str(pdf)

            converter = MagicMock(side_effect=convert)

            with patch.object(
                menu,
                "_import_convert_to_pdf",
                return_value=converter,
            ):
                summary = menu.run_pdf_batch([chapter])

            converter.assert_called_once_with(str(chapter))
            self.assertEqual(
                summary["generated"],
                [chapter],
            )

    def test_invalid_complete_marker_blocks_pdf_generation(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            manga = Path(tmp) / "Manga"
            chapter = manga / "IMG" / "Ch. 1"
            chapter.mkdir(parents=True)

            write_image(chapter / "page-001.png")

            (chapter / ".download-complete.json").write_text(
                "{invalid-json",
                encoding="utf-8",
            )

            converter = MagicMock()

            with patch.object(
                menu,
                "_import_convert_to_pdf",
                return_value=converter,
            ):
                summary = menu.run_pdf_batch([chapter])

            report = (
                manga
                / "reports"
                / "Ch. 1.validation.json"
            )

            converter.assert_not_called()
            self.assertEqual(
                summary["validation_failed"][0][0],
                chapter,
            )

            payload = json.loads(
                report.read_text(encoding="utf-8")
            )
            self.assertEqual(
                payload["issue_type"],
                "download_state_invalid",
            )

    def test_valid_chapter_calls_convert_to_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "Ch. 1"
            chapter.mkdir()
            write_image(chapter / "page-001.jpg")
            pdf = chapter / "Ch. 1.pdf"

            def convert(chapter_dir):
                write_pdf(pdf)
                return str(pdf)

            converter = MagicMock(side_effect=convert)
            with patch.object(menu, "_import_convert_to_pdf", return_value=converter):
                summary = menu.run_pdf_batch([chapter])

        converter.assert_called_once_with(str(chapter))
        self.assertEqual(summary["generated"], [chapter])

    def test_invalid_chapter_does_not_call_convert_to_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "Ch. 1"
            chapter.mkdir()
            write_image(chapter / "page-001.png", size=(1280, 3))

            converter = MagicMock()
            with patch.object(menu, "_import_convert_to_pdf", return_value=converter):
                summary = menu.run_pdf_batch([chapter])

        converter.assert_not_called()
        self.assertEqual(summary["validation_failed"][0][0], chapter)

    def test_expected_total_equal_found_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "page-001.jpg")
            write_image(chapter / "page-002.jpg")

            result = validate_chapter_images(chapter, expected_total=2)

        self.assertTrue(result.ok)

    def test_expected_total_divergence_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "page-001.jpg")

            result = validate_chapter_images(chapter, expected_total=2)

        self.assertFalse(result.ok)
        self.assertIn("esperado 2", "; ".join(result.errors))

    def test_unavailable_expected_total_does_not_create_false_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp)
            write_image(chapter / "cover.jpg")

            result = validate_chapter_images(chapter)

        self.assertTrue(result.ok, result.errors)
        self.assertIsNone(result.expected_total)

    def test_pdf_output_exists_and_page_count_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "chapter.pdf"
            write_pdf(pdf, pages=2)

            result = validate_pdf_output(pdf, expected_pages=2)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.page_count, 2)

    def test_empty_pdf_fails_post_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "chapter.pdf"
            pdf.write_bytes(b"")

            result = validate_pdf_output(pdf, expected_pages=1)

        self.assertFalse(result.ok)
        self.assertIn("vazio", "; ".join(result.errors))

    def test_non_pdf_file_fails_post_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "chapter.pdf"
            pdf.write_bytes(b"plain text")

            result = validate_pdf_output(pdf, expected_pages=1)

        self.assertFalse(result.ok)
        self.assertIn("não parece", "; ".join(result.errors))

    def test_pdf_page_count_divergence_fails_post_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "chapter.pdf"
            write_pdf(pdf, pages=1)

            result = validate_pdf_output(pdf, expected_pages=2)

        self.assertFalse(result.ok)
        self.assertIn("Quantidade de páginas", "; ".join(result.errors))

    def test_pdf_page_counter_ignores_pages_tree_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "chapter.pdf"
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Pages >> endobj\n2 0 obj << /Type /Page >> endobj\n%%EOF")

            self.assertEqual(count_pdf_pages(pdf), 1)

    def test_validation_failure_does_not_interrupt_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "Ch. 1"
            second = Path(tmp) / "Ch. 2"
            first.mkdir()
            second.mkdir()
            write_image(first / "page-001.png", size=(1280, 3))
            write_image(second / "page-001.png")
            second_pdf = second / "Ch. 2.pdf"

            def convert(chapter_dir):
                write_pdf(second_pdf)
                return str(second_pdf)

            converter = MagicMock(side_effect=convert)
            with patch.object(menu, "_import_convert_to_pdf", return_value=converter):
                summary = menu.run_pdf_batch([first, second])

        converter.assert_called_once_with(str(second))
        self.assertEqual(summary["validation_failed"][0][0], first)
        self.assertEqual(summary["generated"], [second])

    def test_conversion_failure_does_not_interrupt_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "Ch. 1"
            second = Path(tmp) / "Ch. 2"
            first.mkdir()
            second.mkdir()
            write_image(first / "page-001.png")
            write_image(second / "page-001.png")

            def convert(chapter_dir):
                path = Path(chapter_dir)
                if path.name == "Ch. 1":
                    raise RuntimeError("boom")
                pdf = path / f"{path.name}.pdf"
                write_pdf(pdf)
                return str(pdf)

            with patch.object(menu, "_import_convert_to_pdf", return_value=convert):
                summary = menu.run_pdf_batch([first, second])

        self.assertEqual(summary["generation_failed"][0][0], first)
        self.assertEqual(summary["generated"], [second])

    def test_existing_pdf_is_preserved_when_regeneration_validation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "Ch. 1"
            chapter.mkdir()
            write_image(chapter / "page-001.png", size=(1280, 3))
            pdf = chapter / "Ch. 1.pdf"
            original = b"%PDF-1.4\noriginal\n%%EOF"
            pdf.write_bytes(original)

            converter = MagicMock()
            with patch.object(menu, "_import_convert_to_pdf", return_value=converter):
                summary = menu.run_pdf_batch([chapter], regenerate_existing=True)

            converter.assert_not_called()
            self.assertEqual(pdf.read_bytes(), original)
            self.assertEqual(summary["validation_failed"][0][0], chapter)

    def test_batch_summary_counts_selected_existing_validation_and_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "Ch. 1"
            invalid = Path(tmp) / "Ch. 2"
            failed = Path(tmp) / "Ch. 3"
            generated = Path(tmp) / "Ch. 4"
            for chapter in (existing, invalid, failed, generated):
                chapter.mkdir()
            write_image(existing / "page-001.png")
            write_pdf(existing / "Ch. 1.pdf")
            write_image(invalid / "page-001.png", size=(1280, 3))
            write_image(failed / "page-001.png")
            write_image(generated / "page-001.png")

            def convert(chapter_dir):
                path = Path(chapter_dir)
                if path.name == "Ch. 3":
                    return None
                pdf = path / f"{path.name}.pdf"
                write_pdf(pdf)
                return str(pdf)

            with patch.object(menu, "_import_convert_to_pdf", return_value=convert):
                summary = menu.run_pdf_batch([existing, invalid, failed, generated])

        self.assertEqual(summary["selected"], 4)
        self.assertEqual(summary["skipped"], [existing])
        self.assertEqual(summary["validation_failed"][0][0], invalid)
        self.assertEqual(summary["generation_failed"][0][0], failed)
        self.assertEqual(summary["generated"], [generated])
        self.assertEqual(len(summary["failed"]), 2)
        self.assertEqual(len(summary["problems"]), 2)


if __name__ == "__main__":
    unittest.main()
