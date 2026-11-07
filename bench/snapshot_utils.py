"""Shared access and matching helpers for the offline snapshot tools."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = ROOT / "bench" / "gold.jsonl"


@dataclass(frozen=True)
class Snapshot:
    url: str
    snapshot_path: str
    title: str
    markdown: str


def extract_snapshot(url: str, snapshot_path: str) -> Snapshot:
    path = Path(snapshot_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"Snapshot not found for {url}: {path}")

    sys.path.insert(0, str(ROOT / "src"))
    from webrag.extract.cleaner import extract_document
    from webrag.models import RawPage

    raw_page = RawPage(
        url=url,
        final_url=url,
        status=200,
        content_type="text/html",
        body=path.read_bytes(),
        fetched_at="2000-01-01T00:00:00+00:00",
    )
    document = extract_document(raw_page)
    if document is None:
        raise ValueError(f"Production extractor returned no document for {url} ({path})")
    return Snapshot(url, str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), document.title, document.markdown)


def load_snapshots() -> list[Snapshot]:
    records = [
        json.loads(line)
        for line in GOLD_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [extract_snapshot(record["url"], record["snapshot"]) for record in records]


def normalized_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def section_regions(markdown: str, section_path_contains: str | None) -> list[tuple[int, int]]:
    if not section_path_contains:
        return [(0, len(markdown))]

    lines = markdown.splitlines(keepends=True)
    regions: list[tuple[int, int]] = []
    offset = 0
    active_start: int | None = None
    active_level: int | None = None
    needle = normalized_text(section_path_contains)

    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line.strip())
        if heading:
            level = len(heading.group(1))
            if active_start is not None and active_level is not None and level <= active_level:
                regions.append((active_start, offset))
                active_start = None
                active_level = None
            if needle in normalized_text(heading.group(2)):
                active_start = offset + len(line)
                active_level = level
        offset += len(line)

    if active_start is not None:
        regions.append((active_start, len(markdown)))
    return regions


def span_offsets(
    markdown: str,
    span: str,
    section_path_contains: str | None = None,
) -> list[tuple[int, int]]:
    parts = span.split()
    if not parts:
        return []
    pattern = re.compile(r"\s+".join(re.escape(part) for part in parts), re.IGNORECASE)
    offsets: list[tuple[int, int]] = []
    for start, end in section_regions(markdown, section_path_contains):
        offsets.extend((start + match.start(), start + match.end()) for match in pattern.finditer(markdown[start:end]))
    return offsets


def span_matches(markdown: str, span: str, section_path_contains: str | None = None) -> bool:
    return bool(span_offsets(markdown, span, section_path_contains))


def spans_from_case(case: dict) -> list[str]:
    if isinstance(case.get("answer_any"), list):
        return [span for span in case["answer_any"] if isinstance(span, str)]
    span = case.get("answer_span")
    return [span] if isinstance(span, str) and span else []


def matching_pages(
    pages: Iterable[Snapshot],
    spans: list[str],
    section_path_contains: str | None = None,
) -> dict[str, tuple[Snapshot, list[str]]]:
    hits: dict[str, tuple[Snapshot, list[str]]] = {}
    for page in pages:
        matched_spans = [
            span
            for span in spans
            if span_matches(page.markdown, span, section_path_contains)
        ]
        if matched_spans:
            hits[page.url] = (page, matched_spans)
    return hits


def fold_accents_with_offsets(text: str) -> tuple[str, list[int]]:
    folded: list[str] = []
    offsets: list[int] = []
    for index, character in enumerate(text):
        value = unicodedata.normalize("NFD", character.casefold())
        value = "".join(char for char in value if unicodedata.category(char) != "Mn")
        value = value.replace("\u0111", "d")
        folded.append(value)
        offsets.extend([index] * len(value))
    return "".join(folded), offsets
