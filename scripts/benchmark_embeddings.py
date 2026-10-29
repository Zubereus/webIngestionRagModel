"""Compare local Ollama embedding models on a small bilingual retrieval set."""

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from webrag.index.embed import get_embedding, get_embeddings_batch
from webrag.index.vectordb import VectorDBManager

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = ROOT / "data" / "chunks.jsonl"
CASES_PATH = ROOT / "benchmarks" / "embedding_queries.json"
DEFAULT_MODELS = (
    "nomic-embed-text:latest",
    "bge-m3:latest",
    "qwen3-embedding:0.6b",
)
OLLAMA_BENCHMARK_TIMEOUT_SECONDS = 180.0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def section_text(value: Any) -> str:
    if isinstance(value, list):
        return " > ".join(str(part) for part in value)
    return str(value or "")


def validate_cases(
    cases: list[dict[str, Any]], chunks_by_id: dict[str, dict[str, Any]]
) -> None:
    if not cases:
        raise ValueError("The benchmark query set is empty.")

    for case in cases:
        targets = case.get("relevant_chunk_ids")
        if not isinstance(targets, list) or not targets:
            raise ValueError(f"Benchmark case has no target passages: {case!r}")
        for chunk_id in targets:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                raise ValueError(f"Benchmark target passage not found: {chunk_id}")
            if chunk.get("collection", "default") != case["collection"]:
                raise ValueError(
                    f"Target passage {chunk_id} is not in collection "
                    f"{case['collection']!r}."
                )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError(
            "Embedding dimension mismatch: "
            f"{len(left)} document values vs {len(right)} query values."
        )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("Embedding model returned a zero-length vector.")
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def dense_ranking(
    query_vector: list[float],
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
) -> list[int]:
    scores = [
        cosine_similarity(query_vector, vector)
        for vector in vectors
    ]
    return sorted(
        range(len(chunks)),
        key=lambda index: (-scores[index], chunks[index]["chunk_id"]),
    )


def hybrid_ranking(
    query: str,
    chunks: list[dict[str, Any]],
    dense_order: list[int],
    top_k: int,
) -> list[int]:
    candidate_count = min(len(chunks), max(top_k * 5, 25))
    dense_ranks = {
        index: rank
        for rank, index in enumerate(dense_order[:candidate_count], start=1)
    }
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [
        {
            **chunk.get("metadata", {}),
            "title": chunk.get("title", ""),
            "section_path": section_text(chunk.get("section_path")),
        }
        for chunk in chunks
    ]
    bm25_scores = VectorDBManager._bm25_scores(query, documents, metadatas)
    bm25_order = sorted(
        range(len(chunks)),
        key=lambda index: (-bm25_scores[index], index),
    )
    bm25_ranks = {
        index: rank for rank, index in enumerate(bm25_order, start=1)
    }
    return sorted(
        range(len(chunks)),
        key=lambda index: -(
            VectorDBManager._rrf_score(
                dense_ranks.get(index), bm25_ranks[index]
            )
            + VectorDBManager._deadline_relevance_boost(
                query, metadatas[index]
            )
        ),
    )


def target_rank(
    ranking: list[int],
    chunks: list[dict[str, Any]],
    relevant_ids: set[str],
) -> int | None:
    for rank, index in enumerate(ranking, start=1):
        if chunks[index]["chunk_id"] in relevant_ids:
            return rank
    return None


def summarize_ranks(ranks: list[int | None], top_k: int) -> dict[str, float]:
    count = len(ranks)
    return {
        f"hit@{k}": sum(rank is not None and rank <= k for rank in ranks) / count
        for k in (1, 3, 5, top_k)
    } | {
        "mrr": sum(1 / rank if rank is not None else 0 for rank in ranks) / count
    }


