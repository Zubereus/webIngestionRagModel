"""Compare existing hybrid retrieval with hybrid retrieval plus BGE reranking."""

import json
import argparse
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from webrag.index.rerank import (
    RERANKER_MODEL,
    RERANKER_BATCH_SIZE,
    RERANKER_MAX_LENGTH,
    get_reranker,
    rerank_chunks,
    reranker_device,
)
from webrag.api.server import keep_relevant
from webrag.index.vectordb import VectorDBManager

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "benchmarks" / "embedding_queries.json"
FINAL_K = 5


def reciprocal_rank(rank: int | None, cutoff: int = FINAL_K) -> float:
    return 1 / rank if rank is not None and rank <= cutoff else 0.0


def relevant_rank(
    chunks: list[dict[str, Any]], relevant_ids: set[str]
) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        if chunk["chunk_id"] in relevant_ids:
            return rank
    return None


def calculate_metrics(ranks: list[int | None], candidate_ranks: list[int | None]) -> dict[str, Any]:
    count = len(ranks)
    return {
        "candidate_recall": sum(rank is not None for rank in candidate_ranks) / count,
        "hit@1": sum(rank is not None and rank <= 1 for rank in ranks) / count,
        "hit@3": sum(rank is not None and rank <= 3 for rank in ranks) / count,
        "hit@5": sum(rank is not None and rank <= FINAL_K for rank in ranks) / count,
        "mrr@5": sum(reciprocal_rank(rank) for rank in ranks) / count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int)
    parser.add_argument("--candidate-k", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=RERANKER_BATCH_SIZE)
    parser.add_argument("--max-length", type=int, default=RERANKER_MAX_LENGTH)
    args = parser.parse_args()
    if args.candidate_k < FINAL_K:
        parser.error(f"--candidate-k must be at least {FINAL_K}")
    if args.batch_size < 1 or args.max_length < 1:
        parser.error("--batch-size and --max-length must be positive")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases:
        raise ValueError(f"No benchmark cases found in {args.cases}")
    end_index = args.end_index if args.end_index is not None else len(cases)
    if args.start_index < 0 or end_index <= args.start_index:
        parser.error("benchmark index range must satisfy 0 <= start < end")
    selected_cases = cases[args.start_index:end_index]
    if not selected_cases:
        parser.error("benchmark index range does not include any cases")

    manager = VectorDBManager()
    rows: list[dict[str, Any]] = []
    retrieval_seconds: list[float] = []
    rerank_seconds: list[float] = []
    device = reranker_device("gemini") or "cpu"
    model_start = time.perf_counter()
    get_reranker(device, args.max_length)
    model_load_seconds = time.perf_counter() - model_start

    for selected_index, case in enumerate(selected_cases):
        case_number = args.start_index + selected_index + 1
        start = time.perf_counter()
        retrieved = manager.query(
            case["collection"],
            case["query"],
            n_results=args.candidate_k,
            retrieval_mode="hybrid",
        )
        retrieval_seconds.append(time.perf_counter() - start)
        relevant_ids = set(case["relevant_chunk_ids"])
        answerable = case.get("answerable", True)
        candidate_rank = relevant_rank(retrieved, relevant_ids)
        gated_candidates = keep_relevant(retrieved, wants_pages=True)
        gate_rank = relevant_rank(gated_candidates, relevant_ids)
        baseline_rank = relevant_rank(retrieved[:FINAL_K], relevant_ids)

        start = time.perf_counter()
        reranked = rerank_chunks(
            case["query"],
            retrieved,
            FINAL_K,
            device,
            args.batch_size,
            args.max_length,
        )
        rerank_seconds.append(time.perf_counter() - start)
        reranked_rank = relevant_rank(reranked, relevant_ids)
        top_score = (
            float(reranked[0]["reranker_score"])
            if reranked
            else None
        )
        rows.append(
            {
                "language": case["language"],
                "query": case["query"],
                "answerable": answerable,
                "accepted_by_relevance_gate": bool(gated_candidates),
                "gate_target_rank": gate_rank,
                "baseline_rank@5": baseline_rank,
                "candidate_rank": candidate_rank,
                "reranked_rank@5": reranked_rank,
                "reranker_top1_score": top_score,
                "reranker_improved": (
                    reciprocal_rank(reranked_rank)
                    > reciprocal_rank(baseline_rank)
                ),
                "reranker_regressed": (
                    reciprocal_rank(reranked_rank)
                    < reciprocal_rank(baseline_rank)
                ),
            }
        )
        print(
            f"Completed {case_number}/{len(cases)} ({case['language']}): "
            f"retrieve={retrieval_seconds[-1]:.2f}s "
            f"rerank={rerank_seconds[-1]:.2f}s",
            flush=True,
        )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups["all"] = rows
    for row in rows:
        groups[row["language"]].append(row)

    print(f"Model: {RERANKER_MODEL} ({device}, max_length={args.max_length})")
    print(
        f"Cases: {len(rows)}/{len(cases)} "
        f"(indices {args.start_index}-{args.start_index + len(rows) - 1}) | "
        f"pool: {args.candidate_k} | final K: {FINAL_K} | "
        f"batch: {args.batch_size} | max_length: {args.max_length}"
    )
    print(f"Model load: {model_load_seconds:.2f}s")
    print(
        "Latency (warm model): "
        f"retrieval mean={statistics.mean(retrieval_seconds):.3f}s, "
        f"rerank mean={statistics.mean(rerank_seconds):.3f}s, "
        f"rerank p50={statistics.median(rerank_seconds):.3f}s"
    )
    print(
        f"{'Language':<10} {'N':>3} {f'Cand@{args.candidate_k}':>9} {'Hybrid H@1':>11} "
        f"{'Rerank H@1':>11} {'Hybrid H@5':>11} {'Rerank H@5':>11} "
        f"{'Hybrid MRR@5':>13} {'Rerank MRR@5':>13}"
    )
    for language, results in groups.items():
        answerable_results = [row for row in results if row["answerable"]]
        if not answerable_results:
            print(f"{language:<10} {len(results):>3} — no answerable cases")
            continue
        baseline_metrics = calculate_metrics(
            [row["baseline_rank@5"] for row in answerable_results],
            [row["candidate_rank"] for row in answerable_results],
        )
        reranked_metrics = calculate_metrics(
            [row["reranked_rank@5"] for row in answerable_results],
            [row["candidate_rank"] for row in answerable_results],
        )
        print(
            f"{language:<10} {len(results):>3} "
            f"{baseline_metrics['candidate_recall']:>9.3f} "
            f"{baseline_metrics['hit@1']:>11.3f} "
            f"{reranked_metrics['hit@1']:>11.3f} "
            f"{baseline_metrics['hit@5']:>11.3f} "
            f"{reranked_metrics['hit@5']:>11.3f} "
            f"{baseline_metrics['mrr@5']:>13.3f} "
            f"{reranked_metrics['mrr@5']:>13.3f}"
        )

    unanswerable_rows = [row for row in rows if not row["answerable"]]
    answerable_rows = [row for row in rows if row["answerable"]]
    gate_target_count = sum(
        row["gate_target_rank"] is not None for row in answerable_rows
    )
    print(
        f"Answerable targets retained by relevance gate: "
        f"{gate_target_count}/{len(answerable_rows)}"
    )
    accepted_unanswerable = sum(
        row["accepted_by_relevance_gate"] for row in unanswerable_rows
    )
    print(
        "Unanswerable questions accepted by relevance gate: "
        f"{accepted_unanswerable}/{len(unanswerable_rows)}"
        if unanswerable_rows
        else "Unanswerable questions: none in this set"
    )
    for label, scored_rows in (
        ("answerable", [row for row in rows if row["answerable"]]),
        ("unanswerable", unanswerable_rows),
    ):
        scores = [
            row["reranker_top1_score"]
            for row in scored_rows
            if row["reranker_top1_score"] is not None
        ]
        if scores:
            print(
                f"Top-1 reranker score ({label}): "
                f"min={min(scores):.4f}, "
                f"median={statistics.median(scores):.4f}, "
                f"max={max(scores):.4f}"
            )
    improved = sum(row["reranker_improved"] for row in rows)
    regressed = sum(row["reranker_regressed"] for row in rows)
    print(f"Queries improved: {improved}/{len(rows)} | regressed: {regressed}/{len(rows)}")
    print("\nPer-query ranks (None means no relevant passage in that ranking):")
    for row in rows:
        print(
            f"{row['language']} {'answerable' if row['answerable'] else 'unanswerable'}: "
            f"hybrid@5={row['baseline_rank@5']} "
            f"pool@{args.candidate_k}={row['candidate_rank']} "
            f"gate@{args.candidate_k}={row['gate_target_rank']} "
            f"rerank@5={row['reranked_rank@5']} "
            f"top_score={row['reranker_top1_score']} | {row['query']}"
        )


if __name__ == "__main__":
    main()
