from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from webrag.chunk.markdown import chunk_document
from webrag.extract import cleaner
from webrag.models import RawPage


def make_text_pdf(pages: list[str], title: str = "Fixture PDF") -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.setTitle(title)
    for text in pages:
        pdf.drawString(72, 720, text)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def make_scanned_pdf(vietnamese_text: str) -> bytes:
    font_paths = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    font_path = next((path for path in font_paths if path.is_file()), None)
    if font_path is None:
        raise unittest.SkipTest("No Vietnamese-capable fixture font is installed.")

    image = Image.new("RGB", (1100, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), vietnamese_text, fill="black", font=ImageFont.truetype(font_path, 34))
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.drawString(72, 720, "Native text on page one. " * 8)
    pdf.showPage()
    pdf.drawImage(ImageReader(BytesIO(image_bytes.getvalue())), 56, 330, width=500, height=164)
    pdf.showPage()
    pdf.drawString(72, 720, "Native text on page three. " * 8)
    pdf.showPage()
    pdf.save()
    return output.getvalue()


def make_pdf_page(body: bytes, content_type: str = "application/pdf") -> RawPage:
    return RawPage(
        url="https://example.org/files/guide.pdf",
        final_url="https://example.org/files/guide.pdf",
        status=200,
        content_type=content_type,
        body=body,
        fetched_at="2026-01-01T00:00:00+00:00",
    )