def benchmark_model(
    model: str,
    cases: list[dict[str, Any]],
    chunks_by_collection: dict[str, list[dict[str, Any]]],
    top_k: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    corpus_vectors: dict[str, list[list[float]]] = {}
    embedding_seconds = 0.0
    query_seconds = 0.0

    for collection, chunks in chunks_by_collection.items():
        texts = [chunk.get("embed_text") or chunk["text"] for chunk in chunks]
        start = time.perf_counter()
        vectors = get_embeddings_batch(
            texts,
            model=model,
            timeout=OLLAMA_BENCHMARK_TIMEOUT_SECONDS,
        )
        embedding_seconds += time.perf_counter() - start
        if len(vectors) != len(chunks):
            raise RuntimeError(
                f"{model} returned {len(vectors)} vectors for "
                f"{len(chunks)} passages in {collection!r}."
            )
        corpus_vectors[collection] = vectors

    case_results = []
    for case in cases:
        collection = case["collection"]
        chunks = chunks_by_collection[collection]
        start = time.perf_counter()
        query_vector = get_embedding(
            case["query"],
            model=model,
            timeout=OLLAMA_BENCHMARK_TIMEOUT_SECONDS,
        )
        query_seconds += time.perf_counter() - start
        dense_order = dense_ranking(
            query_vector, chunks, corpus_vectors[collection]
        )
        hybrid_order = hybrid_ranking(case["query"], chunks, dense_order, top_k)
        relevant_ids = set(case["relevant_chunk_ids"])
        case_results.append(
            {
                "language": case["language"],
                "query": case["query"],
                "relevant_chunk_ids": sorted(relevant_ids),
                "dense_rank": target_rank(dense_order, chunks, relevant_ids),
                "hybrid_rank": target_rank(hybrid_order, chunks, relevant_ids),
            }
        )

    summaries = {}
    for language in sorted({case["language"] for case in cases}):
        language_results = [
            item for item in case_results if item["language"] == language
        ]
        summaries[language] = {
            "queries": len(language_results),
            "dense": summarize_ranks(
                [item["dense_rank"] for item in language_results], top_k
            ),
            "hybrid": summarize_ranks(
                [item["hybrid_rank"] for item in language_results], top_k
            ),
        }

    result = {
        "model": model,
        "document_count": sum(map(len, chunks_by_collection.values())),
        "embedding_seconds": round(embedding_seconds, 2),
        "query_embedding_seconds_total": round(query_seconds, 2),
        "query_embedding_seconds_average": round(
            query_seconds / len(cases), 3
        ),
        "languages": summaries,
    }
    return result, case_results


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="Comma-separated Ollama embedding model tags.",
    )
    parser.add_argument(
        "--top-k", type=int, default=10, help="Retrieval cutoff for metrics."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for a JSON copy of the benchmark results.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print each target passage's dense and hybrid rank.",
    )
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    models = [model.strip() for model in args.models.split(",") if model.strip()]
    if not models:
        parser.error("Provide at least one model with --models.")

    chunks = load_jsonl(CHUNKS_PATH)
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    validate_cases(cases, chunks_by_id)
    chunks_by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for collection in sorted({case["collection"] for case in cases}):
        chunks_by_collection[collection] = [
            chunk
            for chunk in chunks
            if chunk.get("collection", "default") == collection
        ]

    all_results = []
    for model in models:
        print(
            f"\nBenchmarking {model}: "
            f"{sum(map(len, chunks_by_collection.values()))} passages, "
            f"{len(cases)} queries..."
        )
        result, details = benchmark_model(
            model, cases, chunks_by_collection, args.top_k
        )
        all_results.append(result)
        print(
            f"{model} | document embeddings: {result['embedding_seconds']:.2f}s "
            f"| query embedding avg: "
            f"{result['query_embedding_seconds_average']:.3f}s"
        )
        for language, metrics in result["languages"].items():
            dense = metrics["dense"]
            hybrid = metrics["hybrid"]
            print(
                f"  {language} ({metrics['queries']} queries): "
                f"dense R@1 {dense['hit@1']:.0%}, R@5 {dense['hit@5']:.0%}, "
                f"R@{args.top_k} {dense[f'hit@{args.top_k}']:.0%}, "
                f"MRR {dense['mrr']:.3f}; "
                f"hybrid R@5 {hybrid['hit@5']:.0%}, "
                f"R@{args.top_k} {hybrid[f'hit@{args.top_k}']:.0%}, "
                f"MRR {hybrid['mrr']:.3f}"
            )
        if args.details:
            for item in details:
                print(
                    f"  [{item['language']}] dense={item['dense_rank']} "
                    f"hybrid={item['hybrid_rank']} | {item['query']}"
                )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(all_results, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nSaved results to {args.output}")


if __name__ == "__main__":
    main()
