import hashlib
import html
import io
import logging
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pypdfium2 as pdfium
import pytesseract
import trafilatura
from PIL import Image
from pypdf import PdfReader

from webrag.models import Document, PageSpan, RawPage

logger = logging.getLogger(__name__)
MIN_MARKDOWN_CHARS = 100
DEFAULT_OCR_MIN_PAGE_CHARS = 40
DEFAULT_OCR_DPI = 300
INLINE_HTML = re.compile(r"</?(?:font|span|u|b)\b[^>]*>", re.IGNORECASE)
ORPHAN_SUPERSCRIPT = re.compile(
    r"^[ \t]*<sup\b[^>]*>[ \t]*[†‡∗*]+[ \t]*</sup>[ \t]*(?:\r?\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
GENERIC_TITLES = {
    "bộ công an",
    "cổng dịch vụ công trực tuyến",
    "cổng dịch vụ công - bộ công an",
    "lĩnh vực tthc",
}

# Common tracking parameters to strip during canonicalization
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "source"
}
BLOCK_TAGS = {
    "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p",
    "section", "table", "tbody", "tfoot", "thead", "tr", "ul",
}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
TOGGLE_ATTRIBUTES = ("data-toggle", "data-bs-toggle")


class ProcedureAccordionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titles: dict[str, str] = {}
        self.sections: dict[str, list[str]] = {}
        self.heading_id: str | None = None
        self.heading_tag: str | None = None
        self.heading_parts: list[str] = []
        self.heading_depth = 0
        self.active_panel: str | None = None
        self.panel_stack: list[str] = []
        self.skip_tags: list[str] = []
        self.table_depth = 0
        self.table_headers: list[str] = []
        self.table_row: list[tuple[str, str]] = []
        self.table_cell_tag: str | None = None
        self.table_cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        classes = attributes.get("class", "").split()

        if self.active_panel:
            if tag not in VOID_TAGS:
                self.panel_stack.append(tag)
            if tag == "table":
                self.table_depth += 1
                if self.table_depth == 1:
                    self.table_headers = []
                    self.table_row = []
            elif self.table_depth:
                if tag == "tr":
                    self._finish_table_row()
                elif tag in {"td", "th"}:
                    self._finish_table_cell()
                    self.table_cell_tag = tag
                    self.table_cell_parts = []
            elif tag in {"td", "th"}:
                self.sections[self.active_panel].append(" | ")
            elif tag in BLOCK_TAGS:
                self.sections[self.active_panel].append("\n")
        elif self.heading_id and tag == self.heading_tag:
            self.heading_depth += 1

        if tag in {"script", "style"} and (self.active_panel or self.heading_id):
            self.skip_tags.append(tag)

        if (
            self.heading_id is None
            and "item-title" in classes
            and any(attributes.get(name) == "collapse" for name in TOGGLE_ATTRIBUTES)
        ):
            target = (
                attributes.get("data-target")
                or attributes.get("data-bs-target")
                or attributes.get("href")
                or attributes.get("aria-controls")
            )
            if target:
                self.heading_id = target.removeprefix("#")
                self.heading_tag = tag
                self.heading_parts = []
                self.heading_depth = 1

        panel_id = attributes.get("id")
        if (
            self.active_panel is None
            and panel_id
            and panel_id in self.titles
        ):
            self.active_panel = panel_id
            self.panel_stack = [tag]
            self.sections[panel_id] = []

    def handle_endtag(self, tag: str) -> None:
        if self.skip_tags and self.skip_tags[-1] == tag:
            self.skip_tags.pop()

        if self.active_panel:
            if self.table_depth and tag in {"td", "th"}:
                self._finish_table_cell()
            elif self.table_depth and tag == "tr":
                self._finish_table_row()
            elif self.table_depth and tag == "table":
                self.table_depth -= 1
                if self.table_depth == 0:
                    self._finish_table_row()
                    self._finish_table()
            elif not self.table_depth and tag in BLOCK_TAGS:
                self.sections[self.active_panel].append("\n")
            for index in range(len(self.panel_stack) - 1, -1, -1):
                if self.panel_stack[index] == tag:
                    del self.panel_stack[index:]
                    break
            if not self.panel_stack:
                self.active_panel = None

        if self.heading_tag == tag and self.heading_id:
            self.heading_depth -= 1
            if self.heading_depth == 0:
                title = " ".join(" ".join(self.heading_parts).split())
                if title:
                    self.titles[self.heading_id] = title
                self.heading_id = None
                self.heading_tag = None
                self.heading_parts = []

    def handle_data(self, data: str) -> None:
        if self.skip_tags:
            return
        if self.active_panel:
            if self.table_depth:
                if self.table_cell_tag:
                    self.table_cell_parts.append(data)
            else:
                self.sections[self.active_panel].append(data)
        elif self.heading_id:
            self.heading_parts.append(data)

    def _finish_table_cell(self) -> None:
        if self.table_cell_tag is None:
            return
        cell_text = " ".join("".join(self.table_cell_parts).split())
        self.table_row.append((self.table_cell_tag, cell_text))
        self.table_cell_tag = None
        self.table_cell_parts = []

    def _finish_table_row(self) -> None:
        self._finish_table_cell()
        if not self.table_row:
            return
        if not self.table_headers and any(tag == "th" for tag, _ in self.table_row):
            self.table_headers = [text for _, text in self.table_row]
        else:
            cells = [text for _, text in self.table_row]
            if self.table_headers:
                pairs = [
                    f"{header}: {value}"
                    for header, value in zip(self.table_headers, cells)
                    if value
                ]
                row_text = " | ".join(pairs)
            else:
                row_text = " | ".join(
                    f"Column {index}: {value}"
                    for index, value in enumerate(cells, start=1)
                    if value
                )
            if row_text and self.active_panel:
                self.sections[self.active_panel].append(f"\n{row_text}\n")
        self.table_row = []

    def _finish_table(self) -> None:
        self.table_headers = []
        self.table_row = []
        self.table_cell_tag = None
        self.table_cell_parts = []


