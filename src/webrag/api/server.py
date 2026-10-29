import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from collections import deque
from contextlib import closing
from dataclasses import replace
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import httpx

from webrag.chunk.markdown import chunk_document
from webrag.extract.cleaner import canonicalize, extract_document, sha256_hex
from webrag.fetch.crawler import (
    CrawlFetchError,
    discover_sitemap_urls,
    fetch_page,
    fetch_robots,
    normalize_children,
    normalize_crawl_url,
    should_follow,
    validate_public_host,
)
from webrag.fetch.crawler import CrawlFetchError, fetch_safe_page, validate_public_host
from webrag.index.vectordb import VectorDBManager
from webrag.index.rerank import rerank_chunks, reranker_device
from webrag.pipeline import IngestionPipeline
from webrag.store.catalog import StorageManager

OLLAMA_API_BASE = os.getenv("WEBRAG_OLLAMA_API_BASE", "http://localhost:11434")
RERANKER_ENABLED = os.getenv(
    "WEBRAG_ENABLE_RERANKER", "true"
).strip().casefold() in {"1", "true", "yes", "on"}
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODEL_3_5 = "gemini-3.5-flash"
DEFAULT_GEN_MODEL = GEMINI_MODEL_3_5
GEN_MODEL = os.getenv("WEBRAG_GEN_MODEL", DEFAULT_GEN_MODEL)
GEN_PROFILES = {
    "qwen2.5:1.5b": {
        "timeout_seconds": 90,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "repeat_last_n": 64,
            "num_predict": 400,
        },
    },
    "qwen2.5:3b": {
        "timeout_seconds": 120,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "top_k": 30,
            "min_p": 0.05,
            "repeat_penalty": 1.1,
            "repeat_last_n": 64,
            "num_ctx": 4096,
            "num_predict": 400,
        },
    },
    "qwen3:4b": {
        "timeout_seconds": 150,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "top_k": 30,
            "repeat_penalty": 1.1,
            "repeat_last_n": 64,
            "num_ctx": 4096,
            "num_predict": 400,
        },
    },
    "qwen2.5:7b": {
        "timeout_seconds": 180,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "repeat_last_n": 64,
            "num_predict": 400,
        },
    },
}
GEN_PROFILE = GEN_PROFILES.get(GEN_MODEL, GEN_PROFILES["qwen2.5:3b"])
GEN_TIMEOUT_SECONDS = float(
    os.getenv("WEBRAG_GEN_TIMEOUT_SECONDS", str(GEN_PROFILE["timeout_seconds"]))
)
MODEL_OPTIONS = [
    {"id": "qwen2.5:1.5b", "label": "Qwen 2.5 · 1.5B", "provider": "ollama"},
    {"id": "qwen2.5:3b", "label": "Qwen 2.5 · 3B", "provider": "ollama"},
    {"id": "qwen2.5:7b", "label": "Qwen 2.5 · 7B", "provider": "ollama"},
    {"id": "qwen3:4b", "label": "Qwen 3 · 4B", "provider": "ollama"},
    {"id": GEMINI_MODEL, "label": "Gemini 2.5 Flash", "provider": "gemini"},
    {
        "id": GEMINI_MODEL_3_5,
        "label": "Gemini 3.5 Flash",
        "provider": "gemini",
    },
]

app = FastAPI(title="WebRAG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = StorageManager()
vector_db = VectorDBManager()
pipeline = IngestionPipeline(storage=storage)

# Background subscriber queues for SSE /api/pages/events
page_event_queues: list[asyncio.Queue] = []
store_lock = asyncio.Lock()
NOT_FOUND_TEXT = "Your saved pages don't answer this."
NOT_FOUND_TEXT_VI = "Các trang đã lưu không trả lời được câu hỏi này."
VIETNAMESE_MARKS = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìịỉĩóòỏõọốồổỗộớờởỡợ"
    r"úùụủũứừửữựýỳỵỷỹ]",
    re.IGNORECASE,
)
SMALL_TALK = re.compile(
    r"(?:hi|hello|hey|yo|xin chào|chào|cảm ơn|thanks|thank you|thx"
    r"|who are you|what are you|what is your name|what's your name"
    r"|are you (?:a |an )?(?:gpt|gemini|qwen|llama|ai|bot|model|human)"
    r"|(?:which|what) (?:ai |llm )?model are you(?: (?:using|powered by))?"
    r"|what model (?:do you use|are you using|powers you)"
    r"|(?:what is |what's )?(?:your|ur) "
    r"(?:name|model|version|speed|response time|replies|answers?)"
    r"|response time"
    r"|what can you do|how (?:do|does) (?:you|this|webrag) work"
    r"|bạn là ai|bạn là gì|bạn tên gì)",
    re.IGNORECASE,
)
ACKNOWLEDGEMENT = re.compile(
    r"(?:ok(?:ay)?(?:\s+(?:great|thanks))?|got it(?:\s+thanks)?|understood"
    r"|cool(?:\s+thanks)?|great|nice|sounds good|all right|alright"
    r"|you're welcome|cheers|dạ|vâng|được rồi|cảm ơn)",
    re.IGNORECASE,
)
PAGE_HINTS = re.compile(
    r"\b(?:my|saved|these|those|this|the)\s+(?:saved\s+)?(?:pages?|articles?|links?|docs?|documents?|sources?|papers?|studies?)\b"
    r"|\b(?:saved|library|according to (?:the|my))\b"
    r"|(?<!\w)(?:trang|bài viết|tài liệu|theo như|đã lưu|thư viện)(?!\w)",
    re.IGNORECASE,
)
SUMMARY_QUESTION = re.compile(
    r"\b(?:key points?|main points?|main takeaways|takeaways|overview|"
    r"highlights?|summary|summaries|summari[sz](?:e|es|ed|ing|ation)?)\b"
    r"|(?<!\w)(?:điểm chính|ý chính|tóm tắt|khái quát|nội dung chính|"
    r"các điểm nổi bật)(?!\w)",
    re.IGNORECASE,
)
MIN_DENSE_STRICT = float(os.getenv("WEBRAG_MIN_DENSE_STRICT", "0.40"))
MIN_DENSE_SOFT = float(os.getenv("WEBRAG_MIN_DENSE_SOFT", "0.55"))
MIN_BM25 = float(os.getenv("WEBRAG_MIN_BM25", "6.0"))
MAX_CONTEXT_CHARS = int(os.getenv("WEBRAG_MAX_CONTEXT_CHARS", "5000"))
GEMINI_MAX_CONTEXT_CHARS = int(
    os.getenv("WEBRAG_MAX_CONTEXT_CHARS_GEMINI", "30000")
)
GEMINI_MAX_OUTPUT_TOKENS = int(
    os.getenv("WEBRAG_GEMINI_MAX_OUTPUT_TOKENS", "1500")
)
GEMINI_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
GEMINI_MAX_RETRIES = 2
GEMINI_MAX_RETRY_DELAY_SECONDS = 5.0
CHAT_OPTIONS = {
    "temperature": 0.6,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 300,
}
logger = logging.getLogger(__name__)


