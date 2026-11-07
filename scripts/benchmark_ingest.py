"""Benchmark extraction and chunking on saved HTML snapshots without network access."""

import argparse
import json
import math
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from webrag.chunk.markdown import chunk_document
from webrag.extract.cleaner import extract_document
from webrag.index.embed import get_embeddings_batch
from webrag.models import RawPage

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "bench" / "gold.jsonl"
CHUNK_CONFIGS = (
    (150, 0),
    (150, 40),
    (150, 80),
    (250, 0),
    (250, 40),
    (250, 80),
    (350, 0),
    (350, 40),
    (350, 80),
)
FETCHED_AT = "2026-01-01T00:00:00+00:00"


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percent * len(ordered) / 100) - 1)
    return ordered[index]


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        for field in ("url", "snapshot", "must_have", "must_not_have"):
            if field not in case:
                raise ValueError(f"{path}:{line_number} is missing {field!r}")
        if not isinstance(case["must_have"], list) or not isinstance(
            case["must_not_have"], list
        ):
            raise ValueError(f"{path}:{line_number} labels must be JSON arrays")
        cases.append(case)
    if not cases:
        raise ValueError(f"No benchmark cases found in {path}")
    return cases


def table_rows(markdown: str) -> list[str]:
    rows = []
    for line in markdown.splitlines():
        candidate = line.strip()
        if "|" not in candidate:
            continue
        if re.fullmatch(r"[|:\-\s]+", candidate):
            continue
        rows.append(candidate)
    return rows


def count_cut_table_rows(markdown: str, chunks: list[Any]) -> int:
    chunk_texts = [normalize(chunk.text) for chunk in chunks]
    return sum(
        not any(normalize(row) in text for text in chunk_texts)
        for row in table_rows(markdown)
    )


