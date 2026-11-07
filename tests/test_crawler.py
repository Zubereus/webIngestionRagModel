import asyncio
import tempfile
import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from webrag.fetch.crawler import (
    CrawlFetchError,
    normalize_crawl_url,
    should_follow,
    validate_public_host,
)
from webrag.store.catalog import StorageManager


class CrawlerUrlTests(unittest.TestCase):
    def test_normalize_keeps_allowlisted_query_and_strips_tracking(self):
        url = normalize_crawl_url(
            "https://example.org/a/?id=42&utm_source=mail&page=3&filter=x",
            {"id"},
        )
        self.assertEqual(url, "https://example.org/a?id=42")

    def test_normalize_keeps_allowed_procedure_and_category_queries(self):
        first = normalize_crawl_url(
            "https://example.org/bothutuc/tthc?matt=121796&linh_vuc=QL_XUAT_NHAP_CANH&page=2",
            {"id", "matt", "linh_vuc", "page"},
        )
        second = normalize_crawl_url(
            "https://example.org/bothutuc/tthc?matt=121936&linh_vuc=QL_XUAT_NHAP_CANH&page=2",
            {"id", "matt", "linh_vuc", "page"},
        )
        self.assertEqual(
            first,
            "https://example.org/bothutuc/tthc?linh_vuc=QL_XUAT_NHAP_CANH&matt=121796&page=2",
        )
        self.assertNotEqual(first, second)

    def test_same_host_and_path_rules_are_enforced(self):
        self.assertTrue(
            should_follow("https://example.org/docs/one", "example.org", ["/docs"])
        )
        self.assertFalse(
            should_follow("https://other.example/docs/one", "example.org", ["/docs"])
        )
        self.assertFalse(
            should_follow(
                "https://example.org/logout", "example.org", deny_paths=["/logout"]
            )
        )

    def test_private_literal_address_is_rejected(self):
        with self.assertRaises(CrawlFetchError):
            validate_public_host("http://127.0.0.1:8000/")

    def test_single_page_safe_fetch_rejects_private_addresses(self):
        from webrag.fetch.crawler import fetch_safe_page

        with self.assertRaises(CrawlFetchError):
            fetch_safe_page("http://127.0.0.1:11434/")

    def test_add_page_endpoint_rejects_private_addresses(self):
        from fastapi import HTTPException

        from webrag.api import server

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                server.add_page(
                    server.AddPageRequest(url="http://127.0.0.1:11434/"),
                    Mock(),
                )
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_dns_results_containing_private_addresses_are_rejected(self):
        answers = [
            (2, 1, 6, "", ("93.184.216.34", 80)),
            (2, 1, 6, "", ("10.0.0.5", 80)),
        ]
        with patch("webrag.fetch.crawler.socket.getaddrinfo", return_value=answers):
            with self.assertRaises(CrawlFetchError):
                validate_public_host("https://example.org/")

    def test_safe_get_retries_server_errors_and_honors_retry_after(self):
        from webrag.fetch.crawler import _safe_get

        class FakeResponse:
            def __init__(self, status_code, headers=None, body=b""):
                self.status_code = status_code
                self.headers = headers or {}
                self.url = "https://example.org/page"
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def iter_bytes(self):
                yield self.body

        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.stream.side_effect = [
            FakeResponse(503, {"Retry-After": "2"}),
            FakeResponse(200, {"content-type": "text/html"}, b"ok"),
        ]
        with (
            patch("webrag.fetch.crawler.httpx.Client", return_value=client),
            patch("webrag.fetch.crawler.validate_public_host", return_value="example.org"),
            patch("webrag.fetch.crawler._wait_for_host"),
            patch("webrag.fetch.crawler.time.sleep") as sleep,
        ):
            result = _safe_get("https://example.org/page", "example.org", "text/html")

        self.assertEqual(result, (200, "text/html", b"ok", "https://example.org/page"))
        self.assertEqual(client.stream.call_count, 2)
        sleep.assert_called_once_with(2.0)

    def test_safe_get_does_not_retry_client_errors(self):
        from webrag.fetch.crawler import _safe_get

        class FakeResponse:
            status_code = 404
            headers = {"content-type": "text/html"}
            url = "https://example.org/missing"

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def iter_bytes(self):
                yield b"missing"

        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.stream.return_value = FakeResponse()
        with (
            patch("webrag.fetch.crawler.httpx.Client", return_value=client),
            patch("webrag.fetch.crawler.validate_public_host", return_value="example.org"),
            patch("webrag.fetch.crawler._wait_for_host"),
        ):
            result = _safe_get("https://example.org/missing", "example.org", "text/html")

        self.assertEqual(result[0], 404)
        client.stream.assert_called_once()

    def test_safe_get_caps_large_retry_after(self):
        from webrag.fetch.crawler import _safe_get

        class FakeResponse:
            def __init__(self, status_code, headers=None, body=b""):
                self.status_code = status_code
                self.headers = headers or {}
                self.url = "https://example.org/page"
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def iter_bytes(self):
                yield self.body

        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.stream.side_effect = [
            FakeResponse(429, {"Retry-After": "86400"}),
            FakeResponse(200, {"content-type": "text/html"}, b"ok"),
        ]
        with (
            patch("webrag.fetch.crawler.httpx.Client", return_value=client),
            patch("webrag.fetch.crawler.validate_public_host", return_value="example.org"),
            patch("webrag.fetch.crawler._host_request_slot"),
            patch("webrag.fetch.crawler.time.sleep") as sleep,
        ):
            result = _safe_get("https://example.org/page", "example.org", "text/html")

        self.assertEqual(result[0], 200)
        sleep.assert_called_once_with(60.0)
        self.assertEqual(client.stream.call_count, 2)

    def test_safe_get_retries_timeouts(self):
        import httpx

        from webrag.fetch.crawler import _safe_get

        class FakeResponse:
            status_code = 200
            headers = {"content-type": "text/html"}
            url = "https://example.org/page"

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def iter_bytes(self):
                yield b"ok"

        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.stream.side_effect = [httpx.ReadTimeout("timed out"), FakeResponse()]
        with (
            patch("webrag.fetch.crawler.httpx.Client", return_value=client),
            patch("webrag.fetch.crawler.validate_public_host", return_value="example.org"),
            patch("webrag.fetch.crawler._host_request_slot"),
            patch("webrag.fetch.crawler.time.sleep") as sleep,
        ):
            result = _safe_get("https://example.org/page", "example.org", "text/html")

        self.assertEqual(result[0], 200)
        client.stream.assert_called()
        self.assertEqual(client.stream.call_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_host_pacing_waits_since_previous_request_completion(self):
        from webrag.fetch import crawler

        host = "pacing-test.example.org"
        crawler._next_host_request.pop(host, None)
        with (
            patch(
                "webrag.fetch.crawler.time.monotonic",
                side_effect=[10.0, 10.5, 10.75, 11.5],
            ),
            patch("webrag.fetch.crawler.time.sleep") as sleep,
        ):
            with crawler._host_request_slot(host, 1.0):
                pass
            with crawler._host_request_slot(host, 1.0):
                pass

        sleep.assert_called_once_with(0.75)
        crawler._next_host_request.pop(host, None)
        crawler._host_request_locks.pop(host, None)

    def test_retry_after_is_capped(self):
        from webrag.fetch.crawler import MAX_RETRY_DELAY_SECONDS, _retry_delay

        self.assertEqual(_retry_delay("86400", 0), MAX_RETRY_DELAY_SECONDS)


class PdfFetchTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, status_code, headers, body=b"", url="https://example.org/page"):
            self.status_code = status_code
            self.headers = headers
            self.body = body
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_bytes(self):
            yield self.body

    @staticmethod
    def fake_client(response):
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.stream.return_value = response
        return client

    def test_single_page_fetch_accepts_pdf_and_keeps_pdf_type(self):
        from webrag.fetch import crawler
        from webrag.fetch.crawler import fetch_safe_page

        pdf_body = b"%PDF-1.7 fixture"
        client = self.fake_client(
            self.FakeResponse(200, {"content-type": "application/pdf"}, pdf_body)
        )
        with (
            patch.object(crawler.httpx, "Client", return_value=client),
            patch.object(crawler, "validate_public_host", return_value="example.org"),
            patch.object(crawler, "_host_request_slot", return_value=nullcontext()),
        ):
            page = fetch_safe_page("https://example.org/page")

        self.assertEqual(page.content_type, "application/pdf")
        self.assertEqual(page.body, pdf_body)

    def test_pdf_response_uses_configured_limit_not_html_limit(self):
        from webrag.fetch import crawler
        from webrag.fetch.crawler import fetch_safe_page

        client = self.fake_client(
            self.FakeResponse(
                200,
                {"content-type": "application/pdf"},
                b"%PDF-oversized",
            )
        )
        with (
            patch.object(crawler.httpx, "Client", return_value=client),
            patch.object(crawler, "validate_public_host", return_value="example.org"),
            patch.object(crawler, "_host_request_slot", return_value=nullcontext()),
            patch.object(crawler, "MAX_PDF_BYTES", 5),
        ):
            with self.assertRaisesRegex(CrawlFetchError, "5-byte limit"):
                fetch_safe_page("https://example.org/page")

    def test_redirect_to_private_host_is_rejected_before_requesting_it(self):
        from webrag.fetch import crawler
        from webrag.fetch.crawler import fetch_safe_page

        client = self.fake_client(
            self.FakeResponse(302, {"location": "http://127.0.0.1/private"})
        )

        def validate(url):
            if "127.0.0.1" in url:
                raise CrawlFetchError(
                    "Local and private network addresses cannot be crawled."
                )
            return "example.org"

        with (
            patch.object(crawler.httpx, "Client", return_value=client),
            patch.object(crawler, "validate_public_host", side_effect=validate),
            patch.object(crawler, "_host_request_slot", return_value=nullcontext()),
        ):
            with self.assertRaisesRegex(CrawlFetchError, "private"):
                fetch_safe_page("https://example.org/page")

        client.stream.assert_called_once()

    def test_crawler_accepts_pdf_after_robots_check_without_binary_links(self):
        from webrag.fetch import crawler
        from webrag.fetch.crawler import fetch_page

        robots = Mock()
        robots.can_fetch.return_value = True
        with patch.object(
            crawler,
            "_safe_get",
            return_value=(
                200,
                "application/pdf",
                b"%PDF-1.7 fixture",
                "https://example.org/page",
            ),
        ) as safe_get:
            page, links, canonical = fetch_page(
                "https://example.org/page",
                "example.org",
                robots,
            )

        robots.can_fetch.assert_called_once()
        safe_get.assert_called_once()
        self.assertEqual(page.content_type, "application/pdf")
        self.assertEqual(links, [])
        self.assertIsNone(canonical)

    def test_html_fetch_behavior_is_unchanged(self):
        from webrag.fetch import crawler
        from webrag.fetch.crawler import fetch_safe_page

        html_body = b"<html><body>existing HTML</body></html>"
        client = self.fake_client(
            self.FakeResponse(
                200,
                {"content-type": "text/html; charset=utf-8"},
                html_body,
            )
        )
        with (
            patch.object(crawler.httpx, "Client", return_value=client),
            patch.object(crawler, "validate_public_host", return_value="example.org"),
            patch.object(crawler, "_host_request_slot", return_value=nullcontext()),
        ):
            page = fetch_safe_page("https://example.org/page")

        self.assertEqual(page.content_type, "text/html")
        self.assertEqual(page.body, html_body)

    def test_script_content_type_is_not_fetched_as_a_document(self):
        from webrag.fetch import crawler
        from webrag.fetch.crawler import fetch_safe_page

        client = self.fake_client(
            self.FakeResponse(
                200,
                {"content-type": "application/javascript"},
                b"script body",
            )
        )
        with (
            patch.object(crawler.httpx, "Client", return_value=client),
            patch.object(crawler, "validate_public_host", return_value="example.org"),
            patch.object(crawler, "_host_request_slot", return_value=nullcontext()),
        ):
            with self.assertRaisesRegex(CrawlFetchError, "unsupported content type"):
                fetch_safe_page("https://example.org/page")


