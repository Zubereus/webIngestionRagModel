from functools import lru_cache
from typing import Any

import torch
from sentence_transformers import CrossEncoder

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_MAX_LENGTH = 256
RERANKER_BATCH_SIZE = 8


@lru_cache(maxsize=1)
def get_reranker(
    device: str = "cpu",
    max_length: int = RERANKER_MAX_LENGTH,
) -> CrossEncoder:
    model_kwargs = (
        {"torch_dtype": torch.float16}
        if device == "cuda"
        else {}
    )
    return CrossEncoder(
        RERANKER_MODEL,
        device=device,
        max_length=max_length,
        model_kwargs=model_kwargs,
    )


def reranker_device(provider: str) -> str | None:
    return (
        "cuda"
        if provider == "gemini" and torch.cuda.is_available()
        else None
    )


def rerank_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    top_n: int,
    device: str = "cpu",
    batch_size: int = RERANKER_BATCH_SIZE,
    max_length: int = RERANKER_MAX_LENGTH,
) -> list[dict[str, Any]]:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if len(chunks) <= 1:
        return chunks[:top_n]

    passages = []
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        title = metadata.get("title", "")
        section = metadata.get("section_path", "")
        passages.append(
            f"Title: {title}\nSection: {section}\n\n{chunk['text']}"
        )

    scores = get_reranker(device, max_length).predict(
        [(question, passage) for passage in passages],
        batch_size=batch_size,
        show_progress_bar=False,
    )
    ranked = sorted(
        zip(scores, chunks),
        key=lambda pair: float(pair[0]),
        reverse=True,
    )
    return [
        {**chunk, "reranker_score": float(score)}
        for score, chunk in ranked[:top_n]
    ]
