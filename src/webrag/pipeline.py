from typing import Any
from webrag.chunk.markdown import chunk_document
from webrag.extract.cleaner import canonicalize, extract_document, sha256_hex
from webrag.fetch.crawler import fetch_safe_page
from webrag.models import Document
from webrag.store.catalog import StorageManager


class IngestionPipeline:
    def __init__(self, storage: StorageManager | None = None):
        self.storage = storage or StorageManager()

    def ingest_url(self, url: str, collection: str = "default", force: bool = False) -> dict[str, Any]:
        """
        Ingest a single URL through Fetch -> Extract -> Chunk -> Store.
        """
        canonical_url = canonicalize(url)
        doc_id = sha256_hex(canonical_url)[:16]

        # Check existing record in catalog
        existing = self.storage.get_page_record(canonical_url)
        if existing and not force and existing.get("status") in {"extracted", "indexed"}:
            return {
                "status": "skipped",
                "doc_id": doc_id,
                "url": url,
                "canonical_url": canonical_url,
                "collection": existing.get("collection", "default"),
                "reason": "URL already processed with status: " + existing.get("status"),
            }

        # 1. Fetch
        try:
            self.storage.update_status(
                doc_id=doc_id,
                canonical_url=canonical_url,
                status="fetching",
                collection=collection,
            )
            raw_page = fetch_safe_page(url)
        except Exception as e:
            self.storage.update_status(
                doc_id=doc_id,
                canonical_url=canonical_url,
                status="failed",
                error=f"Fetch error: {str(e)}",
                collection=collection,
            )
            return {
                "status": "failed",
                "doc_id": doc_id,
                "url": url,
                "collection": collection,
                "error": f"Failed to fetch: {e}",
            }

        if raw_page.status != 200:
            self.storage.update_status(
                doc_id=doc_id,
                canonical_url=canonical_url,
                status="failed",
                error=f"HTTP status code {raw_page.status}",
                collection=collection,
            )
            return {
                "status": "failed",
                "doc_id": doc_id,
                "url": url,
                "collection": collection,
                "error": f"HTTP {raw_page.status}",
            }

        # 2. Extract
        doc: Document | None = extract_document(raw_page, collection=collection)
        if doc is None:
            self.storage.update_status(
                doc_id=doc_id,
                canonical_url=canonical_url,
                status="failed",
                error="Extraction yielded no usable content",
                collection=collection,
            )
            return {
                "status": "failed",
                "doc_id": doc_id,
                "url": url,
                "collection": collection,
                "error": "Could not extract usable content (page too short, empty, or paywalled)",
            }

        # Check if content has changed based on hash
        if existing and existing.get("content_hash") == doc.content_hash and not force:
            self.storage.update_status(
                doc_id=doc_id,
                canonical_url=canonical_url,
                status="extracted",
                content_hash=doc.content_hash,
                fetched_at=doc.fetched_at,
                collection=collection,
            )
            return {
                "status": "skipped",
                "doc_id": doc_id,
                "url": url,
                "collection": collection,
                "reason": "Content hash unchanged since last ingest",
            }

        # Replace this document's stored rows before writing its refreshed chunks.
        if existing:
            self.storage.remove_doc_files(doc_id)

        # 3. Store raw snapshot
        self.storage.save_raw_snapshot(doc_id, raw_page)

        # 4. Chunk
        chunks = chunk_document(doc)

        # 5. Store processed document & chunks
        self.storage.append_document(doc)
        self.storage.append_chunks(chunks)

        # 6. Update catalog status
        self.storage.update_status(
            doc_id=doc_id,
            canonical_url=canonical_url,
            status="extracted",
            content_hash=doc.content_hash,
            fetched_at=doc.fetched_at,
            collection=collection,
        )

        return {
            "status": "success",
            "doc_id": doc_id,
            "url": doc.url,
            "canonical_url": doc.canonical_url,
            "collection": collection,
            "title": doc.title,
            "chunks_count": len(chunks),
            "markdown_length": len(doc.markdown),
        }