async def broadcast_page_event(event_type: str, data: dict[str, Any]):
    for q in list(page_event_queues):
        try:
            await q.put({"event": event_type, "data": data})
        except Exception:
            page_event_queues.remove(q)


# --- Request Models ---

class AddPageRequest(BaseModel):
    url: str
    collection: str = "default"


class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=3, max_length=63)


class CrawlRequest(BaseModel):
    start_url: str
    collection: str = "default"
    max_pages: int = Field(default=25, ge=1, le=500)
    max_depth: int = Field(default=2, ge=0, le=10)
    query_allowlist: set[str] = Field(default_factory=lambda: {"id"})
    allow_paths: list[str] = Field(default_factory=list)
    deny_paths: list[str] = Field(default_factory=list)
    discover_sitemap: bool = True


class AskRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = Field(default_factory=list)
    scope_doc_ids: Optional[list[str]] = None
    collection: str = "default"
    top_k: int = Field(default=5, ge=1, le=10)
    retrieval_mode: Literal["hybrid", "dense"] = "hybrid"
    model: Optional[str] = None


def is_small_talk(question: str) -> bool:
    message = question.strip().rstrip("!?.,").strip()
    message = re.sub(r",\s*", " ", message)
    message = re.sub(r"\s+", " ", message)
    return bool(
        SMALL_TALK.fullmatch(message)
        or ACKNOWLEDGEMENT.fullmatch(message)
    )


def is_explicit_page_question(question: str) -> bool:
    return bool(PAGE_HINTS.search(question))


def not_found_text(question: str) -> str:
    return NOT_FOUND_TEXT_VI if is_vietnamese_text(question) else NOT_FOUND_TEXT


def is_vietnamese_text(text: str) -> bool:
    return bool(VIETNAMESE_MARKS.search(text))


def normalize_collection_name(name: str) -> str:
    trimmed_name = name.strip()
    if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9 _-]{1,61}[a-zA-Z0-9])", trimmed_name):
        raise HTTPException(
            status_code=400,
            detail="Collection names must be 3–63 characters, start and end with a letter or number, and contain only letters, numbers, spaces, hyphens, or underscores.",
        )
    return re.sub(r"[ -]+", "_", trimmed_name).lower()


# --- Page Endpoints ---

@app.get("/api/collections")
def list_collections():
    names = {"default"}
    for collection in vector_db.client.list_collections():
        name = getattr(collection, "name", collection)
        if isinstance(name, str):
            names.add(name)

    with closing(sqlite3.connect(storage.db_path)) as conn:
        rows = conn.execute(
            "SELECT DISTINCT collection FROM pages WHERE collection IS NOT NULL"
        ).fetchall()
    names.update(
        normalize_collection_name(row[0])
        for row in rows
        if isinstance(row[0], str) and row[0].strip()
    )
    return {"collections": sorted(names)}


@app.post("/api/collections", status_code=201)
def create_collection(req: CreateCollectionRequest):
    collection_name = normalize_collection_name(req.name)
    existing_names = {
        getattr(collection, "name", collection)
        for collection in vector_db.client.list_collections()
    }
    existing_names.add("default")
    if collection_name in existing_names:
        raise HTTPException(status_code=409, detail="This collection already exists.")

    vector_db.get_collection(collection_name)
    return {"name": collection_name}


@app.post("/api/pages")
async def add_page(req: AddPageRequest, bg: BackgroundTasks):
    url = req.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid URL format. Must start with http:// or https://")

    canonical = canonicalize(url)
    try:
        await asyncio.to_thread(validate_public_host, canonical)
    except CrawlFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc_id = sha256_hex(canonical)[:16]
    domain = urlparse(canonical).netloc

    existing = storage.get_page_record(canonical)
    if existing and existing.get("status") in {"ready", "extracted", "indexed"}:
        return {
            "doc_id": doc_id,
            "canonical_url": canonical,
            "domain": domain,
            "title": canonical,
            "language": "en",
            "fetched_at": existing.get("fetched_at") or "",
            "chunk_count": 0,
            "status": "ready",
            "collection": existing.get("collection", "default"),
            "duplicate": True,
        }

    # Optimistic initial record
    page_data = {
        "doc_id": doc_id,
        "canonical_url": canonical,
        "domain": domain,
        "title": canonical,
        "language": None,
        "fetched_at": "",
        "chunk_count": 0,
        "status": "queued",
        "collection": req.collection,
    }

    # Process in background
    bg.add_task(run_pipeline_stages, url, req.collection, doc_id, canonical, domain)
    return page_data


async def run_pipeline_stages(url: str, collection: str, doc_id: str, canonical: str, domain: str):
    try:
        # Stage 1: Fetching
        storage.update_status(doc_id, canonical, "fetching", collection=collection)
        await broadcast_page_event("stage", {"doc_id": doc_id, "status": "fetching"})
        raw_page = await asyncio.to_thread(fetch_safe_page, url)

        if raw_page.status != 200:
            error_msg = f"HTTP {raw_page.status}"
            storage.update_status(doc_id, canonical, "failed", error=error_msg, collection=collection)
            await broadcast_page_event("failed", {"doc_id": doc_id, "error": error_msg})
            return

        # Stage 2: Extracting
        storage.update_status(doc_id, canonical, "extracting", collection=collection)
        await broadcast_page_event("stage", {"doc_id": doc_id, "status": "extracting"})
        doc = await asyncio.to_thread(extract_document, raw_page, collection=collection)

        if not doc:
            error_msg = "Couldn't extract readable content"
            storage.update_status(doc_id, canonical, "failed", error=error_msg, collection=collection)
            await broadcast_page_event("failed", {"doc_id": doc_id, "error": error_msg})
            return

        existing = storage.get_page_record(doc.canonical_url)
        if existing and existing.get("content_hash") == doc.content_hash:
            storage.update_status(
                doc_id,
                canonical,
                "ready",
                content_hash=doc.content_hash,
                fetched_at=doc.fetched_at,
                collection=collection,
            )
            await broadcast_page_event(
                "ready",
                {
                    "doc_id": doc_id,
                    "title": doc.title,
                    "chunk_count": 0,
                    "status": "ready",
                    "domain": domain,
                },
            )
            return

        chunks = await asyncio.to_thread(chunk_document, doc)
        async with store_lock:
            await asyncio.to_thread(vector_db.delete_doc, doc_id, collection)
            await asyncio.to_thread(storage.remove_doc_files, doc_id)
            await asyncio.to_thread(storage.save_raw_snapshot, doc_id, raw_page)
            await asyncio.to_thread(storage.append_document, doc)
            await asyncio.to_thread(storage.append_chunks, chunks)
            await asyncio.to_thread(
                vector_db.index_chunks, [chunk.to_dict() for chunk in chunks]
            )

        # Stage 3: Indexing
        storage.update_status(doc_id, canonical, "indexing", content_hash=doc.content_hash, fetched_at=doc.fetched_at, collection=collection)
        await broadcast_page_event("stage", {"doc_id": doc_id, "status": "indexing"})

        # Stage 4: Ready
        storage.update_status(doc_id, canonical, "ready", content_hash=doc.content_hash, fetched_at=doc.fetched_at, collection=collection)
        await broadcast_page_event("ready", {
            "doc_id": doc_id,
            "title": doc.title,
            "chunk_count": len(chunks),
            "status": "ready",
            "domain": domain,
        })
    except Exception as e:
        storage.update_status(doc_id, canonical, "failed", error=str(e), collection=collection)
        await broadcast_page_event("failed", {"doc_id": doc_id, "error": str(e)})


