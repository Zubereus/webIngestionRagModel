import logging
import math
import os
import re
from typing import Any, List, Optional
from webrag.models import Chunk, Document, PageSpan

logger = logging.getLogger(__name__)

HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$")
DEFAULT_TOKEN_CAP = 400
TOKENIZER_NAME = "BAAI/bge-m3"

_TOKENIZER = None
_TOKENIZER_TRIED = False
_WARNED_TOKENIZER = False


def _reset_tokenizer_cache() -> None:
    """Reset cached tokenizer state (primarily for unit testing fallback behavior)."""
    global _TOKENIZER, _TOKENIZER_TRIED, _WARNED_TOKENIZER
    _TOKENIZER = None
    _TOKENIZER_TRIED = False
    _WARNED_TOKENIZER = False


def get_tokenizer() -> Any:
    """Lazily load and cache the BAAI/bge-m3 tokenizer.

    If unavailable, logs exactly one warning and returns None.
    """
    global _TOKENIZER, _TOKENIZER_TRIED, _WARNED_TOKENIZER
    if not _TOKENIZER_TRIED:
        _TOKENIZER_TRIED = True
        try:
            from transformers import AutoTokenizer

            try:
                _TOKENIZER = AutoTokenizer.from_pretrained(
                    TOKENIZER_NAME,
                    local_files_only=True,
                )
            except Exception:
                _TOKENIZER = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
        except Exception:
            _TOKENIZER = None

    if _TOKENIZER is None and not _WARNED_TOKENIZER:
        _WARNED_TOKENIZER = True
        logger.warning(
            "bge-m3 tokenizer is unavailable; falling back to conservative token estimate."
        )

    return _TOKENIZER


