from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from webrag.chunk.markdown import chunk_document
from webrag.extract.cleaner import (
    extract_collapsed_sections,
    extract_document,
    merge_collapsed_sections,
    normalize_markdown,
    strip_inline_html,
    unescape_entities,
)
from webrag.models import RawPage


class DocumentTitleTests(unittest.TestCase):
    def setUp(self):
        self.page = RawPage(
            url="https://example.org/procedure",
            final_url="https://example.org/procedure",
            status=200,
            content_type="text/html",
            body=b"<html><body>procedure</body></html>",
            fetched_at="2026-01-01T00:00:00+00:00",
        )
        self.markdown = (
            "### LĨNH VỰC TTHC\n\n"
            "#### Cấp lại giấy phép xuất nhập cảnh\n\n"
            + ("Thông tin thủ tục hành chính. " * 10)
        )

    def extract_with_metadata_title(self, metadata_title):
        metadata = SimpleNamespace(
            title=metadata_title,
            author=None,
            date=None,
            language=None,
        )
        with (
            patch("webrag.extract.cleaner.trafilatura.extract", return_value=self.markdown),
            patch(
                "webrag.extract.cleaner.trafilatura.extract_metadata",
                return_value=metadata,
            ),
        ):
            return extract_document(self.page)

    def test_generic_site_title_uses_first_non_generic_content_heading(self):
        document = self.extract_with_metadata_title("BỘ CÔNG AN")
        self.assertIsNotNone(document)
        self.assertEqual(document.title, "Cấp lại giấy phép xuất nhập cảnh")

    def test_specific_metadata_title_is_preserved(self):
        document = self.extract_with_metadata_title("Example procedure")
        self.assertIsNotNone(document)
        self.assertEqual(document.title, "Example procedure")

    def test_extracts_collapsed_procedure_section_and_table_text(self):
        html = """
        <div class="tthc-list-item">
          <div class="item-title collapsed" data-toggle="collapse"
               href="#collapse6a">Thành phần hồ sơ</div>
          <div id="collapse6a" class="collapse">
            <table><tr><th>Tên giấy tờ</th><th>Số lượng</th></tr>
            <tr><td>Ảnh mới chụp</td><td>02</td></tr></table>
          </div>
        </div>
        """

        sections = extract_collapsed_sections(html)

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0][0], "Thành phần hồ sơ")
        self.assertIn("Tên giấy tờ: Ảnh mới chụp", sections[0][1])
        self.assertIn("Số lượng: 02", sections[0][1])
        self.assertIn(
            "Tên giấy tờ: Ảnh mới chụp | Số lượng: 02",
            sections[0][1],
        )

    def test_table_rows_keep_values_associated_with_column_headers(self):
        html = """
        <div class="item-title" data-toggle="collapse" href="#deadlines">
          Thời hạn giải quyết
        </div>
        <div id="deadlines" class="collapse">
          <table>
            <tr><th>Hình thức nộp</th><th>Thời hạn giải quyết</th></tr>
            <tr><td>Trực tiếp</td><td>08 Ngày làm việc</td></tr>
            <tr><td>Trực tuyến</td><td>08 Ngày làm việc</td></tr>
          </table>
        </div>
        """

        sections = extract_collapsed_sections(html)

        self.assertEqual(len(sections), 1)
        self.assertIn(
            "Hình thức nộp: Trực tiếp | Thời hạn giải quyết: 08 Ngày làm việc",
            sections[0][1],
        )
        self.assertIn(
            "Hình thức nộp: Trực tuyến | Thời hạn giải quyết: 08 Ngày làm việc",
            sections[0][1],
        )

    def test_extracts_sections_when_trafilatura_finds_no_content(self):
        body = (
            "Thông tin chi tiết về hồ sơ cần chuẩn bị cho thủ tục hành chính. "
            "Người nộp hồ sơ cần kiểm tra đầy đủ giấy tờ trước khi gửi yêu cầu."
        )
        html = f"""
        <div class="item-title" data-toggle="collapse" href="#panel">
          Hồ sơ cần chuẩn bị
        </div>
        <div id="panel" class="collapse">{body}</div>
        """
        page = RawPage(
            url=self.page.url,
            final_url=self.page.final_url,
            status=200,
            content_type="text/html",
            body=html.encode("utf-8"),
            fetched_at=self.page.fetched_at,
        )
        metadata = SimpleNamespace(
            title="BỘ CÔNG AN", author=None, date=None, language="vi"
        )
        with (
            patch("webrag.extract.cleaner.trafilatura.extract", return_value=None),
            patch(
                "webrag.extract.cleaner.trafilatura.extract_metadata",
                return_value=metadata,
            ),
        ):
            document = extract_document(page)

        self.assertIsNotNone(document)
        self.assertIn("## Hồ sơ cần chuẩn bị", document.markdown)
        self.assertIn(body, document.markdown)
        self.assertEqual(document.title, "Hồ sơ cần chuẩn bị")

    def test_supports_bootstrap_five_and_nested_heading_markup(self):
        html = """
        <div class="item-title" data-bs-toggle="collapse" data-bs-target="#panel">
          Hồ sơ <div>cần chuẩn bị</div>
          <script>ignored heading text</script>
        </div>
        <div id="panel">
          Nội dung chính.
          <script>ignored panel text</script>
          <style>.ignored { display: none; }</style>
          Nội dung được giữ lại.
        </div>
        """

        sections = extract_collapsed_sections(html)

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0][0], "Hồ sơ cần chuẩn bị")
        self.assertIn("Nội dung chính.", sections[0][1])
        self.assertIn("Nội dung được giữ lại.", sections[0][1])
        self.assertNotIn("ignored", sections[0][1])

    def test_page_without_accordion_preserves_extracted_markdown(self):
        expected = normalize_markdown(self.markdown)
        metadata = SimpleNamespace(
            title="Example procedure",
            author=None,
            date=None,
            language="en",
        )
        with (
            patch(
                "webrag.extract.cleaner.trafilatura.extract",
                return_value=self.markdown,
            ),
            patch(
                "webrag.extract.cleaner.trafilatura.extract_metadata",
                return_value=metadata,
            ),
        ):
            document = extract_document(self.page)

        self.assertIsNotNone(document)
        self.assertEqual(document.markdown, expected)

    def test_extract_document_strips_inline_font_and_span_markup(self):
        markdown = (
            "A <font color=\"#75507B\">styled</font> "
            "<span style=\"color: red\">inline</span> "
            "<u style=\"text-decoration: underline\"><b>formatted</b></u> fact. "
            + ("More extracted text. " * 10)
        )
        metadata = SimpleNamespace(
            title="Example procedure",
            author=None,
            date=None,
            language="en",
        )
        with (
            patch("webrag.extract.cleaner.trafilatura.extract", return_value=markdown),
            patch(
                "webrag.extract.cleaner.trafilatura.extract_metadata",
                return_value=metadata,
            ),
        ):
            document = extract_document(self.page)

        self.assertIsNotNone(document)
        self.assertIn("A styled inline formatted fact.", document.markdown)
        self.assertNotRegex(document.markdown, r"</?(?:font|span|u|b)\b")

    def test_extract_document_removes_standalone_affiliation_markers(self):
        markdown = (
            "###### Abstract\n\n"
            "<sup>†</sup>\n\n"
            "<sup>†</sup>\n\n"
            "<sup>∗</sup>University affiliation.\n\n"
            "An abstract sentence with an inline citation <sup>1</sup>. "
            + ("More extracted text. " * 10)
        )
        metadata = SimpleNamespace(
            title="Example paper",
            author=None,
            date=None,
            language="en",
        )
        with (
            patch("webrag.extract.cleaner.trafilatura.extract", return_value=markdown),
            patch(
                "webrag.extract.cleaner.trafilatura.extract_metadata",
                return_value=metadata,
            ),
        ):
            document = extract_document(self.page)

        self.assertIsNotNone(document)
        self.assertNotIn("<sup>†</sup>", document.markdown)
        self.assertIn("<sup>∗</sup>University affiliation.", document.markdown)
        self.assertIn("citation <sup>1</sup>", document.markdown)

    def test_strip_inline_html_preserves_inner_text(self):
        self.assertEqual(
            strip_inline_html(
                '<font color="red">one <span style="x"><b>two</b></span></font>'
            ),
            "one two",
        )

    def test_fastapi_first_steps_snapshot_strips_font_and_span_preserving_text(self):
        snapshot_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "raw"
            / "94c74a9258b3dd5f.html"
        )
        if not snapshot_path.is_file():
            self.skipTest("FastAPI first-steps snapshot not found.")
        page = RawPage(
            url="https://fastapi.tiangolo.com/tutorial/first-steps/",
            final_url="https://fastapi.tiangolo.com/tutorial/first-steps/",
            status=200,
            content_type="text/html",
            body=snapshot_path.read_bytes(),
            fetched_at="2026-01-01T00:00:00+00:00",
        )
        document = extract_document(page)
        self.assertIsNotNone(document)
        self.assertNotIn("<font", document.markdown)
        self.assertNotIn("<span", document.markdown)
        self.assertIn("uv run fastapi", document.markdown)
        self.assertIn("FastAPI", document.markdown)

    def test_matt_26279_snapshot_unescapes_entities_preserving_sample_form_text(self):
        snapshot_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "raw"
            / "c9972798b5d0c4c6.html"
        )
        if not snapshot_path.is_file():
            self.skipTest("matt=26279 snapshot not found.")
        page = RawPage(
            url="https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279",
            final_url="https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279",
            status=200,
            content_type="text/html",
            body=snapshot_path.read_bytes(),
            fetched_at="2026-01-01T00:00:00+00:00",
        )
        document = extract_document(page)
        self.assertIsNotNone(document)
        self.assertNotIn("&amp;amp;", document.markdown)
        self.assertIn("mẫu NA9", document.markdown)

    def test_unescape_entities_preserves_code_fences(self):
        text = "outside &amp;amp;\n```\ninside &amp;amp;\n```\noutside again &amp;amp;"
        unescaped = unescape_entities(text)
        self.assertEqual(
            unescaped,
            "outside &\n```\ninside &amp;amp;\n```\noutside again &",
        )

    def test_collapsed_sections_become_retrievable_chunk_headings(self):
        html = """
        <div class="item-title" data-toggle="collapse" href="#documents">
          Thành phần hồ sơ
        </div>
        <div id="documents" class="collapse">
          Người đề nghị nộp tờ khai theo mẫu và giấy tờ tùy thân hợp lệ.
        </div>
        <div class="item-title" data-toggle="collapse" href="#legal">
          Căn cứ pháp lý
        </div>
        <div id="legal" class="collapse">
          Quy định tại văn bản pháp luật hiện hành về xuất nhập cảnh.
        </div>
        """
        page = RawPage(
            url=self.page.url,
            final_url=self.page.final_url,
            status=200,
            content_type="text/html",
            body=html.encode("utf-8"),
            fetched_at=self.page.fetched_at,
        )
        metadata = SimpleNamespace(
            title="BỘ CÔNG AN",
            author=None,
            date=None,
            language="vi",
        )
        with (
            patch(
                "webrag.extract.cleaner.trafilatura.extract",
                return_value="Thông tin thủ tục hành chính. " * 10,
            ),
            patch(
                "webrag.extract.cleaner.trafilatura.extract_metadata",
                return_value=metadata,
            ),
        ):
            document = extract_document(page)

        self.assertIsNotNone(document)
        chunks = chunk_document(document)
        section_paths = [chunk.section_path for chunk in chunks]
        self.assertIn(["Thành phần hồ sơ"], section_paths)
        self.assertIn(["Căn cứ pháp lý"], section_paths)

    def test_merge_adds_heading_for_short_section_and_avoids_long_duplicate(self):
        repeated_detail = (
            "A repeated detail with enough text to exceed the duplicate threshold. "
            * 3
        )
        markdown = f"### Phí\n\n200.000đ\n\n### Chi tiết\n\n{repeated_detail}"
        merged = merge_collapsed_sections(
            markdown,
            [
                ("Phí", "200.000đ"),
                ("Chi tiết", repeated_detail),
            ],
        )

        self.assertEqual(merged, markdown)

    def test_renamed_accordion_heading_is_preserved_without_hardcoding(self):
        sections = extract_collapsed_sections(
            """
            <div class="item-title" data-toggle="collapse" href="#panel">
              Yêu cầu bổ sung
            </div>
            <div id="panel">Nội dung cho tiêu đề mới.</div>
            """
        )

        self.assertEqual(sections, [("Yêu cầu bổ sung", "Nội dung cho tiêu đề mới.")])


if __name__ == "__main__":
    unittest.main()
