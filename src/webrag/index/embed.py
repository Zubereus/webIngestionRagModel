from collections import Counter
from collections.abc import Callable
from contextlib import closing
import hashlib
import logging
import os
import sqlite3
import struct
from pathlib import Path
from collections.abc import Callable
from typing import Literal

import httpx

OLLAMA_API_BASE = "http://localhost:11434"
DEFAULT_EMBED_MODEL = os.getenv("WEBRAG_EMBED_MODEL", "bge-m3:latest")
EMBEDDING_BATCH_SIZE = 16
logger = logging.getLogger(__name__)
MODEL_PREFIXES = {
    "nomic-embed-text": {
        "document": "search_document: ",
        "query": "search_query: ",
    },
    "qwen3-embedding": {
        "query": (
            "Instruct: Given a search query, retrieve relevant passages that answer "
            "the query\nQuery: "
        ),
    },
}


def embedding_cache_path(chroma_dir: Path | str | None = None) -> Path:
    """Return a cache database path adjacent to the configured Chroma directory."""
    if chroma_dir is None:
        chroma_dir = os.getenv(
            "WEBRAG_CHROMA_DIR", str(Path("data") / "chroma_bge_m3")
        )
    directory = Path(chroma_dir)
    return directory.parent / f"{directory.name}_embedding_cache.sqlite3"


EMBEDDING_CACHE_PATH = embedding_cache_path()


def add_prefix(
    text: str, model: str, kind: Literal["document", "query"]
) -> str:
    """Apply a model-specific task prefix when the embedding model requires one."""
    prefixes = MODEL_PREFIXES.get(model.split(":", maxsplit=1)[0], {})
    return prefixes.get(kind, "") + text


def _embedding_cache_key(model: str, text: str) -> str:
    return hashlib.sha256(
        model.encode("utf-8") + text.encode("utf-8")
    ).hexdigest()


