"""Print dense and BM25 score ranges for representative questions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from webrag.index.vectordb import VectorDBManager

COLLECTION = "default"
ON_TOPIC = [
    "what is RAG?",
    "what is chunking?",
    "RAG là gì?",
]
OFF_TOPIC = [
    "what is the capital of France?",
    "tell me a joke",
    "how do I write a good prompt?",
    "bạn khỏe không?",
]


def best_scores(db: VectorDBManager, question: str) -> tuple[float, float]:
    chunks = db.query(
        collection_name=COLLECTION,
        query_text=question,
        n_results=5,
        retrieval_mode="hybrid",
    )
    dense = max((float(c.get("dense_score") or 0.0) for c in chunks), default=0.0)
    bm25 = max((float(c.get("bm25_score") or 0.0) for c in chunks), default=0.0)
    return dense, bm25


def score_all(
    db: VectorDBManager, questions: list[str]
) -> list[tuple[str, float, float]]:
    return [(question, *best_scores(db, question)) for question in questions]


def print_rows(title: str, rows: list[tuple[str, float, float]]) -> None:
    print(f"\n{title}")
    for question, dense, bm25 in rows:
        print(f"  dense={dense:.2f}  bm25={bm25:5.1f}  {question}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    db = VectorDBManager()
    on_rows = score_all(db, ON_TOPIC)
    off_rows = score_all(db, OFF_TOPIC)
    print_rows("ON TOPIC", on_rows)
    print_rows("OFF TOPIC", off_rows)

    highest_off = max((dense for _, dense, _ in off_rows), default=0.0)
    lowest_on = min((dense for _, dense, _ in on_rows), default=0.0)
    gap = lowest_on - highest_off
    print(
        f"\nhighest off-topic dense = {highest_off:.2f}, "
        f"lowest on-topic dense = {lowest_on:.2f}, gap = {gap:.2f}"
    )
    if gap > 0.05:
        print(f"suggested MIN_DENSE_SOFT about {(highest_off + lowest_on) / 2:.2f}")
    else:
        print("gap is too small for dense alone: add a BM25 requirement for soft mode")


if __name__ == "__main__":
    main()