async def crawl_progress(job_id: str, **details: Any) -> None:
    job = storage.get_crawl_job(job_id)
    if job is None:
        return
    await broadcast_page_event(
        "crawl_progress",
        {
            "job_id": job_id,
            "status": job["status"],
            "pages_processed": job["pages_processed"],
            "pages_failed": job["pages_failed"],
            "max_pages": job["max_pages"],
            **details,
        },
    )


async def ingest_crawl_url(
    url: str,
    depth: int,
    collection: str,
    start_host: str,
    robots: Any,
    query_allowlist: set[str],
    allow_paths: list[str],
    deny_paths: list[str],
) -> tuple[list[str], str | None]:
    preliminary_url = canonicalize(url)
    preliminary_id = sha256_hex(preliminary_url)[:16]
    storage.update_status(
        preliminary_id, preliminary_url, "fetching", collection=collection
    )
    await broadcast_page_event(
        "stage",
        {"doc_id": preliminary_id, "status": "fetching", "url": preliminary_url},
    )

    try:
        raw_page, links, canonical_hint = await asyncio.to_thread(
            fetch_page, url, start_host, robots
        )
        canonical_url = canonicalize(raw_page.final_url)
        if canonical_hint:
            hint = canonicalize(canonical_hint)
            if should_follow(hint, start_host, allow_paths, deny_paths):
                canonical_url = hint
        page_for_extraction = replace(raw_page, final_url=canonical_url)
        doc = await asyncio.to_thread(
            extract_document, page_for_extraction, collection=collection
        )
        if doc is None:
            error = "Couldn't extract readable content."
            storage.update_status(
                preliminary_id,
                preliminary_url,
                "failed",
                error=error,
                collection=collection,
            )
            await broadcast_page_event(
                "failed",
                {"doc_id": preliminary_id, "url": preliminary_url, "error": error},
            )
            discovered = normalize_children(
                links, start_host, query_allowlist, allow_paths, deny_paths
            )
            return discovered, error

        doc_id = doc.doc_id
        domain = urlparse(doc.canonical_url).netloc
        if preliminary_id != doc_id:
            with closing(sqlite3.connect(storage.db_path)) as conn:
                conn.execute("DELETE FROM pages WHERE doc_id = ?", (preliminary_id,))
                conn.commit()
        storage.update_status(doc_id, doc.canonical_url, "extracting", collection=collection)
        await broadcast_page_event(
            "stage", {"doc_id": doc_id, "status": "extracting", "url": doc.canonical_url}
        )

        existing = storage.get_page_record(doc.canonical_url)
        if existing and existing.get("content_hash") == doc.content_hash:
            storage.update_status(
                doc_id,
                doc.canonical_url,
                "ready",
                content_hash=doc.content_hash,
                fetched_at=doc.fetched_at,
                collection=collection,
            )
            chunks_found = normalize_children(
                links, start_host, query_allowlist, allow_paths, deny_paths
            ) if depth >= 0 else []
            await broadcast_page_event(
                "ready",
                {"doc_id": doc_id, "title": doc.title, "chunk_count": 0, "status": "ready", "domain": domain},
            )
            return chunks_found, None

        chunks = await asyncio.to_thread(chunk_document, doc)
        storage.update_status(
            doc_id,
            doc.canonical_url,
            "indexing",
            content_hash=doc.content_hash,
            fetched_at=doc.fetched_at,
            collection=collection,
        )
        await broadcast_page_event(
            "stage", {"doc_id": doc_id, "status": "indexing", "url": doc.canonical_url}
        )

        async with store_lock:
            previous_collection = (existing or {}).get("collection") or collection
            await asyncio.to_thread(
                vector_db.delete_doc, doc_id, previous_collection
            )
            await asyncio.to_thread(storage.remove_doc_files, doc_id)
            await asyncio.to_thread(storage.save_raw_snapshot, doc_id, raw_page)
            await asyncio.to_thread(storage.append_document, doc)
            await asyncio.to_thread(storage.append_chunks, chunks)
            await asyncio.to_thread(
                vector_db.index_chunks, [chunk.to_dict() for chunk in chunks]
            )

        storage.update_status(
            doc_id,
            doc.canonical_url,
            "ready",
            content_hash=doc.content_hash,
            fetched_at=doc.fetched_at,
            collection=collection,
        )
        await broadcast_page_event(
            "ready",
            {
                "doc_id": doc_id,
                "title": doc.title,
                "chunk_count": len(chunks),
                "status": "ready",
                "domain": domain,
            },
        )
        discovered = normalize_children(
            links, start_host, query_allowlist, allow_paths, deny_paths
        )
        if canonical_hint and should_follow(
            canonical_hint, start_host, allow_paths, deny_paths
        ):
            canonical_child = normalize_crawl_url(canonical_hint, query_allowlist)
            if canonical_child != preliminary_url:
                discovered.append(canonical_child)
        return list(dict.fromkeys(discovered)), None
    except Exception as exc:
        error = str(exc)
        storage.update_status(
            preliminary_id,
            preliminary_url,
            "failed",
            error=error,
            collection=collection,
        )
        await broadcast_page_event(
            "failed",
            {"doc_id": preliminary_id, "url": preliminary_url, "error": error},
        )
        return [], error


