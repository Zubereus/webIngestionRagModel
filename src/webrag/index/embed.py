import os
from typing import Literal

import httpx

OLLAMA_API_BASE = "http://localhost:11434"
DEFAULT_EMBED_MODEL = os.getenv("WEBRAG_EMBED_MODEL", "bge-m3:latest")
EMBEDDING_BATCH_SIZE = 16
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


def add_prefix(
    text: str, model: str, kind: Literal["document", "query"]
) -> str:
    """Apply a model-specific task prefix when the embedding model requires one."""
    prefixes = MODEL_PREFIXES.get(model.split(":", maxsplit=1)[0], {})
    return prefixes.get(kind, "") + text


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
) -> list[list[float]]:
    """Get embeddings in bounded Ollama batches while reusing one HTTP connection."""
    if not texts:
        return []

    embeddings: list[list[float]] = []
    url = f"{api_base}/api/embed"
    with httpx.Client(timeout=timeout) as client:
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = [
                add_prefix(text, model, "document")
                for text in texts[start : start + EMBEDDING_BATCH_SIZE]
            ]
            response = client.post(url, json={"model": model, "input": batch})
            response.raise_for_status()
            batch_embeddings = response.json().get("embeddings")
            if not isinstance(batch_embeddings, list) or len(batch_embeddings) != len(batch):
                raise RuntimeError(
                    "Ollama returned an unexpected number of embeddings."
                )
            embeddings.extend(batch_embeddings)
    return embeddings
