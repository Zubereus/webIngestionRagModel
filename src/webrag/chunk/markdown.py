import re
from typing import List
from webrag.models import Chunk, Document

HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$")


def approx_token_count(text: str) -> int:
    """Rough estimation of token count (~1.3 tokens per whitespace-separated word)."""
    words = len(text.split())
    return int(words * 1.3)


def count_words(lines: list[str]) -> int:
    return sum(len(line.split()) for line in lines)


def tail_lines(lines: list[str], max_words: int) -> list[str]:
    """Keep whole trailing lines up to the requested overlap size."""
    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        line_words = len(line.split())
        if total + line_words > max_words:
            break
        kept.insert(0, line)
        total += line_words
    return kept


def split_by_words(line: str, max_words: int) -> list[str]:
    """Split an individual line only when it exceeds the chunk size."""
    words = line.split()
    return [
        " ".join(words[index : index + max_words])
        for index in range(0, len(words), max_words)
    ]


def split_long_text(
    text: str, max_words: int = 350, overlap_words: int = 50
) -> list[str]:
    """Split on line boundaries while preserving row and list formatting."""
    if max_words < 1:
        raise ValueError("max_words must be at least 1")
    if overlap_words < 0:
        raise ValueError("overlap_words must not be negative")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [
        piece
        for line in lines
        for piece in split_by_words(line, max_words)
    ]
    chunks: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        line_word_count = len(line.split())
        if current and count_words(current) + line_word_count > max_words:
            chunks.append(current)
            overlap_limit = min(overlap_words, max_words - line_word_count)
            current = tail_lines(current, overlap_limit)
        current.append(line)

    if current:
        chunks.append(current)

    return ["\n".join(chunk) for chunk in chunks] or [text]


def chunk_document(
    doc: Document,
    max_chunk_words: int = 350,
    overlap_words: int = 40,
) -> list[Chunk]:
    """
    Structure-aware chunker that parses markdown headings to track section paths
    and produces context-enriched Chunks.
    """
    lines = doc.markdown.split("\n")
    sections: list[tuple[list[str], str]] = []  # (section_path, content_text)

    current_path: list[tuple[int, str]] = []  # [(level, title)]
    current_lines: list[str] = []

    def flush_section():
        text = "\n".join(current_lines).strip()
        if text:
            path = [item[1] for item in current_path]
            sections.append((path, text))
        current_lines.clear()

    for line in lines:
        heading_match = HEADING_REGEX.match(line.strip())
        if heading_match:
            flush_section()
            level = len(heading_match.group(1))
            heading_title = heading_match.group(2).strip()

            # Pop deeper or equal level headings from path
            while current_path and current_path[-1][0] >= level:
                current_path.pop()

            current_path.append((level, heading_title))
        else:
            current_lines.append(line)

    flush_section()

    chunks: list[Chunk] = []
    ordinal = 0

    for section_path, section_text in sections:
        # If section is small, keep as one chunk; otherwise, split with overlap
        sub_texts = split_long_text(section_text, max_words=max_chunk_words, overlap_words=overlap_words)

        for text in sub_texts:
            breadcrumb = " > ".join(section_path) if section_path else "Overview"
            embed_text = f"Title: {doc.title}\nSection: {breadcrumb}\n\n{text}"

            chunk = Chunk(
                chunk_id=f"{doc.doc_id}:{ordinal}",
                doc_id=doc.doc_id,
                ordinal=ordinal,
                text=text,
                embed_text=embed_text,
                section_path=section_path,
                token_count=approx_token_count(text),
                url=doc.canonical_url,
                title=doc.title,
                fetched_at=doc.fetched_at,
                collection=doc.collection,
            )
            chunks.append(chunk)
            ordinal += 1

    return chunks