async def run_site_crawl(
    job_id: str,
    request: CrawlRequest,
    start_url: str,
    start_host: str,
) -> None:
    storage.update_crawl_job(job_id, status="running")
    await crawl_progress(job_id, current_url=start_url)
    frontier: deque[tuple[str, int]] = deque([(start_url, 0)])
    seen = {start_url}
    processed = 0
    failed = 0
    try:
        robots = await asyncio.to_thread(fetch_robots, start_url, start_host)
        if request.discover_sitemap and request.max_depth > 0:
            try:
                sitemap_urls = await asyncio.to_thread(
                    discover_sitemap_urls, start_url, start_host, robots
                )
                for sitemap_url in sitemap_urls:
                    normalized = normalize_crawl_url(sitemap_url, request.query_allowlist)
                    if (
                        normalized not in seen
                        and should_follow(
                            normalized, start_host, request.allow_paths, request.deny_paths
                        )
                    ):
                        seen.add(normalized)
                        frontier.append((normalized, 1))
            except CrawlFetchError as exc:
                await crawl_progress(job_id, warning=f"Sitemap discovery failed: {exc}")

        while frontier and processed < request.max_pages:
            job = storage.get_crawl_job(job_id)
            if job is None or job["cancel_requested"]:
                storage.update_crawl_job(job_id, status="cancelled")
                await crawl_progress(job_id)
                return

            batch: list[tuple[str, int]] = []
            while frontier and len(batch) < 2 and processed + len(batch) < request.max_pages:
                batch.append(frontier.popleft())

            outcomes = await asyncio.gather(*[
                ingest_crawl_url(
                    url,
                    depth,
                    request.collection,
                    start_host,
                    robots,
                    request.query_allowlist,
                    request.allow_paths,
                    request.deny_paths,
                )
                for url, depth in batch
            ])
            for (url, depth), (links, error) in zip(batch, outcomes):
                processed += 1
                if error:
                    failed += 1
                if depth < request.max_depth:
                    for link in links:
                        normalized = normalize_crawl_url(link, request.query_allowlist)
                        if (
                            normalized not in seen
                            and should_follow(
                                normalized,
                                start_host,
                                request.allow_paths,
                                request.deny_paths,
                            )
                        ):
                            seen.add(normalized)
                            frontier.append((normalized, depth + 1))
                storage.update_crawl_job(
                    job_id,
                    pages_processed=processed,
                    pages_failed=failed,
                )
                await crawl_progress(
                    job_id,
                    current_url=url,
                    depth=depth,
                    error=error,
                )

        job = storage.get_crawl_job(job_id)
        final_status = "cancelled" if job and job["cancel_requested"] else "completed"
        storage.update_crawl_job(
            job_id,
            status=final_status,
            pages_processed=processed,
            pages_failed=failed,
        )
        await crawl_progress(job_id)
    except Exception as exc:
        storage.update_crawl_job(job_id, status="failed", error=str(exc))
        await crawl_progress(job_id, error=str(exc))


@app.post("/api/crawl", status_code=202)
async def start_crawl(request: CrawlRequest, bg: BackgroundTasks):
    start_url = canonicalize(request.start_url.strip())
    try:
        start_host = await asyncio.to_thread(validate_public_host, start_url)
    except CrawlFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for path in request.allow_paths + request.deny_paths:
        if not path.startswith("/"):
            raise HTTPException(status_code=422, detail="Crawl path rules must start with '/'.")

    job = storage.create_crawl_job(
        start_url,
        request.collection,
        request.max_pages,
        request.max_depth,
    )
    bg.add_task(run_site_crawl, job["job_id"], request, start_url, start_host)
    return job


@app.get("/api/crawl/{job_id}")
def get_crawl_job(job_id: str):
    job = storage.get_crawl_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found.")
    return job


@app.delete("/api/crawl/{job_id}")
def cancel_crawl(job_id: str):
    job = storage.get_crawl_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found.")
    if job["status"] in {"completed", "failed", "cancelled"}:
        return job
    storage.request_crawl_cancel(job_id)
    return {"job_id": job_id, "status": "cancelling"}


@app.get("/api/health")
@app.head("/api/health")
def health_check():
    return {"status": "ok", "model": GEN_MODEL}


@app.get("/api/models")
def list_generation_models():
    gemini_configured = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "default_model": GEN_MODEL,
        "models": [
            {
                **model,
                "available": (
                    gemini_configured if model["provider"] == "gemini" else True
                ),
            }
            for model in MODEL_OPTIONS
        ],
    }


