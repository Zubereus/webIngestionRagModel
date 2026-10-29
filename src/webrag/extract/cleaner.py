import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import trafilatura

from webrag.models import Document, RawPage

MIN_MARKDOWN_CHARS = 100
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


def extract_collapsed_sections(html: str) -> list[tuple[str, str]]:
    parser = ProcedureAccordionParser()
    parser.feed(html)
    sections = []
    for panel_id, parts in parser.sections.items():
        title = parser.titles.get(panel_id)
        body = normalize_markdown("".join(parts))
        if title and body:
            sections.append((title, body))
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


def extract_document(page: RawPage, collection: str = "default") -> Document | None:
    """Extract clean markdown and metadata from a RawPage. Returns None if unusable."""
    if page.status != 200:
        return None

    html = decode_body(page)
    markdown = trafilatura.extract(
        html,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
        favor_precision=True,
    ) or ""
    cleaned_markdown = normalize_markdown(markdown)
    collapsed_sections = extract_collapsed_sections(html)
    cleaned_markdown = merge_collapsed_sections(cleaned_markdown, collapsed_sections)
    if len(cleaned_markdown) < MIN_MARKDOWN_CHARS:
        return None

    meta = trafilatura.extract_metadata(html)
    canonical = canonicalize(page.final_url)
    metadata_title = meta.title.strip() if meta and meta.title else ""
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