class CrawlJobStorageTests(unittest.TestCase):
    def test_create_and_cancel_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = StorageManager(Path(temp_dir))
            job = storage.create_crawl_job(
                "https://example.org/", "default", max_pages=25, max_depth=2
            )
            self.assertEqual(job["status"], "queued")
            self.assertTrue(storage.request_crawl_cancel(job["job_id"]))
            self.assertEqual(storage.get_crawl_job(job["job_id"])["cancel_requested"], 1)

    def test_raw_snapshots_keep_the_source_file_extension(self):
        from webrag.models import RawPage

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = StorageManager(Path(temp_dir))
            pdf_page = RawPage(
                url="https://example.org/guide.pdf",
                final_url="https://example.org/guide.pdf",
                status=200,
                content_type="application/pdf",
                body=b"%PDF-1.7",
                fetched_at="2026-01-01T00:00:00+00:00",
            )

            snapshot = storage.save_raw_snapshot("doc-1", pdf_page)
            storage.remove_doc_files("doc-1")

        self.assertEqual(snapshot.suffix, ".pdf")
        self.assertFalse(snapshot.exists())

    def test_bounded_crawl_processes_start_and_discovered_page(self):
        from webrag.api import server
        from webrag.models import Document, RawPage

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = StorageManager(Path(temp_dir))
            request = server.CrawlRequest(
                start_url="https://example.org/start",
                max_pages=2,
                max_depth=1,
                discover_sitemap=False,
            )
            job = storage.create_crawl_job(
                request.start_url,
                request.collection,
                request.max_pages,
                request.max_depth,
            )
            def fetch_page(url, _host, _robots):
                links = ["https://example.org/next"] if url.endswith("/start") else []
                raw_page = RawPage(
                    url=url,
                    final_url=url,
                    status=200,
                    content_type="text/html",
                    body=b"<html></html>",
                    fetched_at="2026-01-01T00:00:00+00:00",
                )
                return raw_page, links, None

            def extract_document(page, collection):
                if page.url.endswith("/start"):
                    return None
                canonical = page.final_url
                doc_id = server.sha256_hex(canonical)[:16]
                return Document(
                    doc_id=doc_id,
                    url=page.url,
                    canonical_url=canonical,
                    domain="example.org",
                    title=canonical,
                    author=None,
                    published_at=None,
                    language="en",
                    markdown="A test document.",
                    content_hash=server.sha256_hex(canonical),
                    fetched_at=page.fetched_at,
                    collection=collection,
                )

            fake_vector_db = Mock()
            with ExitStack() as stack:
                stack.enter_context(patch.object(server, "storage", storage))
                stack.enter_context(patch.object(server, "vector_db", fake_vector_db))
                stack.enter_context(patch.object(server, "store_lock", asyncio.Lock()))
                stack.enter_context(
                    patch.object(server, "broadcast_page_event", AsyncMock())
                )
                stack.enter_context(
                    patch.object(server, "fetch_robots", return_value=object())
                )
                stack.enter_context(
                    patch.object(server, "fetch_page", side_effect=fetch_page)
                )
                stack.enter_context(
                    patch.object(server, "extract_document", side_effect=extract_document)
                )
                stack.enter_context(
                    patch.object(server, "chunk_document", return_value=[])
                )
                asyncio.run(
                    server.run_site_crawl(
                        job["job_id"], request, request.start_url, "example.org"
                    )
                )

            finished = storage.get_crawl_job(job["job_id"])
            self.assertEqual(finished["status"], "completed")
            self.assertEqual(finished["pages_processed"], 2)
            self.assertEqual(finished["pages_failed"], 1)
            self.assertEqual(
                storage.get_page_record("https://example.org/start")["status"],
                "failed",
            )
            self.assertEqual(
                storage.get_page_record("https://example.org/next")["status"],
                "ready",
            )
            fake_vector_db.replace_doc.assert_called_once_with(
                server.sha256_hex("https://example.org/next")[:16],
                request.collection,
                [],
            )


