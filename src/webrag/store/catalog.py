import json
from contextlib import closing
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from webrag.models import Chunk, Document, RawPage

DEFAULT_DATA_DIR = Path("data")


class StorageManager:
    def __init__(self, base_dir: Path | str = DEFAULT_DATA_DIR):
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "raw"
        self.documents_file = self.base_dir / "documents.jsonl"
        self.chunks_file = self.base_dir / "chunks.jsonl"
        self.db_path = self.base_dir / "catalog.db"

        self._ensure_dirs()
        self._init_db()

    def _ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pages (
                    doc_id        TEXT PRIMARY KEY,
                    canonical_url TEXT NOT NULL UNIQUE,
                    status        TEXT NOT NULL,
                    content_hash  TEXT,
                    fetched_at    TEXT,
                    error         TEXT,
                    collection    TEXT DEFAULT 'default'
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_jobs (
                    job_id TEXT PRIMARY KEY,
                    start_url TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    status TEXT NOT NULL,
                    max_pages INTEGER NOT NULL,
                    max_depth INTEGER NOT NULL,
                    pages_processed INTEGER NOT NULL DEFAULT 0,
                    pages_failed INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            # Add collection column if existing table lacks it
            try:
                conn.execute("ALTER TABLE pages ADD COLUMN collection TEXT DEFAULT 'default';")
            except sqlite3.OperationalError:
                pass  # already exists
            conn.execute(
                """
                UPDATE crawl_jobs
                SET status='failed',
                    error=COALESCE(error, 'Server restarted before the crawl completed.'),
                    updated_at=?
                WHERE status IN ('queued', 'running');
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()

    def create_crawl_job(
        self,
        start_url: str,
        collection: str,
        max_pages: int,
        max_depth: int,
    ) -> dict[str, Any]:
        job_id = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO crawl_jobs
                    (job_id, start_url, collection, status, max_pages, max_depth, created_at, updated_at)
                VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
                """,
                (job_id, start_url, collection, max_pages, max_depth, now, now),
            )
            conn.commit()
        return self.get_crawl_job(job_id) or {}

    def get_crawl_job(self, job_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM crawl_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_crawl_job(self, job_id: str, **fields: Any) -> None:
        allowed = {
            "status", "pages_processed", "pages_failed", "cancel_requested", "error"
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [job_id]
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                f"UPDATE crawl_jobs SET {assignments} WHERE job_id = ?",
                values,
            )
            conn.commit()

    def request_crawl_cancel(self, job_id: str) -> bool:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute(
                """
                UPDATE crawl_jobs
                SET cancel_requested = 1, updated_at = ?
                WHERE job_id = ? AND status IN ('queued', 'running')
                """,
                (datetime.now(timezone.utc).isoformat(), job_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_page_record(self, canonical_url: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM pages WHERE canonical_url = ?", (canonical_url,)
            ).fetchone()
            return dict(row) if row else None

    def update_status(
        self,
        doc_id: str,
        canonical_url: str,
        status: str,
        content_hash: str | None = None,
        fetched_at: str | None = None,
        error: str | None = None,
        collection: str = "default",
    ) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO pages (doc_id, canonical_url, status, content_hash, fetched_at, error, collection)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    status=excluded.status,
                    content_hash=COALESCE(excluded.content_hash, pages.content_hash),
                    fetched_at=COALESCE(excluded.fetched_at, pages.fetched_at),
                    error=excluded.error,
                    collection=excluded.collection;
                """,
                (doc_id, canonical_url, status, content_hash, fetched_at, error, collection),
            )
            conn.commit()

    def save_raw_snapshot(self, doc_id: str, page: RawPage) -> Path:
        file_path = self.raw_dir / f"{doc_id}.html"
        file_path.write_bytes(page.body)
        return file_path

    def append_document(self, doc: Document) -> None:
        with self.documents_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")

    def append_chunks(self, chunks: list[Chunk]) -> None:
        with self.chunks_file.open("a", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

    def remove_doc_files(self, doc_id: str) -> None:
        for path in (self.documents_file, self.chunks_file):
            self._rewrite_without(path, doc_id)
        snapshot = self.raw_dir / f"{doc_id}.html"
        if snapshot.exists():
            snapshot.unlink()

    @staticmethod
    def _rewrite_without(path: Path, doc_id: str) -> None:
        if not path.exists():
            return
        kept = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("doc_id") != doc_id:
                kept.append(line)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
        temp.replace(path)
