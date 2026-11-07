from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RawPage:
    url: str
    final_url: str          # after redirects
    status: int
    content_type: str
    body: bytes
    fetched_at: str         # ISO 8601, UTC


@dataclass(frozen=True)
class PageSpan:
    page: int
    start: int
    end: int
    ocr: bool


@dataclass(frozen=True)
class Document:
    doc_id: str             # sha256(canonical_url)[:16]
    url: str
    canonical_url: str
    domain: str
    title: str
    author: str | None
    published_at: str | None
    language: str | None
    markdown: str
    content_hash: str       # sha256(markdown) to check if page changed
    fetched_at: str
    collection: str = "default"
    page_spans: list[PageSpan] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str           # f"{doc_id}:{ordinal}"
    doc_id: str
    ordinal: int
    text: str               # raw chunk content
    embed_text: str         # context-enriched text for embedding (e.g. Title > Section: text)
    section_path: list[str] # heading hierarchy e.g. ["Introduction", "Architecture"]
    token_count: int
    url: str
    title: str
    fetched_at: str
    collection: str = "default"
    page: int | None = None
    ocr: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