def unescape_entities(text: str) -> str:
    """Unescape HTML entities until stable, leaving fenced code blocks intact."""
    lines = text.splitlines(keepends=True)
    in_code_block = False
    fence_char = ""
    fence_len = 0
    result = []
    for line in lines:
        stripped = line.strip()
        match = re.match(r"^(`{3,}|~{3,})", stripped)
        if match:
            delimiter = match.group(1)
            char = delimiter[0]
            length = len(delimiter)
            if not in_code_block:
                in_code_block = True
                fence_char = char
                fence_len = length
                result.append(line)
                continue
            elif char == fence_char and length >= fence_len:
                in_code_block = False
                fence_char = ""
                fence_len = 0
                result.append(line)
                continue
        if in_code_block:
            result.append(line)
        else:
            cur = line
            while True:
                nxt = html.unescape(cur)
                if nxt == cur:
                    break
                cur = nxt
            result.append(cur)
    return "".join(result)


def extract_collapsed_sections(html: str) -> list[tuple[str, str]]:
    parser = ProcedureAccordionParser()
    parser.feed(html)
    sections = []
    for panel_id, parts in parser.sections.items():
        title = parser.titles.get(panel_id)
        body = normalize_markdown("".join(parts))
        if title and body:
            sections.append((unescape_entities(title), unescape_entities(body)))
    return sections