def conservative_token_count(text: str) -> int:
    """Conservative token estimate when tokenizer is unavailable.

    Overestimates token counts to ensure chunks do not breach the target cap.
    """
    words = len(text.split())
    return max(int(words * 1.5), (len(text) + 2) // 3)


def count_tokens(text: str, tokenizer: Any = None) -> int:
    """Count tokens in text using bge-m3 tokenizer or conservative estimate."""
    tok = tokenizer or get_tokenizer()
    if tok is not None:
        return len(tok.encode(text, add_special_tokens=False))
    return conservative_token_count(text)


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


def split_line_by_tokens(
    line: str, max_tokens: int, tokenizer: Any = None
) -> list[str]:
    """Split an individual oversized line directly by token slices."""
    tok = tokenizer or get_tokenizer()
    if tok is not None:
        tokens = tok.encode(line, add_special_tokens=False)
        if len(tokens) <= max_tokens:
            return [line]
        pieces: list[str] = []
        idx = 0
        total = len(tokens)
        while idx < total:
            take = min(max_tokens, total - idx)
            sub_tokens = tokens[idx : idx + take]
            decoded = tok.decode(sub_tokens, skip_special_tokens=True).strip()
            while (
                take > 1
                and len(tok.encode(decoded, add_special_tokens=False)) > max_tokens
            ):
                take -= 1
                sub_tokens = tokens[idx : idx + take]
                decoded = tok.decode(sub_tokens, skip_special_tokens=True).strip()
            if decoded:
                pieces.append(decoded)
            idx += take
        return pieces or [line]
    else:
        if conservative_token_count(line) <= max_tokens:
            return [line]
        words = line.split()
        pieces: list[str] = []
        cur_words: list[str] = []
        for word in words:
            candidate = " ".join(cur_words + [word])
            if cur_words and conservative_token_count(candidate) > max_tokens:
                pieces.append(" ".join(cur_words))
                cur_words = [word]
            elif conservative_token_count(word) > max_tokens:
                if cur_words:
                    pieces.append(" ".join(cur_words))
                    cur_words = []
                step = max(1, max_tokens * 2)
                for c_idx in range(0, len(word), step):
                    piece = word[c_idx : c_idx + step]
                    if piece:
                        pieces.append(piece)
            else:
                cur_words.append(word)
        if cur_words:
            pieces.append(" ".join(cur_words))
        return pieces or [line]


def enforce_token_cap(
    text: str, max_tokens: int = DEFAULT_TOKEN_CAP, tokenizer: Any = None
) -> list[str]:
    """Ensure a chunk adheres to the hard token cap.

    Splits further on line boundaries, and splits any single line over the cap by tokens.
    """
    if count_tokens(text, tokenizer=tokenizer) <= max_tokens:
        return [text]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return [text]

    expanded_lines: list[str] = []
    for line in lines:
        if count_tokens(line, tokenizer=tokenizer) > max_tokens:
            expanded_lines.extend(
                split_line_by_tokens(line, max_tokens, tokenizer=tokenizer)
            )
        else:
            expanded_lines.append(line)

    chunks: list[str] = []
    current_lines: list[str] = []

    for line in expanded_lines:
        if not current_lines:
            current_lines.append(line)
            continue
        candidate = "\n".join(current_lines + [line])
        if count_tokens(candidate, tokenizer=tokenizer) <= max_tokens:
            current_lines.append(line)
        else:
            chunks.append("\n".join(current_lines))
            current_lines = [line]

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks


def resolve_token_cap(
    max_tokens: int | None = None,
    max_chunk_tokens: int | None = None,
) -> int:
    """Resolve token cap from parameters or environment variable, defaulting to 400."""
    if max_tokens is not None:
        cap = max_tokens
    elif max_chunk_tokens is not None:
        cap = max_chunk_tokens
    else:
        env_val = os.getenv("WEBRAG_MAX_CHUNK_TOKENS") or os.getenv("WEBRAG_MAX_TOKENS")
        if env_val:
            try:
                cap = int(env_val)
            except ValueError:
                cap = DEFAULT_TOKEN_CAP
        else:
            cap = DEFAULT_TOKEN_CAP
    if cap < 1:
        raise ValueError("max_tokens must be at least 1")
    return cap


def chunk_document(
    doc: Document,
    max_chunk_words: int = 350,
    overlap_words: int = 40,
    max_tokens: int | None = None,
    max_chunk_tokens: int | None = None,
    tokenizer: Any = None,
) -> list[Chunk]:
    """Structure-aware chunker that parses markdown headings to track section paths,

    produces context-enriched Chunks, and enforces a hard token cap on chunk bodies.
    """
    token_cap = resolve_token_cap(
        max_tokens=max_tokens, max_chunk_tokens=max_chunk_tokens
    )
    tok = tokenizer or get_tokenizer()

    sections: list[tuple[list[str], str, int | None, bool | None]] = []

    current_path: list[tuple[int, str]] = []  # [(level, title)]
    current_lines: list[str] = []

    def flush_section(page: PageSpan | None):
        text = "\n".join(current_lines).strip()
        if text:
            path = [item[1] for item in current_path]
            sections.append(
                (path, text, page.page if page else None, page.ocr if page else None)
            )
        current_lines.clear()

    pages = doc.page_spans or [None]
    for page in pages:
        page_text = (
            doc.markdown[page.start : page.end] if page else doc.markdown
        )
        for line in page_text.split("\n"):
            heading_match = HEADING_REGEX.match(line.strip())
            if heading_match:
                flush_section(page)
                level = len(heading_match.group(1))
                heading_title = heading_match.group(2).strip()

                # Pop deeper or equal level headings from path
                while current_path and current_path[-1][0] >= level:
                    current_path.pop()

                current_path.append((level, heading_title))
            else:
                current_lines.append(line)
        flush_section(page)

    chunks: list[Chunk] = []
    ordinal = 0

    for section_path, section_text, page_number, used_ocr in sections:
        # Step 1: existing word-based split
        sub_texts = split_long_text(
            section_text, max_words=max_chunk_words, overlap_words=overlap_words
        )

        # Step 2: enforce hard token cap on body
        capped_texts: list[str] = []
        for text in sub_texts:
            capped_texts.extend(
                enforce_token_cap(text, max_tokens=token_cap, tokenizer=tok)
            )

        for text in capped_texts:
            breadcrumb = " > ".join(section_path) if section_path else "Overview"
            embed_text = f"Title: {doc.title}\nSection: {breadcrumb}\n\n{text}"

            chunk = Chunk(
                chunk_id=f"{doc.doc_id}:{ordinal}",
                doc_id=doc.doc_id,
                ordinal=ordinal,
                text=text,
                embed_text=embed_text,
                section_path=section_path,
                token_count=count_tokens(text, tokenizer=tok),
                url=doc.canonical_url,
                title=doc.title,
                fetched_at=doc.fetched_at,
                collection=doc.collection,
                page=page_number,
                ocr=used_ocr,
            )
            chunks.append(chunk)
            ordinal += 1

    return chunks