def describe_longest_chunks(
    extraction_results: list[dict[str, Any]], tokenizer: Any
) -> None:
    longest: list[tuple[int, int, Any]] = []
    for result in extraction_results:
        document = result["document"]
        if document is None:
            continue
        chunks = chunk_document(
            document,
            max_chunk_words=150,
            overlap_words=40,
        )
        longest.extend(
            (
                len(tokenizer.encode(chunk.text, add_special_tokens=False)),
                index,
                chunk,
            )
            for index, chunk in enumerate(chunks)
        )

    print("\n10 longest chunks at 150 words / 40 overlap (bge-m3 tokens)")
    for token_count, _, chunk in sorted(longest, key=lambda item: item[0], reverse=True)[:10]:
        section = " > ".join(chunk.section_path) or "Overview"
        preview = " ".join(chunk.text.split())[:200]
        context_tokens = len(
            tokenizer.encode(chunk.embed_text, add_special_tokens=False)
        )
        print(
            f"  {token_count} body tokens ({context_tokens} with title/section) | "
            f"{chunk.url} | {section} | {preview}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--tokenizer", default="BAAI/bge-m3")
    parser.add_argument(
        "--max-words",
        type=int,
        help="Run the sweep's overlap settings with this single chunk word limit.",
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help=(
            "Measure cold Ollama embedding and warm-cache runs for each "
            "configuration."
        ),
    )
    args = parser.parse_args()
    if args.max_words is not None and args.max_words < 1:
        parser.error("--max-words must be at least 1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "The benchmark requires transformers; install the project requirements."
        ) from exc
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            args.tokenizer,
            local_files_only=True,
        )
    except OSError as exc:
        raise RuntimeError(
            f"Tokenizer {args.tokenizer!r} is not available in the local Hugging Face "
            "cache or a local directory. Pre-cache it before running this offline "
            "benchmark, or pass --tokenizer with a local tokenizer directory."
        ) from exc

    cases = load_cases(args.cases)
    extraction_results = []
    extraction_seconds = []
    total_facts = 0
    found_facts = 0
    total_negative_labels = 0
    leaked_labels = 0

    for case in cases:
        snapshot = Path(case["snapshot"])
        if not snapshot.is_absolute():
            snapshot = ROOT / snapshot
        if not snapshot.is_file():
            raise FileNotFoundError(
                f"Snapshot not found for {case['url']}: {snapshot}. "
                "The script never downloads missing pages."
            )
        page = RawPage(
            url=case["url"],
            final_url=case.get("final_url", case["url"]),
            status=200,
            content_type="text/html",
            body=snapshot.read_bytes(),
            fetched_at=FETCHED_AT,
        )
        start = time.perf_counter()
        document = extract_document(page, case.get("collection", "default"))
        elapsed = time.perf_counter() - start
        extraction_seconds.append(elapsed)

        text = normalize(document.markdown) if document else ""
        found = [fact for fact in case["must_have"] if normalize(fact) in text]
        leaked = [term for term in case["must_not_have"] if normalize(term) in text]
        total_facts += len(case["must_have"])
        found_facts += len(found)
        total_negative_labels += len(case["must_not_have"])
        leaked_labels += len(leaked)
        extraction_results.append(
            {
                "case": case,
                "document": document,
                "found_facts": found,
                "leaked_labels": leaked,
                "seconds": elapsed,
            }
        )

    print(f"Snapshots: {len(cases)} | tokenizer: {args.tokenizer} (local-only)")
    template_counts = Counter(
        (
            urlparse(case["url"]).hostname,
            "/".join(urlparse(case["url"]).path.split("/")[:4]),
        )
        for case in cases
    )
    template, template_count = template_counts.most_common(1)[0]
    print(
        f"Largest URL template group: {template_count}/{len(cases)} pages | "
        f"{template[0]}{template[1]}"
    )
    if args.max_words is not None:
        fact_word_counts = [
            len(fact.split())
            for case in cases
            for fact in case["must_have"]
        ]
        print(
            f"Fact-label lengths: {min(fact_word_counts, default=0)}-"
            f"{max(fact_word_counts, default=0)} "
            f"words; {sum(count > args.max_words for count in fact_word_counts)} "
            f"exceed --max-words"
        )
    print(
        f"Extraction labels (candidate labels; verify entries marked TODO): "
        f"fact recall {found_facts}/{total_facts} "
        f"({found_facts / total_facts:.1%}), boilerplate leakage "
        f"{leaked_labels}/{total_negative_labels} "
        f"({leaked_labels / total_negative_labels:.1%})"
        if total_facts and total_negative_labels
        else f"Extraction labels: fact recall {found_facts}/{total_facts}; "
        f"boilerplate leakage {leaked_labels}/{total_negative_labels}"
    )
    describe_longest_chunks(extraction_results, tokenizer)
    for result in extraction_results:
        case = result["case"]
        fact_count = len(case["must_have"])
        leak_count = len(case["must_not_have"])
        status = case.get("labels_status", "unspecified")
        print(
            f"  {case['snapshot']}: facts {len(result['found_facts'])}/{fact_count}, "
            f"leaks {len(result['leaked_labels'])}/{leak_count}, "
            f"labels={status}"
        )

    total_table_rows = sum(
        len(table_rows(result["document"].markdown))
        for result in extraction_results
        if result["document"] is not None
    )
    print(
        "\n"
        f"{'words':>5} {'overlap':>7} {'chunks':>6} "
        f"{'tok p50/p95/max':>16} {'>256/>512':>10} {'<30w':>5} "
        f"{'row cuts':>8} {'facts':>7} {'extract ms p50/p95':>19} "
        f"{'chunk ms p50/p95':>18} {'embed cold ms/hit%':>19} "
        f"{'embed warm ms/hit%':>19}"
    )

    chunk_configs = (
        tuple(
            (args.max_words, overlap)
            for overlap in dict.fromkeys(overlap for _, overlap in CHUNK_CONFIGS)
        )
        if args.max_words is not None
        else CHUNK_CONFIGS
    )
    for max_words, overlap in chunk_configs:
        chunks = []
        chunk_seconds = []
        survived_facts = 0
        table_row_cuts = 0
        site_stats: dict[str, dict[str, Any]] = {}
        for result in extraction_results:
            document = result["document"]
            if document is None:
                continue
            start = time.perf_counter()
            page_chunks = chunk_document(
                document,
                max_chunk_words=max_words,
                overlap_words=overlap,
            )
            chunk_seconds.append(time.perf_counter() - start)
            chunks.extend(page_chunks)
            page_facts = result["case"]["must_have"]
            page_survived_facts = sum(
                any(normalize(fact) in normalize(chunk.text) for chunk in page_chunks)
                for fact in page_facts
            )
            page_table_rows = len(table_rows(document.markdown))
            page_table_row_cuts = count_cut_table_rows(
                document.markdown, page_chunks
            )
            survived_facts += page_survived_facts
            table_row_cuts += page_table_row_cuts
            site = urlparse(result["case"]["url"]).hostname or "unknown"
            stats = site_stats.setdefault(
                site,
                {
                    "pages": 0,
                    "chunks": 0,
                    "over_256": 0,
                    "row_cuts": 0,
                    "table_rows": 0,
                    "facts_survived": 0,
                    "facts": 0,
                },
            )
            page_token_lengths = [
                len(tokenizer.encode(chunk.text, add_special_tokens=False))
                for chunk in page_chunks
            ]
            stats["pages"] += 1
            stats["chunks"] += len(page_chunks)
            stats["over_256"] += sum(
                token_count > 256 for token_count in page_token_lengths
            )
            stats["row_cuts"] += page_table_row_cuts
            stats["table_rows"] += page_table_rows
            stats["facts_survived"] += page_survived_facts
            stats["facts"] += len(page_facts)

        token_lengths = [
            len(tokenizer.encode(chunk.text, add_special_tokens=False))
            for chunk in chunks
        ]
        tiny_chunks = sum(len(chunk.text.split()) < 30 for chunk in chunks)
        over_256 = sum(size > 256 for size in token_lengths)
        over_512 = sum(size > 512 for size in token_lengths)
        fact_ratio = (
            f"{survived_facts}/{total_facts}"
            if total_facts
            else "n/a"
        )
        row_cut_ratio = f"{table_row_cuts}/{total_table_rows}"
        cold_embedding_result = "n/a"
        warm_embedding_result = "n/a"
        if args.embed:
            print(f"Embedding {len(chunks)} chunks via Ollama bge-m3...", flush=True)
            with tempfile.TemporaryDirectory(
                prefix="webrag-embedding-benchmark-"
            ) as cache_dir:
                cache_path = Path(cache_dir) / "embeddings.sqlite3"
                texts = [chunk.embed_text for chunk in chunks]
                cold_stats: dict[str, int] = {}
                start = time.perf_counter()
                embeddings = get_embeddings_batch(
                    texts,
                    model="bge-m3:latest",
                    timeout=180.0,
                    cache_path=cache_path,
                    cache_stats=cold_stats,
                )
                cold_ms = (time.perf_counter() - start) * 1000
                if len(embeddings) != len(chunks):
                    raise RuntimeError(
                        "Ollama returned an unexpected number of chunk embeddings."
                    )

                warm_stats: dict[str, int] = {}
                start = time.perf_counter()
                warm_embeddings = get_embeddings_batch(
                    texts,
                    model="bge-m3:latest",
                    timeout=180.0,
                    cache_path=cache_path,
                    cache_stats=warm_stats,
                )
                warm_ms = (time.perf_counter() - start) * 1000
                if warm_embeddings != embeddings:
                    raise RuntimeError(
                        "Warm-cache embeddings differed from cold-run embeddings."
                    )
                cold_hit_rate = (
                    cold_stats["hits"] / cold_stats["total"]
                    if cold_stats["total"]
                    else 0.0
                )
                warm_hit_rate = (
                    warm_stats["hits"] / warm_stats["total"]
                    if warm_stats["total"]
                    else 0.0
                )
                cold_embedding_result = (
                    f"{cold_ms:.0f}/{cold_hit_rate:.0%}"
                )
                warm_embedding_result = (
                    f"{warm_ms:.0f}/{warm_hit_rate:.0%}"
                )
        print(
            f"{max_words:>5} {overlap:>7} {len(chunks):>6} "
            f"{percentile(token_lengths, 50):.0f}/{percentile(token_lengths, 95):.0f}/"
            f"{max(token_lengths, default=0):<4} "
            f"{over_256:>4}/{over_512:<5} {tiny_chunks:>5} "
            f"{row_cut_ratio:>8} {fact_ratio:>7} "
            f"{percentile(extraction_seconds, 50) * 1000:.1f}/"
            f"{percentile(extraction_seconds, 95) * 1000:.1f}".rjust(19)
            + " "
            + f"{percentile(chunk_seconds, 50) * 1000:.1f}/"
            f"{percentile(chunk_seconds, 95) * 1000:.1f}".rjust(18)
            + f" {cold_embedding_result:>19} {warm_embedding_result:>19}"
        )
        print(
            "  Site groups: host | pages | chunks | >256 tokens | "
            "table rows cut | facts survived"
        )
        for site, stats in sorted(site_stats.items()):
            print(
                f"    {site:<32} {stats['pages']:>2} {stats['chunks']:>6} "
                f"{stats['over_256']:>4} "
                f"{stats['row_cuts']}/{stats['table_rows']} "
                f"{stats['facts_survived']}/{stats['facts']}"
            )

    print(
        "\nToken lengths use chunk.text with special tokens excluded. "
        "A table row is counted as cut when no single chunk contains the full "
        "normalized Markdown row."
    )


if __name__ == "__main__":
    main()