class PdfExtractionTests(unittest.TestCase):
    def test_text_pdf_chunks_keep_three_page_numbers(self):
        body = make_text_pdf(
            [
                "Page one contains enough native text for extraction and should stay on page one.",
                "Page two contains enough native text for extraction and should stay on page two.",
                "Page three contains enough native text for extraction and should stay on page three.",
            ]
        )

        with patch.object(cleaner, "_ocr_available") as ocr_available:
            document = cleaner.extract_document(make_pdf_page(body))
        with patch("webrag.chunk.markdown.get_tokenizer", return_value=None):
            chunks = chunk_document(document)

        self.assertIsNotNone(document)
        canonical = cleaner.canonicalize("https://example.org/files/guide.pdf")
        self.assertEqual(document.doc_id, cleaner.sha256_hex(canonical)[:16])
        self.assertEqual(document.content_hash, cleaner.sha256_hex(document.markdown))
        self.assertEqual([chunk.page for chunk in chunks], [1, 2, 3])
        self.assertEqual([chunk.ocr for chunk in chunks], [False, False, False])
        self.assertTrue(all("Page one" not in chunk.text or chunk.page == 1 for chunk in chunks))
        ocr_available.assert_not_called()

    def test_pdf_content_hash_depends_on_extracted_text_not_pdf_metadata(self):
        body_one = make_text_pdf(["Stable extracted text. " * 8], title="First title")
        body_two = make_text_pdf(["Stable extracted text. " * 8], title="Second title")

        first = cleaner.extract_document(make_pdf_page(body_one))
        second = cleaner.extract_document(make_pdf_page(body_two))

        self.assertNotEqual(body_one, body_two)
        self.assertEqual(first.content_hash, second.content_hash)

    def test_scanned_pdf_runs_ocr_only_for_the_image_page(self):
        body = make_scanned_pdf(
            "Thời hạn giải quyết: 08 Ngày làm việc; sử dụng mẫu TK01."
        )
        recognized = (
            "Thời hạn giải quyết: 08 Ngày làm việc; sử dụng mẫu TK01. "
            * 3
        )

        with (
            patch.object(cleaner, "_ocr_available", return_value=True),
            patch.object(cleaner, "_ocr_image", return_value=recognized) as ocr_image,
        ):
            document = cleaner.extract_document(make_pdf_page(body))
        with patch("webrag.chunk.markdown.get_tokenizer", return_value=None):
            chunks = chunk_document(document)

        self.assertIsNotNone(document)
        self.assertEqual(ocr_image.call_count, 1)
        self.assertEqual(
            [(span.page, span.ocr) for span in document.page_spans],
            [(1, False), (2, True), (3, False)],
        )
        self.assertEqual({chunk.page for chunk in chunks}, {1, 2, 3})
        self.assertEqual(
            {chunk.page for chunk in chunks if chunk.ocr},
            {2},
        )

    def test_missing_tesseract_warns_once_and_keeps_native_text_pages(self):
        body = make_text_pdf(
            [
                (
                    "This native text page contains enough words to keep a useful "
                    "document available. "
                )
                * 2,
                "tiny",
            ]
        )
        with (
            patch.object(
                cleaner.pytesseract,
                "get_tesseract_version",
                side_effect=FileNotFoundError("tesseract not installed"),
            ),
            patch.object(cleaner.pytesseract, "image_to_string") as image_to_string,
            self.assertLogs("webrag.extract.cleaner", level="WARNING") as logs,
        ):
            document = cleaner.extract_document(make_pdf_page(body))
        with patch("webrag.chunk.markdown.get_tokenizer", return_value=None):
            chunks = chunk_document(document)

        self.assertIsNotNone(document)
        self.assertIn("native text page", document.markdown)
        self.assertEqual(len(chunks), 2)
        self.assertEqual([chunk.ocr for chunk in chunks], [False, False])
        self.assertEqual(len(logs.records), 1)
        self.assertIn("Tesseract is unavailable", logs.records[0].getMessage())
        image_to_string.assert_not_called()

    def test_missing_vietnamese_language_data_skips_ocr_with_one_warning(self):
        body = make_text_pdf(
            [
                (
                    "This native text page contains enough words to keep a useful "
                    "document available. "
                )
                * 2,
                "tiny",
            ]
        )
        with (
            patch.object(cleaner.pytesseract, "get_tesseract_version", return_value="5"),
            patch.object(cleaner.pytesseract, "get_languages", return_value=["eng"]),
            patch.object(cleaner.pytesseract, "image_to_string") as image_to_string,
            self.assertLogs("webrag.extract.cleaner", level="WARNING") as logs,
        ):
            document = cleaner.extract_document(make_pdf_page(body))

        self.assertIsNotNone(document)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("vie", logs.records[0].getMessage())
        image_to_string.assert_not_called()

    def test_image_source_is_sent_directly_to_ocr(self):
        image_bytes = BytesIO()
        Image.new("RGB", (80, 40), "white").save(image_bytes, format="PNG")
        page = make_pdf_page(image_bytes.getvalue(), "image/png")
        recognized = "Extracted image text. " * 8

        with (
            patch.object(cleaner, "_ocr_available", return_value=True),
            patch.object(cleaner, "_ocr_image", return_value=recognized) as ocr_image,
        ):
            document = cleaner.extract_document(page)

        self.assertIsNotNone(document)
        self.assertEqual(ocr_image.call_count, 1)
        self.assertEqual(document.page_spans[0].page, 1)
        self.assertTrue(document.page_spans[0].ocr)

    def test_html_extraction_keeps_existing_markdown_without_page_metadata(self):
        markdown = "A stable HTML extraction result. " * 5
        metadata = type(
            "Metadata",
            (),
            {"title": "HTML page", "author": None, "date": None, "language": "en"},
        )()
        page = make_pdf_page(b"<html>existing behavior</html>", "text/html")
        with (
            patch.object(cleaner.trafilatura, "extract", return_value=markdown),
            patch.object(cleaner.trafilatura, "extract_metadata", return_value=metadata),
        ):
            document = cleaner.extract_document(page)

        self.assertIsNotNone(document)
        self.assertEqual(document.markdown, markdown.strip())
        self.assertIsNone(document.page_spans)
        with patch("webrag.chunk.markdown.get_tokenizer", return_value=None):
            chunks = chunk_document(document)
        self.assertTrue(all(chunk.page is None and chunk.ocr is None for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