def _connect_embedding_cache(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            cache_key TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            vector BLOB NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS model_dimensions (
            model TEXT PRIMARY KEY,
            dimension INTEGER NOT NULL
        )
        """
    )
    return connection


def _load_cached_embeddings(
    path: Path, model: str, cache_keys: list[str]
) -> tuple[dict[str, list[float]], int | None]:
    cached: dict[str, list[float]] = {}
    with closing(_connect_embedding_cache(path)) as connection:
        expected_row = connection.execute(
            "SELECT dimension FROM model_dimensions WHERE model = ?", (model,)
        ).fetchone()
        expected_dimension = expected_row[0] if expected_row else None
        if expected_dimension is None:
            return cached, None

        for start in range(0, len(cache_keys), 500):
            batch_keys = cache_keys[start : start + 500]
            placeholders = ",".join("?" for _ in batch_keys)
            rows = connection.execute(
                f"""
                SELECT cache_key, dimension, vector FROM embeddings
                WHERE model = ? AND cache_key IN ({placeholders})
                """,
                [model, *batch_keys],
            )
            for cache_key, dimension, vector_blob in rows:
                if (
                    dimension != expected_dimension
                    or len(vector_blob) != dimension * 4
                ):
                    continue
                cached[cache_key] = list(
                    struct.unpack(f"<{dimension}f", vector_blob)
                )
    return cached, expected_dimension


def _store_cached_embeddings(
    path: Path,
    model: str,
    embeddings: dict[str, list[float]],
    expected_dimension: int | None,
) -> None:
    if not embeddings:
        return
    dimension = len(next(iter(embeddings.values())))
    with closing(_connect_embedding_cache(path)) as connection, connection:
        stored_dimension = connection.execute(
            "SELECT dimension FROM model_dimensions WHERE model = ?", (model,)
        ).fetchone()
        if stored_dimension is not None and stored_dimension[0] != dimension:
            raise RuntimeError(
                f"Embedding dimension for {model!r} changed from "
                f"{stored_dimension[0]} to {dimension}; clear the embedding cache "
                "after updating a model under the same tag."
            )
        if expected_dimension is not None and expected_dimension != dimension:
            raise RuntimeError(
                f"Ollama returned {dimension}-dimension embeddings for {model!r}; "
                f"the cache expects {expected_dimension}."
            )
        connection.execute(
            "INSERT OR IGNORE INTO model_dimensions (model, dimension) VALUES (?, ?)",
            (model, dimension),
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO embeddings
                (cache_key, model, dimension, vector)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    cache_key,
                    model,
                    dimension,
                    struct.pack(f"<{dimension}f", *vector),
                )
                for cache_key, vector in embeddings.items()
            ],
        )


def get_embedding(
    text: str,
    model: str = DEFAULT_EMBED_MODEL,
    api_base: str = OLLAMA_API_BASE,
    timeout: float = 30.0,
) -> list[float]:
    """Get vector embedding for a single text using Ollama."""
    url = f"{api_base}/api/embeddings"
    payload = {"model": model, "prompt": add_prefix(text, model, "query")}
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["embedding"]


def get_embeddings_batch(
    texts: list[str],
    model: str = DEFAULT_EMBED_MODEL,
    api_base: str = OLLAMA_API_BASE,
    timeout: float = 60.0,
    *,
    cache_path: Path | str | None = None,
    cache_stats: dict[str, int] | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> list[list[float]]:
    """Get document embeddings from SQLite cache and bounded Ollama batches."""
    if not texts:
        if cache_stats is not None:
            cache_stats.update(hits=0, misses=0, total=0)
        return []

    prefixed_texts = [add_prefix(text, model, "document") for text in texts]
    cache_keys = [
        _embedding_cache_key(model, text) for text in prefixed_texts
    ]
    cache_key_counts = Counter(cache_keys)
    cache_file = Path(cache_path) if cache_path is not None else EMBEDDING_CACHE_PATH
    cached, expected_dimension = _load_cached_embeddings(
        cache_file, model, list(dict.fromkeys(cache_keys))
    )
    hits = sum(count for key, count in cache_key_counts.items() if key in cached)
    if progress_callback is not None and hits:
        progress_callback(hits)

    missing_texts: dict[str, str] = {}
    for key, text in zip(cache_keys, prefixed_texts):
        if key not in cached:
            missing_texts.setdefault(key, text)

    fetched: dict[str, list[float]] = {}
    missing_items = list(missing_texts.items())
    if missing_items:
        url = f"{api_base}/api/embed"
        with httpx.Client(timeout=timeout) as client:
            for start in range(0, len(missing_items), EMBEDDING_BATCH_SIZE):
                batch_items = missing_items[start : start + EMBEDDING_BATCH_SIZE]
                batch_keys = [key for key, _ in batch_items]
                batch_texts = [text for _, text in batch_items]
                response = client.post(
                    url, json={"model": model, "input": batch_texts}
                )
                response.raise_for_status()
                batch_embeddings = response.json().get("embeddings")
                if (
                    not isinstance(batch_embeddings, list)
                    or len(batch_embeddings) != len(batch_texts)
                ):
                    raise RuntimeError(
                        "Ollama returned an unexpected number of embeddings."
                    )
                for key, vector in zip(batch_keys, batch_embeddings):
                    float_vector = [float(value) for value in vector]
                    if (
                        expected_dimension is not None
                        and len(float_vector) != expected_dimension
                    ):
                        raise RuntimeError(
                            f"Ollama returned {len(float_vector)}-dimension embeddings "
                            f"for {model!r}; the cache expects {expected_dimension}."
                        )
                    if fetched and len(float_vector) != len(
                        next(iter(fetched.values()))
                    ):
                        raise RuntimeError(
                            "Ollama returned embeddings with inconsistent dimensions."
                        )
                    fetched[key] = list(
                        struct.unpack(
                            f"<{len(float_vector)}f",
                            struct.pack(f"<{len(float_vector)}f", *float_vector),
                        )
                    )
                if progress_callback is not None:
                    progress_callback(sum(cache_key_counts[key] for key in batch_keys))
                if expected_dimension is None and fetched:
                    expected_dimension = len(next(iter(fetched.values())))

    _store_cached_embeddings(cache_file, model, fetched, expected_dimension)
    cached.update(fetched)
    misses = len(texts) - hits
    if cache_stats is not None:
        cache_stats.update(hits=hits, misses=misses, total=len(texts))
    logger.info(
        "Embedding cache for %s: %d hits, %d misses (%d texts)",
        model,
        hits,
        misses,
        len(texts),
    )
    return [cached[key] for key in cache_keys]