def merge_collapsed_sections(
    markdown: str, sections: list[tuple[str, str]]
) -> str:
    normalized_markdown = " ".join(markdown.split()).casefold()
    existing_sections: dict[str, set[str]] = {}
    current_title: str | None = None
    current_parts: list[str] = []

    def store_existing_section() -> None:
        if current_title:
            existing_sections.setdefault(current_title, set()).add(
                " ".join(" ".join(current_parts).split()).casefold()
            )

    for line in markdown.splitlines():
        heading_match = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if heading_match:
            store_existing_section()
            current_title = heading_match.group(1).strip().casefold()
            current_parts = []
        elif current_title:
            current_parts.append(line)
    store_existing_section()

    additions = []
    for title, body in sections:
        normalized_body = " ".join(body.split()).casefold()
        if normalized_body in existing_sections.get(title.casefold(), set()):
            continue
        if (
            len(normalized_body) >= 100
            and normalized_body in normalized_markdown
        ):
            continue
        additions.append(f"## {title}\n\n{body}")
    if not additions:
        return markdown
    return normalize_markdown(f"{markdown}\n\n" + "\n\n".join(additions))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonicalize(url: str) -> str:
    """Normalize URL by stripping fragments, tracking queries, and trailing slashes."""
    parts = urlparse(url)
    filtered_query = [
        (k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMS
    ]
    query_str = urlencode(filtered_query)
    clean_path = parts.path.rstrip("/") or "/"
    return urlunparse(
        (parts.scheme.lower(), parts.netloc.lower(), clean_path, "", query_str, "")
    )


def decode_body(page: RawPage) -> str:
    return page.body.decode("utf-8", errors="replace")


def normalize_markdown(text: str) -> str:
    # Collapse excess whitespace and empty lines
    no_trailing_ws = re.sub(r"[ \t]+\n", "\n", text)
    collapsed = re.sub(r"\n{3,}", "\n\n", no_trailing_ws)
    return collapsed.strip()


def strip_inline_html(text: str) -> str:
    return INLINE_HTML.sub("", text)


def strip_orphan_superscripts(text: str) -> str:
    return ORPHAN_SUPERSCRIPT.sub("", text)


def content_heading(markdown: str) -> str | None:
    """Return the first non-generic heading extracted from the page content."""
    for line in markdown.splitlines():
        heading = re.sub(r"^#{1,6}\s+", "", line).strip()
        if not line.startswith("#") or not heading:
            continue
        if heading.casefold() in GENERIC_TITLES:
            continue
        return heading
    return None


def _positive_int_setting(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("%s must be an integer; using %d.", name, default)
        return default
    if value < 1:
        logger.warning("%s must be positive; using %d.", name, default)
        return default
    return value


def _ocr_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        languages = set(pytesseract.get_languages(config=""))
    except (
        OSError,
        pytesseract.TesseractError,
        pytesseract.TesseractNotFoundError,
    ) as exc:
        logger.warning("Skipping OCR because Tesseract is unavailable: %s", exc)
        return False

    missing = {"vie", "eng"} - languages
    if missing:
        logger.warning(
            "Skipping OCR because Tesseract language data is missing: %s.",
            ", ".join(sorted(missing)),
        )
        return False
    return True


def _ocr_image(image: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(image, lang="vie+eng").strip()
    except (OSError, pytesseract.TesseractError, pytesseract.TesseractNotFoundError) as exc:
        logger.warning("Tesseract OCR failed; keeping native text: %s", exc)
        return ""


def _page_spans(page_texts: list[tuple[str, bool]]) -> tuple[str, list[PageSpan]]:
    text_parts = []
    spans = []
    offset = 0
    for page_number, (page_text, used_ocr) in enumerate(page_texts, start=1):
        cleaned_text = normalize_markdown(page_text)
        start = offset
        end = start + len(cleaned_text)
        spans.append(
            PageSpan(
                page=page_number,
                start=start,
                end=end,
                ocr=used_ocr,
            )
        )
        text_parts.append(cleaned_text)
        offset = end + 2
    return "\n\n".join(text_parts), spans


def _document_from_page_text(
    page: RawPage,
    collection: str,
    markdown: str,
    page_spans: list[PageSpan],
    title: str,
    author: str | None = None,
) -> Document | None:
    if len(markdown.strip()) < MIN_MARKDOWN_CHARS:
        return None
    canonical = canonicalize(page.final_url)
    return Document(
        doc_id=sha256_hex(canonical)[:16],
        url=page.url,
        canonical_url=canonical,
        domain=urlparse(canonical).netloc,
        title=title or page.final_url,
        author=author,
        published_at=None,
        language=None,
        markdown=markdown,
        content_hash=sha256_hex(markdown),
        fetched_at=page.fetched_at,
        collection=collection,
        page_spans=page_spans,
    )


def _extract_pdf_document(page: RawPage, collection: str) -> Document | None:
    reader = PdfReader(io.BytesIO(page.body))
    page_texts = [(pdf_page.extract_text() or "", False) for pdf_page in reader.pages]
    ocr_min_chars = _positive_int_setting(
        "WEBRAG_OCR_MIN_PAGE_CHARS", DEFAULT_OCR_MIN_PAGE_CHARS
    )
    pages_needing_ocr = [
        index for index, (text, _) in enumerate(page_texts) if len(text.strip()) < ocr_min_chars
    ]

    if pages_needing_ocr and _ocr_available():
        pdf_document = pdfium.PdfDocument(page.body)
        try:
            dpi = _positive_int_setting("WEBRAG_OCR_DPI", DEFAULT_OCR_DPI)
            for page_index in pages_needing_ocr:
                pdf_page = pdf_document[page_index]
                bitmap = pdf_page.render(scale=dpi / 72)
                try:
                    image = bitmap.to_pil()
                    try:
                        recognized = _ocr_image(image)
                    finally:
                        image.close()
                finally:
                    bitmap.close()
                    pdf_page.close()
                if recognized:
                    page_texts[page_index] = (recognized, True)
        finally:
            pdf_document.close()

    markdown, spans = _page_spans(page_texts)
    metadata = reader.metadata
    title = str(metadata.title).strip() if metadata and metadata.title else ""
    author = str(metadata.author).strip() if metadata and metadata.author else None
    return _document_from_page_text(
        page,
        collection,
        markdown,
        spans,
        title or Path(urlparse(page.final_url).path).name,
        author,
    )


def _extract_image_document(page: RawPage, collection: str) -> Document | None:
    if not _ocr_available():
        return None
    with Image.open(io.BytesIO(page.body)) as image:
        rgb_image = image.convert("RGB")
    try:
        recognized = _ocr_image(rgb_image)
    finally:
        rgb_image.close()
    markdown, spans = _page_spans([(recognized, bool(recognized))])
    return _document_from_page_text(
        page,
        collection,
        markdown,
        spans,
        Path(urlparse(page.final_url).path).name,
    )


def extract_document(page: RawPage, collection: str = "default") -> Document | None:
    """Extract clean markdown and metadata from a RawPage. Returns None if unusable."""
    if page.status != 200:
        return None

    content_type = page.content_type.split(";", 1)[0].strip().lower()
    if content_type == "application/pdf":
        return _extract_pdf_document(page, collection)
    if content_type in {"image/png", "image/jpeg"}:
        return _extract_image_document(page, collection)

    html = decode_body(page)
    markdown = trafilatura.extract(
        html,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
        favor_precision=True,
    ) or ""
    cleaned_markdown = normalize_markdown(
        strip_orphan_superscripts(strip_inline_html(markdown))
    )
    collapsed_sections = extract_collapsed_sections(html)
    cleaned_markdown = merge_collapsed_sections(cleaned_markdown, collapsed_sections)
    cleaned_markdown = unescape_entities(cleaned_markdown)
    if len(cleaned_markdown) < MIN_MARKDOWN_CHARS:
        return None

    meta = trafilatura.extract_metadata(html)
    canonical = canonicalize(page.final_url)
    metadata_title = meta.title.strip() if meta and meta.title else ""
    if metadata_title:
        metadata_title = unescape_entities(metadata_title)
    heading_title = content_heading(cleaned_markdown)
    if not metadata_title or metadata_title.casefold() in GENERIC_TITLES:
        title = heading_title or metadata_title or page.final_url
    else:
        title = metadata_title

    return Document(
        doc_id=sha256_hex(canonical)[:16],
        url=page.url,
        canonical_url=canonical,
        domain=urlparse(canonical).netloc,
        title=title.strip(),
        author=meta.author if meta else None,
        published_at=meta.date if meta else None,
        language=meta.language if meta else None,
        markdown=cleaned_markdown,
        content_hash=sha256_hex(cleaned_markdown),
        fetched_at=page.fetched_at,
        collection=collection,
    )
