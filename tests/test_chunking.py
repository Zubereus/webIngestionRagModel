import logging
import os
import unittest
from unittest.mock import patch

from webrag.chunk.markdown import (
    DEFAULT_TOKEN_CAP,
    _reset_tokenizer_cache,
    chunk_document,
    conservative_token_count,
    count_tokens,
    enforce_token_cap,
    get_tokenizer,
    split_line_by_tokens,
    split_long_text,
)
from webrag.models import Document


def make_test_document(
    doc_id: str,
    title: str,
    markdown: str,
    url: str = "https://example.org/test",
    collection: str = "default",
) -> Document:
    return Document(
        doc_id=doc_id,
        url=url,
        canonical_url=url,
        domain="example.org",
        title=title,
        author=None,
        published_at=None,
        language=None,
        markdown=markdown,
        content_hash="test_hash_" + doc_id,
        fetched_at="2026-01-01T00:00:00+00:00",
        collection=collection,
    )


class SplitLongTextTests(unittest.TestCase):
    def test_preserves_table_and_list_line_boundaries(self):
        text = (
            "Hình thức nộp | Thời hạn giải quyết\n"
            "Trực tiếp | 08 Ngày làm việc\n"
            "Trực tuyến | 08 Ngày làm việc\n"
            "- Gửi hồ sơ qua bưu chính"
        )

        chunks = split_long_text(text, max_words=30, overlap_words=0)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)
        self.assertIn("Trực tiếp | 08 Ngày làm việc\nTrực tuyến", chunks[0])

    def test_splits_oversized_lines_and_retains_whole_line_overlap(self):
        text = (
            "Header one two\n"
            "Row A B C D\n"
            "Row E F G H\n"
            "A very long line with enough words to exceed a small chunk size"
        )

        chunks = split_long_text(text, max_words=7, overlap_words=2)

        self.assertGreater(len(chunks), 1)
        self.assertIn("Row A B C D", "\n".join(chunks))
        self.assertIn("A very long line with enough words", "\n".join(chunks))
        for chunk in chunks:
            self.assertLessEqual(len(chunk.split()), 7)

    def test_rejects_non_positive_chunk_size(self):
        with self.assertRaisesRegex(ValueError, "max_words"):
            split_long_text("some text", max_words=0)


class TokenCapChunkingTests(unittest.TestCase):
    def setUp(self):
        _reset_tokenizer_cache()

    def tearDown(self):
        _reset_tokenizer_cache()

    def test_default_token_cap_is_400(self):
        self.assertEqual(DEFAULT_TOKEN_CAP, 400)

    def test_splits_oversized_chunk_on_line_boundaries(self):
        lines = [f"Line {i}: This is a sample sentence with several words." for i in range(10)]
        text = "\n".join(lines)
        chunks = enforce_token_cap(text, max_tokens=50)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(count_tokens(chunk), 50)
            for line in chunk.splitlines():
                self.assertIn(line, lines)

    def test_splits_single_line_over_cap_by_tokens(self):
        single_line = "Word " * 200
        chunks = enforce_token_cap(single_line, max_tokens=50)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(count_tokens(chunk), 50)

    def test_chunk_document_enforces_default_hard_cap(self):
        long_paragraph = "This is a detailed analysis of neural retrieval architectures. " * 80
        doc = make_test_document(
            doc_id="testdoc1",
            title="Test Doc",
            markdown=f"# Heading 1\n\n{long_paragraph}",
        )
        chunks = chunk_document(doc)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(count_tokens(chunk.text), 400)
            self.assertEqual(chunk.token_count, count_tokens(chunk.text))

    def test_chunk_document_configurable_via_parameter(self):
        text = "FastAPI is a modern, fast web framework for building APIs with Python. " * 30
        doc = make_test_document(
            doc_id="testdoc2",
            title="FastAPI Doc",
            markdown=f"## Overview\n\n{text}",
        )
        chunks = chunk_document(doc, max_tokens=80)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(count_tokens(chunk.text), 80)

    def test_chunk_document_configurable_via_env_var(self):
        text = "Vector databases index embeddings for similarity search across passages. " * 30
        doc = make_test_document(
            doc_id="testdoc3",
            title="Vector DB",
            markdown=f"## Indexing\n\n{text}",
        )
        with patch.dict(os.environ, {"WEBRAG_MAX_CHUNK_TOKENS": "75"}):
            chunks = chunk_document(doc)
            self.assertGreater(len(chunks), 1)
            for chunk in chunks:
                self.assertLessEqual(count_tokens(chunk.text), 75)

    def test_fallback_to_conservative_estimate_and_logs_one_warning(self):
        _reset_tokenizer_cache()
        with (
            patch("transformers.AutoTokenizer.from_pretrained", side_effect=ImportError("No transformers")),
            self.assertLogs("webrag.chunk.markdown", level="WARNING") as log_cm,
        ):
            tok = get_tokenizer()
            self.assertIsNone(tok)
            # Call multiple times to verify only one warning is logged
            _ = count_tokens("sample text")
            _ = enforce_token_cap("line 1\nline 2", max_tokens=50)

            # Exactly one warning was emitted
            warning_messages = [
                record.getMessage()
                for record in log_cm.records
                if "bge-m3 tokenizer is unavailable" in record.getMessage()
            ]
            self.assertEqual(len(warning_messages), 1)

    def test_split_line_by_tokens_fallback_without_tokenizer(self):
        long_line = "alpha beta gamma delta epsilon zeta eta theta iota kappa " * 15
        with patch("webrag.chunk.markdown.get_tokenizer", return_value=None):
            pieces = split_line_by_tokens(long_line, max_tokens=30, tokenizer=None)
            self.assertGreater(len(pieces), 1)
            for piece in pieces:
                self.assertLessEqual(conservative_token_count(piece), 30)

    def test_backward_compatibility_existing_callers(self):
        doc = make_test_document(
            doc_id="compat1",
            title="Compatibility Test",
            markdown="### Section One\n\nFirst paragraph.\n\n### Section Two\n\nSecond paragraph.",
        )
        # Calling with doc only (backward compatibility)
        chunks = chunk_document(doc)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].section_path, ["Section One"])
        self.assertEqual(chunks[1].section_path, ["Section Two"])

        # Calling with max_chunk_words and overlap_words positional args
        chunks_pos = chunk_document(doc, 150, 40)
        self.assertEqual(len(chunks_pos), 2)


if __name__ == "__main__":
    unittest.main()