class PageReindexTests(unittest.TestCase):
    def test_unchanged_page_does_not_rechunk_or_reembed(self):
        from webrag.api import server

        storage = Mock()
        storage.get_page_record.return_value = {"content_hash": "unchanged"}
        vector_db = Mock()
        document = Mock(
            canonical_url="https://example.org/page",
            content_hash="unchanged",
            fetched_at="2026-01-01T00:00:00+00:00",
            title="Example page",
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(server, "storage", storage))
            stack.enter_context(patch.object(server, "vector_db", vector_db))
            stack.enter_context(
                patch.object(server, "fetch_safe_page", return_value=object())
            )
            stack.enter_context(
                patch.object(server, "extract_document", return_value=document)
            )
            chunk_document = stack.enter_context(
                patch.object(server, "chunk_document")
            )
            stack.enter_context(
                patch.object(server, "broadcast_page_event", AsyncMock())
            )
            asyncio.run(
                server.run_pipeline_stages(
                    "https://example.org/page",
                    "default",
                    "page-id",
                    "https://example.org/page",
                    "example.org",
                )
            )

        chunk_document.assert_not_called()
        vector_db.replace_doc.assert_not_called()
        vector_db.delete_doc.assert_not_called()
        vector_db.index_chunks.assert_not_called()

    def test_unchanged_crawl_page_skips_embedding(self):
        from webrag.api import server
        from webrag.models import Document, RawPage
        from webrag.store.catalog import StorageManager

        url = "https://example.org/page"
        page = RawPage(
            url=url,
            final_url=url,
            status=200,
            content_type="text/html",
            body=b"<html>same page</html>",
            fetched_at="2026-01-02T00:00:00+00:00",
        )
        document = Document(
            doc_id=server.sha256_hex(url)[:16],
            url=url,
            canonical_url=url,
            domain="example.org",
            title="Same page",
            author=None,
            published_at=None,
            language="en",
            markdown="Unchanged document.",
            content_hash="unchanged",
            fetched_at=page.fetched_at,
        )
        vector_db = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = StorageManager(Path(temp_dir))
            storage.update_status(
                document.doc_id,
                url,
                "ready",
                content_hash="unchanged",
            )
            with ExitStack() as stack:
                stack.enter_context(patch.object(server, "storage", storage))
                stack.enter_context(patch.object(server, "vector_db", vector_db))
                stack.enter_context(
                    patch.object(server, "fetch_page", return_value=(page, [], None))
                )
                stack.enter_context(
                    patch.object(server, "extract_document", return_value=document)
                )
                chunk_document = stack.enter_context(
                    patch.object(server, "chunk_document")
                )
                stack.enter_context(
                    patch.object(server, "broadcast_page_event", AsyncMock())
                )
                result = asyncio.run(
                    server.ingest_crawl_url(
                        url,
                        0,
                        "default",
                        "example.org",
                        object(),
                        {"id"},
                        [],
                        [],
                    )
                )

        self.assertEqual(result, ([], None))
        chunk_document.assert_not_called()
        vector_db.replace_doc.assert_not_called()
        vector_db.index_chunks.assert_not_called()

    def test_embedding_failure_marks_page_failed_and_keeps_old_chunks(self):
        import chromadb
        from chromadb.config import Settings

        from webrag.api import server
        from webrag.index.vectordb import VectorDBManager
        from webrag.models import Chunk, Document, RawPage

        url = "https://example.org/page"
        old_chunk = Chunk(
            chunk_id="page-id:0",
            doc_id="page-id",
            ordinal=0,
            text="old content",
            embed_text="old content",
            section_path=[],
            token_count=2,
            url=url,
            title="Example page",
            fetched_at="2026-01-01T00:00:00+00:00",
        )
        new_chunk = Chunk(
            chunk_id="page-id:0",
            doc_id="page-id",
            ordinal=0,
            text="new content",
            embed_text="new content",
            section_path=[],
            token_count=2,
            url=url,
            title="Example page",
            fetched_at="2026-01-02T00:00:00+00:00",
        )
        raw_page = RawPage(
            url=url,
            final_url=url,
            status=200,
            content_type="text/html",
            body=b"<html>new content</html>",
            fetched_at=new_chunk.fetched_at,
        )
        document = Document(
            doc_id="page-id",
            url=url,
            canonical_url=url,
            domain="example.org",
            title="Example page",
            author=None,
            published_at=None,
            language="en",
            markdown="new content",
            content_hash="new-hash",
            fetched_at=new_chunk.fetched_at,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = StorageManager(Path(temp_dir))
            storage.update_status(
                "page-id",
                url,
                "ready",
                content_hash="old-hash",
            )
            storage.append_chunks([old_chunk])
            storage.save_raw_snapshot(
                "page-id",
                RawPage(
                    url=url,
                    final_url=url,
                    status=200,
                    content_type="text/html",
                    body=b"<html>old content</html>",
                    fetched_at=old_chunk.fetched_at,
                ),
            )
            vector_db = object.__new__(VectorDBManager)
            vector_db.client = chromadb.EphemeralClient(
                settings=Settings(allow_reset=True)
            )
            vector_db.client.reset()
            vector_db.embedding_cache_path = Path(temp_dir) / "embedding-cache.sqlite3"
            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.1, 0.2]],
            ):
                vector_db.index_chunks([old_chunk.to_dict()])

            with ExitStack() as stack:
                stack.enter_context(patch.object(server, "storage", storage))
                stack.enter_context(patch.object(server, "vector_db", vector_db))
                stack.enter_context(patch.object(server, "store_lock", asyncio.Lock()))
                stack.enter_context(
                    patch.object(server, "fetch_safe_page", return_value=raw_page)
                )
                stack.enter_context(
                    patch.object(server, "extract_document", return_value=document)
                )
                stack.enter_context(
                    patch.object(server, "chunk_document", return_value=[new_chunk])
                )
                stack.enter_context(
                    patch.object(server, "broadcast_page_event", AsyncMock())
                )
                stack.enter_context(
                    patch(
                        "webrag.index.vectordb.get_embeddings_batch",
                        side_effect=RuntimeError("embedding failed"),
                    )
                )
                asyncio.run(
                    server.run_pipeline_stages(
                        url,
                        "default",
                        "page-id",
                        url,
                        "example.org",
                    )
                )

            indexed = vector_db.get_collection("default").get(
                where={"doc_id": "page-id"},
                include=["documents"],
            )
            page_record = storage.get_page_record(url)
            stored_chunks = storage.chunks_file.read_text(encoding="utf-8")
            stored_snapshot = (storage.raw_dir / "page-id.html").read_bytes()

        self.assertEqual(indexed["ids"], ["page-id:0"])
        self.assertEqual(indexed["documents"], ["old content"])
        self.assertEqual(page_record["status"], "failed")
        self.assertEqual(page_record["content_hash"], "old-hash")
        self.assertIn('"text": "old content"', stored_chunks)
        self.assertEqual(stored_snapshot, b"<html>old content</html>")


if __name__ == "__main__":
    unittest.main()
