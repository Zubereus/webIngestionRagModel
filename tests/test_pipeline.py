import unittest
from unittest.mock import Mock, patch

from webrag.extract.cleaner import sha256_hex
from webrag.models import Document, RawPage
from webrag.pipeline import IngestionPipeline


class PipelineReindexTests(unittest.TestCase):
    def test_changed_page_replaces_old_jsonl_rows_before_append(self):
        storage = Mock()
        storage.get_page_record.return_value = {
            "content_hash": "old-hash",
            "status": "ready",
            "collection": "default",
        }
        pipeline = IngestionPipeline(storage=storage)
        page = RawPage(
            url="https://example.org/page",
            final_url="https://example.org/page",
            status=200,
            content_type="text/html",
            body=b"<html>Updated</html>",
            fetched_at="2026-01-02T00:00:00+00:00",
        )
        document = Document(
            doc_id=sha256_hex(page.final_url)[:16],
            url=page.url,
            canonical_url=page.final_url,
            domain="example.org",
            title="Updated",
            author=None,
            published_at=None,
            language="en",
            markdown="Updated document content.",
            content_hash="new-hash",
            fetched_at=page.fetched_at,
        )

        with (
            patch("webrag.pipeline.fetch_safe_page", return_value=page),
            patch("webrag.pipeline.extract_document", return_value=document),
            patch("webrag.pipeline.chunk_document", return_value=[]),
        ):
            result = pipeline.ingest_url(page.url, force=True)

        self.assertEqual(result["status"], "success")
        doc_id = sha256_hex(page.final_url)[:16]
        storage.remove_doc_files.assert_called_once_with(doc_id)
        storage.save_raw_snapshot.assert_called_once_with(doc_id, page)
        storage.append_document.assert_called_once_with(document)


if __name__ == "__main__":
    unittest.main()