@app.api_route("/api/pages", methods=["GET", "HEAD"])
def list_pages(
    status: Optional[str] = None,
    domain: Optional[str] = None,
    q: Optional[str] = None,
    collection: Optional[str] = None,
):
    with closing(sqlite3.connect(storage.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM pages WHERE 1=1"
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if collection:
            sql += " AND collection = ?"
            params.append(collection)
        sql += " ORDER BY fetched_at DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    # Count chunks per doc_id
    chunk_counts: dict[str, int] = {}
    titles: dict[str, str] = {}
    languages: dict[str, str] = {}
    if storage.documents_file.exists():
        with storage.documents_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                titles[d["doc_id"]] = d.get("title", "")
                languages[d["doc_id"]] = d.get("language") or "en"

    if storage.chunks_file.exists():
        with storage.chunks_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                did = c["doc_id"]
                chunk_counts[did] = chunk_counts.get(did, 0) + 1

    results = []
    for row in rows:
        did = row["doc_id"]
        c_url = row["canonical_url"]
        dom = urlparse(c_url).netloc
        title = titles.get(did, c_url)
        lang = languages.get(did, "en")
        count = chunk_counts.get(did, 0)

        # Filters
        if domain and domain.lower() not in dom.lower():
            continue
        if q:
            q_lower = q.lower()
            if q_lower not in title.lower() and q_lower not in c_url.lower():
                continue

        results.append({
            "doc_id": did,
            "canonical_url": c_url,
            "domain": dom,
            "title": title,
            "language": lang,
            "fetched_at": row.get("fetched_at") or "",
            "chunk_count": count,
            "status": row.get("status") if row.get("status") != "extracted" else "ready",
            "collection": row.get("collection") or "default",
            "error": row.get("error"),
        })

    return results


@app.post("/api/pages/{doc_id}/refetch")
def refetch_page(doc_id: str, bg: BackgroundTasks):
    rec = None
    with closing(sqlite3.connect(storage.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM pages WHERE doc_id = ?", (doc_id,)).fetchone()
        if row:
            rec = dict(row)

    if not rec:
        raise HTTPException(status_code=404, detail="Page record not found")

    url = rec["canonical_url"]
    coll = rec.get("collection", "default")
    dom = urlparse(url).netloc

    bg.add_task(run_pipeline_stages, url, coll, doc_id, url, dom)
    return {"status": "refetching", "doc_id": doc_id}


# --- SSE Page Events ---

@app.get("/api/pages/events")
async def page_events():
    queue = asyncio.Queue()
    page_event_queues.append(queue)

    async def event_generator():
        try:
            while True:
                msg = await queue.get()
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
        except asyncio.CancelledError:
            if queue in page_event_queues:
                page_event_queues.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/pages/{doc_id}")
def get_page_details(doc_id: str):
    doc_match = None
    if storage.documents_file.exists():
        with storage.documents_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                if d["doc_id"] == doc_id:
                    doc_match = d
                    break

    if not doc_match:
        raise HTTPException(status_code=404, detail="Document not found")

    return doc_match


@app.delete("/api/pages/{doc_id}")
def delete_page(doc_id: str):
    with closing(sqlite3.connect(storage.db_path)) as conn:
        row = conn.execute("SELECT collection FROM pages WHERE doc_id = ?", (doc_id,)).fetchone()
        conn.execute("DELETE FROM pages WHERE doc_id = ?", (doc_id,))
        conn.commit()
    if row:
        vector_db.delete_doc(doc_id, row[0] or "default")
    storage.remove_doc_files(doc_id)

    return {"status": "deleted", "doc_id": doc_id}


# --- Chunk Retrieval ---

@app.get("/api/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    target = None
    doc_chunks = []
    if storage.chunks_file.exists():
        with storage.chunks_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                if c["chunk_id"] == chunk_id:
                    target = c
                doc_id = chunk_id.split(":")[0]
                if c["doc_id"] == doc_id:
                    doc_chunks.append(c)

    if not target:
        raise HTTPException(status_code=404, detail="Chunk not found")

    # Sort chunks by ordinal to provide context before and after
    doc_chunks.sort(key=lambda x: x.get("ordinal", 0))
    target_idx = next((i for i, c in enumerate(doc_chunks) if c["chunk_id"] == chunk_id), -1)

    context_before = doc_chunks[target_idx - 1]["text"] if target_idx > 0 else ""
    context_after = doc_chunks[target_idx + 1]["text"] if target_idx != -1 and target_idx < len(doc_chunks) - 1 else ""

    return {
        **target,
        "context_before": context_before,
        "context_after": context_after,
    }


# --- Ask Endpoint (SSE) ---


def find_chunks(
    req: AskRequest, top_k: int | None = None
) -> list[dict[str, Any]]:
    return vector_db.query(
        collection_name=req.collection,
        query_text=req.question,
        n_results=top_k if top_k is not None else req.top_k,
        retrieval_mode=req.retrieval_mode,
        doc_ids=req.scope_doc_ids,
    )


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def display_score(chunk: dict[str, Any]) -> float:
    if chunk.get("dense_score") is not None:
        return float(chunk["dense_score"])
    return float(chunk.get("score") or 0.0)


def is_relevant(chunk: dict[str, Any], wants_pages: bool) -> bool:
    dense_score = chunk.get("dense_score")
    bm25_score = float(chunk.get("bm25_score") or 0.0)
    min_dense = MIN_DENSE_STRICT if wants_pages else MIN_DENSE_SOFT
    return (
        (dense_score is not None and float(dense_score) >= min_dense)
        or bm25_score >= MIN_BM25
    )


def keep_relevant(chunks: list[dict[str, Any]], wants_pages: bool) -> list[dict[str, Any]]:
    return [chunk for chunk in chunks if is_relevant(chunk, wants_pages)]


def pick_mode(wants_pages: bool, chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "chat"
    return "strict" if wants_pages else "soft"


def fit_context_blocks(blocks: list[str], limit: int) -> list[str]:
    kept: list[str] = []
    used = 0
    for block in blocks:
        separator_size = len("\n\n---\n\n") if kept else 0
        available = limit - used - separator_size
        if available <= 0:
            break
        if kept and len(block) > available:
            break
        kept_block = block[:available]
        kept.append(kept_block)
        used += separator_size + len(kept_block)
        if len(kept_block) < len(block):
            break
    return kept


def fit_context(blocks: list[str], limit: int) -> str:
    return "\n\n---\n\n".join(fit_context_blocks(blocks, limit))


def context_limit(provider: str) -> int:
    return GEMINI_MAX_CONTEXT_CHARS if provider == "gemini" else MAX_CONTEXT_CHARS


def clean_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    refusals = {NOT_FOUND_TEXT, NOT_FOUND_TEXT_VI}
    for message in history[-6:]:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if role == "assistant" and content in refusals:
            if cleaned and cleaned[-1]["role"] == "user":
                cleaned.pop()
            continue
        cleaned.append({
            "role": role,
            "content": re.sub(r"\[\d+\]", "", content)[:600],
        })
    return cleaned


def model_identity(tag: str) -> str:
    if tag == GEMINI_MODEL:
        return "Gemini 2.5 Flash"
    if tag == GEMINI_MODEL_3_5:
        return "Gemini 3.5 Flash"
    name, _, size = tag.partition(":")
    family = name[:1].upper() + name[1:]
    return f"{family} {size.split('-')[0].upper()}".strip()


APP_FACTS = (
    "WebRAG: The Reading Room lets the user save webpages and ask questions about them. "
    "It searches saved passages and can answer with numbered citations. Questions about saved "
    "pages take longer because they require retrieval; casual chat skips the search."
)


def chat_prompt(model: str = GEN_MODEL) -> str:
    identity = model_identity(model)
    maker = " from Alibaba Cloud" if model.startswith("qwen") else ""
    model_description = (
        f" (Ollama tag: {model}), an open AI model"
        if model in GEN_PROFILES
        else f" ({model}), a Google AI model"
    )
    location = (
        "locally inside WebRAG: The Reading Room"
        if model in GEN_PROFILES
        else "through Google's Gemini API"
    )
    return (
        f"You are {identity}{model_description}{maker}. "
        f"You run {location}.\n"
        "Be friendly, direct, and usually answer in 1 to 4 sentences. Reply in the user's "
        "language. Never use citations or claim to have searched saved pages for this reply. "
        f'Never say "{NOT_FOUND_TEXT}" in normal conversation. If the user names a different '
        f"model or size, say no and identify yourself as {identity} ({model}). "
        "If unsure, say so instead of guessing.\n\n"
        f"{APP_FACTS}\n\n"
        f'Example: User: are you GPT-4? Assistant: No, I am {identity} ({model}).'
    )


def strict_prompt(not_found: str, model: str = GEN_MODEL) -> str:
    identity = model_identity(model)
    return (
        f"You are {identity}, a careful research assistant inside WebRAG. The user is asking "
        "about saved pages. Use only the numbered reference passages for page facts. Cite each "
        "supported claim with [n]. Reply in the user's language and be concise. If passages "
        f"do not answer, reply exactly: {not_found}. Do not add a sources list."
    )


def is_gemini(model: str) -> bool:
    return model.startswith("gemini-")


def gemini_strict_prompt(not_found: str) -> str:
    return (
        "You answer questions about saved sources using only the numbered passages "
        "provided. Return only a JSON object with boolean `answerable` and string "
        "`answer` fields.\n\n"
        "Rules:\n"
        "- End every factual claim with [n] for the passage or passages that support it.\n"
        "- Copy numbers, durations, fees, form codes, and legal references exactly as "
        "written, with their units. Never round, convert, or merge ranges.\n"
        "- Compare each passage's Procedure and Section with the question. Similar "
        "procedures, jurisdictions, versions, or applicant types may differ. If the "
        "question does not specify which applies and the passages differ, explain each "
        "variant separately with its citation.\n"
        "- Set answerable to true when the passages support a direct or partial answer. "
        "For a partial answer, give only the supported information and clearly identify "
        "what is missing.\n"
        "- Set answerable to false when the passages do not support an answer to the "
        f"question. In that case set answer to exactly: {not_found}\n"
        "- Reply in the language of the question. Lead with the direct answer, then "
        "give relevant conditions or steps. Do not add a sources list or text outside "
        "the JSON object."
    )


def is_summary_question(question: str) -> bool:
    return bool(SUMMARY_QUESTION.search(question))


def soft_prompt(model: str = GEN_MODEL) -> str:
    identity = model_identity(model)
    return (
        f"You are {identity}, a friendly assistant inside WebRAG. Saved passages may help. "
        "If a passage helps, use it and cite [n]. If none helps, ignore them and answer from "
        "your own knowledge without citations; never say the saved pages do not answer. "
        "Reply in the user's language and keep it concise."
    )


def build_system_prompt(
    mode: str, not_found: str, question: str = "", model: str = GEN_MODEL
) -> str:
    if mode == "strict" and is_gemini(model):
        prompt = gemini_strict_prompt(not_found)
        if is_summary_question(question):
            prompt += (
                "\n\nFor broad overview, summary, or key-points questions, provide "
                "a complete synthesis of the major themes in the supplied passages. "
                "Use 5-7 numbered points with 1-3 substantive sentences each, aiming "
                "for 250-400 words when the evidence supports that length. Cite the "
                "passage or passages for every point. Do not stop after the opening "
                "overview or first heading, and do not pad with unsupported claims."
            )
        return prompt

    if mode == "strict":
        prompt = strict_prompt(not_found, model)
    elif mode == "soft":
        prompt = soft_prompt(model)
    else:
        prompt = chat_prompt(model)

    if is_vietnamese_text(question):
        prompt += (
            "\n\nNGÔN NGỮ BẮT BUỘC: Câu hỏi của người dùng bằng tiếng Việt. "
            "Chỉ trả lời bằng tiếng Việt; tuyệt đối không dùng tiếng Trung, "
            "tiếng Indonesia hoặc ngôn ngữ khác. Giữ nguyên tên riêng và mã biểu mẫu."
        )
    else:
        prompt += (
            "\n\nLANGUAGE: Answer only in the same language as the user's question. "
            "Do not switch to Chinese unless the user asks in Chinese."
        )
    if mode == "strict":
        prompt += (
            "\nFor questions about dates, amounts, deadlines, or processing times, "
            "state the exact value and unit given in the reference passages. Do not "
            "replace an exact duration with a rounded or generalized range."
        )
    return prompt


def user_language_suffix(question: str) -> str:
    if is_vietnamese_text(question):
        return "Hãy trả lời hoàn toàn bằng tiếng Việt."
    return "Answer in the same language as the question."


def should_refuse_without_sources(question: str, chunks: list[dict[str, Any]]) -> bool:
    return not is_small_talk(question) and not chunks


def prioritize_qualified_chunks(
    question: str, chunks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    qualifier_match = re.search(r"\(([^)]*)\)", question)
    if not qualifier_match:
        return chunks

    qualifier_terms = set(VectorDBManager._tokens(qualifier_match.group(1)))
    if not qualifier_terms:
        return chunks

    def match_score(chunk: dict[str, Any]) -> float:
        title_terms = set(
            VectorDBManager._tokens(str(chunk.get("metadata", {}).get("title", "")))
        )
        return len(qualifier_terms & title_terms) / len(qualifier_terms)

    return sorted(chunks, key=match_score, reverse=True)


def build_sources(chunks: list[dict[str, Any]]):
    citations, retrieved, context_blocks = [], [], []
    for number, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        score = round(display_score(chunk), 3)
        citations.append({
            "n": number, "chunk_id": chunk["chunk_id"],
            "doc_id": meta.get("doc_id", ""), "title": meta.get("title", ""),
            "url": meta.get("url", ""), "score": score,
        })
        retrieved.append({
            "rank": number, "score": score, "title": meta.get("title", ""),
            "url": meta.get("url", ""), "snippet": chunk["text"][:160].strip(),
            "chunk_id": chunk["chunk_id"],
        })
        context_blocks.append(
            f'<passage id="{number}">\n'
            f"Procedure: {meta.get('title', '')}\n"
            f"Section: {meta.get('section_path') or 'Unknown'}\n"
            f"URL: {meta.get('url', '')}\n"
            f"Content:\n{chunk['text']}\n"
            "</passage>"
        )
    return citations, retrieved, context_blocks


def evidence_excerpt_answer(
    question: str, chunks: list[dict[str, Any]]
) -> str | None:
    asks_duration = bool(
        re.search(
            r"\b(?:thời\s+gian|thời\s+hạn|bao\s+lâu|mất\s+bao\s+lâu|"
            r"how\s+long|duration|processing\s+time|deadline)\b",
            question,
            re.IGNORECASE,
        )
    )
    duration_value_pattern = re.compile(
        r"(?<!\w)\d+(?:[.,]\d+)?"
        r"(?:\s*(?:đến|[-–])\s*\d+(?:[.,]\d+)?)?"
        r"\s*(?:ngày\s+làm\s+việc|ngày|tháng|năm|tuần|giờ|phút|"
        r"seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
        re.IGNORECASE,
    )
    qualifier_match = re.search(r"\(([^)]*)\)", question)
    qualifier_terms = (
        set(VectorDBManager._tokens(qualifier_match.group(1)))
        if qualifier_match
        else set()
    )
    ranked_chunks = []
    for number, chunk in enumerate(chunks, start=1):
        excerpt = chunk["text"].strip()
        if not excerpt:
            continue

        metadata = chunk["metadata"]
        section = str(metadata.get("section_path", ""))
        section_terms = VectorDBManager._tokens(section)
        section_match = VectorDBManager._bm25_scores(
            question,
            [""],
            [{"title": "", "section_path": section}],
        )[0] / max(len(section_terms), 1)

        title_terms = set(VectorDBManager._tokens(str(metadata.get("title", ""))))
        qualifier_match_score = (
            len(qualifier_terms & title_terms) / len(qualifier_terms)
            if qualifier_terms
            else 0.0
        )
        duration_match_score = int(
            asks_duration and bool(duration_value_pattern.search(excerpt))
        )
        ranked_chunks.append(
            (
                qualifier_match_score,
                duration_match_score,
                section_match,
                -number,
                number,
                chunk,
                excerpt,
            )
        )

    if not ranked_chunks:
        return None

    (
        _,
        _,
        _,
        _,
        number,
        chunk,
        excerpt,
    ) = max(ranked_chunks, key=lambda item: item[:4])
    if len(excerpt) > 900:
        duration_match = (
            duration_value_pattern.search(excerpt) if asks_duration else None
        )
        if duration_match:
            start = max(0, duration_match.start() - 300)
            end = min(len(excerpt), start + 900)
            excerpt = (
                ("..." if start else "")
                + excerpt[start:end].strip()
                + ("..." if end < len(excerpt) else "")
            )
        else:
            excerpt = excerpt[:897].rsplit(" ", 1)[0].rstrip() + "..."
    quoted_excerpt = excerpt.replace("\n", "\n> ")
    title = str(chunk["metadata"].get("title", "")).strip()
    section = str(chunk["metadata"].get("section_path", "")).strip()
    source_label = " — ".join(part for part in (title, section) if part)

    if is_vietnamese_text(question):
        intro = "Mình chưa thể xác minh câu trả lời tổng hợp. Đoạn nguồn phù hợp nhất"
        if source_label:
            intro += f" (**{source_label}**)"
        return f"{intro}:\n\n> {quoted_excerpt} [{number}]"

    intro = "I couldn't verify a synthesized answer. The best-matching source excerpt"
    if source_label:
        intro += f" (**{source_label}**)"
    return f"{intro}:\n\n> {quoted_excerpt} [{number}]"


def has_valid_citations(
    answer: str,
    citations: list[dict[str, Any]],
    question: str,
    chunks: list[dict[str, Any]],
) -> bool:
    def normalize_number(number: str) -> str:
        return re.sub(r"\D", "", number).lstrip("0") or "0"

    citation_groups = re.findall(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]", answer)
    if not citation_groups:
        return False
    cited_numbers = {
        int(number)
        for group in citation_groups
        for number in re.findall(r"\d+", group)
    }
    if any(number < 1 or number > len(citations) for number in cited_numbers):
        return False

    qualifier_match = re.search(r"\(([^)]*)\)", question)
    if qualifier_match:
        qualifier_terms = set(VectorDBManager._tokens(qualifier_match.group(1)))
        if qualifier_terms and not all(
            qualifier_terms.issubset(
                set(
                    VectorDBManager._tokens(
                        str(citations[number - 1].get("title", ""))
                    )
                )
            )
            for number in cited_numbers
        ):
            return False

    cited_text = " ".join(chunks[number - 1]["text"] for number in cited_numbers)
    source_numbers = {
        normalize_number(number)
        for number in re.findall(r"\d+(?:[.,]\d+)*", cited_text)
    }
    numeric_claims = re.findall(
        r"(?<!\w)(\d+(?:[.,]\d+)*)"
        r"(?:\s*(?:đến|[-–])\s*(\d+(?:[.,]\d+)*))?"
        r"\s*(?:ngày\s+làm\s+việc|ngày|tháng|năm|giờ|phút|đồng|%)",
        answer,
        re.IGNORECASE,
    )
    source_ranges = {
        (normalize_number(first), normalize_number(second))
        for first, second in re.findall(
            r"(?<!\d)(\d+(?:[.,]\d+)*)\s*(?:đến|[-–])\s*"
            r"(\d+(?:[.,]\d+)*)",
            cited_text,
            re.IGNORECASE,
        )
    }
    for first, second in numeric_claims:
        if second and (
            normalize_number(first),
            normalize_number(second),
        ) not in source_ranges:
            return False
        claimed_numbers = (first, second) if second else (first,)
        if any(
            normalize_number(number) not in source_numbers
            for number in claimed_numbers
        ):
            return False
    return True


@app.post("/api/ask")
async def ask_stream(req: AskRequest):
    model = req.model or GEN_MODEL
    model_option = next(
        (option for option in MODEL_OPTIONS if option["id"] == model), None
    )
    if model_option is None:
        raise HTTPException(status_code=400, detail="Unsupported generation model.")
    provider = model_option["provider"]
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if provider == "gemini" and not gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini is not configured. Set GEMINI_API_KEY on the backend.",
        )
    profile = GEN_PROFILES.get(model, GEN_PROFILES["qwen2.5:3b"])
    timeout_seconds = (
        GEN_TIMEOUT_SECONDS
        if model == GEN_MODEL
        else float(profile["timeout_seconds"])
    )
    model_options = profile["options"]

    async def sse_stream():
        start_time = time.time()
        small_talk = (
            is_small_talk(req.question)
            and not is_explicit_page_question(req.question)
        )
        wants_pages = not small_talk
        not_found = not_found_text(req.question)
        raw_chunks: list[dict[str, Any]] = []
        yield sse("stage", {
            "name": "Searching your pages" if wants_pages else "Preparing answer"
        })

        if wants_pages:
            yield sse("stage", {"name": "Ranking passages"})
            retrieval_top_k = max(req.top_k, 8) if provider == "gemini" else req.top_k
            device = reranker_device(provider) if RERANKER_ENABLED else None
            candidate_count = (
                max(retrieval_top_k, 12) if device else retrieval_top_k
            )
            found = await asyncio.to_thread(
                find_chunks, req, top_k=candidate_count
            )
            relevant = (
                found
                if provider == "gemini" and device
                else keep_relevant(found, wants_pages)
            )
            if relevant and device:
                yield sse("stage", {"name": "Reranking passages"})
                relevant = await asyncio.to_thread(
                    rerank_chunks, req.question, relevant, retrieval_top_k, device
                )
            else:
                if relevant and provider == "gemini":
                    logger.warning(
                        "Skipping BGE reranking because CUDA is unavailable."
                    )
                relevant = relevant[:retrieval_top_k]
            raw_chunks = prioritize_qualified_chunks(
                req.question, relevant
            )

        if wants_pages and should_refuse_without_sources(req.question, raw_chunks):
            yield sse("stage", {"name": "Not found"})
            yield sse("not_found", {"message": not_found})
            yield sse("done", {
                "duration": round(time.time() - start_time, 2),
                "passages_used": 0,
            })
            return

        mode = pick_mode(wants_pages, raw_chunks)
        yield sse("mode", {"mode": mode})

        citations, retrieved, context_blocks = build_sources(raw_chunks)
        if mode != "chat":
            context_blocks = fit_context_blocks(
                context_blocks, context_limit(provider)
            )
            raw_chunks = raw_chunks[:len(context_blocks)]
            citations, _, _ = build_sources(raw_chunks)
            yield sse("citations", citations)
            yield sse("retrieved", retrieved)

        yield sse("stage", {"name": "Writing answer"})
        if mode == "chat":
            user_prompt = (
                f"{req.question}\n\n{user_language_suffix(req.question)}"
            )
        else:
            context = "\n\n---\n\n".join(context_blocks)
            if provider == "gemini":
                user_prompt = (
                    f"REFERENCE CONTEXT:\n{context}\n\n"
                    f"QUESTION: {req.question}\n\nANSWER:"
                )
            else:
                user_prompt = (
                    f"REFERENCE CONTEXT:\n{context}\n\nQUESTION: {req.question}\n\n"
                    f"{user_language_suffix(req.question)} Give exact values and units "
                    "from the passages when answering. If the passages do not contain "
                    "the answer, say that the saved pages do not answer.\n\nANSWER:"
                )

        options = (
            {**model_options, **CHAT_OPTIONS}
            if mode == "chat"
            else model_options.copy()
        )
        if is_vietnamese_text(req.question) and provider != "gemini":
            options["temperature"] = 0
        system_prompt = build_system_prompt(mode, not_found, req.question, model)
        messages = [
            *clean_history(req.history),
            {"role": "user", "content": user_prompt},
        ]
        if provider == "gemini":
            generation_config = {
                "topP": options.get("top_p", 0.9),
                "topK": options.get("top_k", 30),
                "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
            }
            if mode == "strict":
                generation_config["responseMimeType"] = "application/json"
                generation_config["responseSchema"] = {
                    "type": "OBJECT",
                    "properties": {
                        "answerable": {"type": "BOOLEAN"},
                        "answer": {"type": "STRING"},
                    },
                    "required": ["answerable", "answer"],
                }
            if not model.startswith("gemini-3"):
                generation_config["temperature"] = options["temperature"]
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [
                    {
                        "role": "model" if message["role"] == "assistant" else "user",
                        "parts": [{"text": message["content"]}],
                    }
                    for message in messages
                ],
                "generationConfig": generation_config,
            }
            request_url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:streamGenerateContent?alt=sse"
            )
            request_headers = {"x-goog-api-key": gemini_api_key}
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
                "stream": True,
                "keep_alive": "30m",
                "options": options,
            }
            if model.startswith("qwen3:"):
                payload["think"] = False
            request_url = f"{OLLAMA_API_BASE}/api/chat"
            request_headers = {}

        answer_parts: list[str] = []
        refused = False
        prompt_tokens = 0
        finish_reason = None
        for attempt in range(GEMINI_MAX_RETRIES + 1 if provider == "gemini" else 1):
            answer_parts.clear()
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    async with client.stream(
                        "POST",
                        request_url,
                        json=payload,
                        headers=request_headers,
                    ) as resp:
                        try:
                            resp.raise_for_status()
                        except httpx.HTTPStatusError:
                            await resp.aread()
                            raise
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            if provider == "gemini":
                                if not line.startswith("data: "):
                                    continue
                                chunk_json = json.loads(line.removeprefix("data: "))
                                candidates = chunk_json.get("candidates", [])
                                if candidates:
                                    finish_reason = candidates[0].get(
                                        "finishReason", finish_reason
                                    )
                                parts = (
                                    (candidates or [{}])[0]
                                    .get("content", {})
                                    .get("parts", [])
                                )
                                token = "".join(
                                    part.get("text", "")
                                    for part in parts
                                    if isinstance(part.get("text"), str)
                                )
                                prompt_tokens = chunk_json.get(
                                    "usageMetadata", {}
                                ).get("promptTokenCount", prompt_tokens)
                            else:
                                chunk_json = json.loads(line)
                                token = chunk_json.get("message", {}).get("content", "")
                                if chunk_json.get("done"):
                                    prompt_tokens = chunk_json.get(
                                        "prompt_eval_count", 0
                                    )
                            if token:
                                answer_parts.append(token)
                                if mode == "chat":
                                    yield sse("token", {"text": token})
                break
            except httpx.HTTPStatusError as e:
                retryable = (
                    provider == "gemini"
                    and e.response.status_code in GEMINI_TRANSIENT_STATUS_CODES
                    and attempt < GEMINI_MAX_RETRIES
                    and not answer_parts
                )
                if retryable:
                    retry_after = e.response.headers.get("Retry-After", "")
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = float(2**attempt)
                    delay = min(max(delay, 0.0), GEMINI_MAX_RETRY_DELAY_SECONDS)
                    logger.warning(
                        "Gemini returned transient HTTP %d; retrying attempt %d/%d "
                        "after %.1fs",
                        e.response.status_code,
                        attempt + 1,
                        GEMINI_MAX_RETRIES,
                        delay,
                    )
                    yield sse(
                        "stage",
                        {"name": f"Gemini is busy; retrying ({attempt + 1}/{GEMINI_MAX_RETRIES})"},
                    )
                    await asyncio.sleep(delay)
                    continue

                response_body = e.response.text
                try:
                    error_data = e.response.json()
                except json.JSONDecodeError:
                    error_data = {}
                detail = (
                    error_data.get("error", {}).get("message")
                    if isinstance(error_data, dict)
                    and isinstance(error_data.get("error"), dict)
                    else None
                )
                if not isinstance(detail, str) or not detail:
                    detail = response_body[:1000] or e.response.reason_phrase
                provider_name = "Gemini API" if provider == "gemini" else "Ollama"
                yield sse(
                    "error",
                    {
                        "message": (
                            f"{provider_name} returned HTTP {e.response.status_code}: "
                            f"{detail}"
                        )
                    },
                )
                return
            except httpx.RequestError as e:
                provider_name = "Gemini API" if provider == "gemini" else "Ollama"
                yield sse(
                    "error",
                    {
                        "message": (
                            f"Could not connect to {provider_name} "
                            f"({type(e).__name__}): {str(e) or 'no additional details'}. "
                            "Check the backend's internet connection, DNS, firewall, "
                            "and proxy settings."
                        )
                    },
                )
                return
            except Exception as e:
                yield sse("error", {"message": str(e)})
                return

        answer = "".join(answer_parts).strip()
        structured_output_valid = True
        if provider == "gemini" and mode == "strict":
            try:
                structured_answer = json.loads(answer)
            except json.JSONDecodeError:
                structured_answer = None

            if (
                not isinstance(structured_answer, dict)
                or not isinstance(structured_answer.get("answerable"), bool)
                or not isinstance(structured_answer.get("answer"), str)
            ):
                logger.warning(
                    "Gemini returned an invalid strict structured response model=%s",
                    model,
                )
                structured_output_valid = False
                answer = ""
            else:
                refused = not structured_answer["answerable"]
                answer = structured_answer["answer"].strip()
        else:
            normalized_answer = answer.casefold()
            refusal_prefixes = (
                not_found.rstrip(".").casefold(),
                not_found.casefold(),
            )
            refused = any(
                normalized_answer.startswith(prefix)
                for prefix in refusal_prefixes
            )
        citations_valid = (
            mode != "strict"
            or (
                structured_output_valid
                and has_valid_citations(answer, citations, req.question, raw_chunks)
            )
        )
        if provider == "gemini":
            logger.info(
                "Gemini generation completed model=%s finish_reason=%s "
                "answer_chars=%d prompt_tokens=%d refused=%s citations_valid=%s",
                model,
                finish_reason,
                len(answer),
                prompt_tokens,
                refused,
                citations_valid,
            )
        if mode == "strict" and refused:
            yield sse("not_found", {"message": not_found})
        elif mode == "strict" and not citations_valid:
            fallback = evidence_excerpt_answer(req.question, raw_chunks)
            if fallback is not None:
                yield sse("token", {"text": fallback})
            else:
                yield sse("not_found", {"message": not_found})
        elif mode == "strict" and answer:
            yield sse("token", {"text": answer})
        yield sse("done", {
            "duration": round(time.time() - start_time, 2),
            "passages_used": len(raw_chunks),
            "pages_used": len({c["doc_id"] for c in citations}),
            "prompt_tokens": prompt_tokens,
        })

    return StreamingResponse(sse_stream(), media_type="text/event-stream")


# --- Library Clear & Export ---

@app.get("/api/export")
def export_dataset():
    if not storage.chunks_file.exists():
        raise HTTPException(status_code=404, detail="No chunks dataset found")
    return FileResponse(
        storage.chunks_file,
        media_type="application/jsonlines",
        filename="webrag_chunks.jsonl",
    )


@app.delete("/api/library/clear")
def clear_library():
    with closing(sqlite3.connect(storage.db_path)) as conn:
        conn.execute("DELETE FROM pages;")
        conn.commit()

    vector_db.delete_all()
    for path in (storage.documents_file, storage.chunks_file):
        if path.exists():
            path.unlink()
    for snapshot in storage.raw_dir.glob("*.html"):
        snapshot.unlink()

    return {"status": "cleared"}
