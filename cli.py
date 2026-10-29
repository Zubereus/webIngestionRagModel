import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Add src to pythonpath so it runs without installing package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from webrag.index.vectordb import VectorDBManager
from webrag.pipeline import IngestionPipeline
from webrag.rag.generate import generate_rag_answer
from webrag.store.catalog import StorageManager


def cmd_ingest(args):
    pipeline = IngestionPipeline()
    print(f"\n[+] Processing: {args.url} (Collection: {args.collection})")
    result = pipeline.ingest_url(args.url, collection=args.collection, force=args.force)

    print("\nResult:")
    for k, v in result.items():
        print(f"  {k}: {v}")


def cmd_list(args):
    storage = StorageManager()
    with sqlite3.connect(storage.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM pages ORDER BY fetched_at DESC").fetchall()

    if not rows:
        print("\nCatalog is empty. Ingest some URLs first with `python cli.py ingest <url>`")
        return

    print(f"\n{'Doc ID':<18} {'Collection':<14} {'Status':<12} {'URL'}")
    print("-" * 85)
    for row in rows:
        coll = row["collection"] if "collection" in row.keys() and row["collection"] else "default"
        print(f"{row['doc_id']:<18} {coll:<14} {row['status']:<12} {row['canonical_url']}")


def cmd_inspect(args):
    storage = StorageManager()
    if not storage.chunks_file.exists():
        print("\nNo chunks file found yet.")
        return

    matched_chunks = []
    with storage.chunks_file.open("r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            if chunk["doc_id"] == args.doc_id:
                matched_chunks.append(chunk)

    if not matched_chunks:
        print(f"\nNo chunks found for Doc ID: {args.doc_id}")
        return

    print(f"\nFound {len(matched_chunks)} chunks for {args.doc_id}:\n")
    for chunk in matched_chunks:
        print(f"=== Chunk #{chunk['ordinal']} (ID: {chunk['chunk_id']}) ===")
        print(f"Path: {' > '.join(chunk['section_path']) or 'Root'}")
        print(f"Tokens approx: {chunk['token_count']}")
        print(f"Sample content:\n{chunk['text'][:250]}...\n")


def cmd_index(args):
    storage = StorageManager()
    if not storage.chunks_file.exists():
        print("\nNo chunks file found. Run `python cli.py ingest <url>` first.")
        return

    vdb = VectorDBManager()
    results = vdb.index_chunks_file(storage.chunks_file, force=args.force)

    print("\n--- Indexing Summary ---")
    if not results or all(count == 0 for count in results.values()):
        print("All chunks in dataset are already up-to-date in vector DB.")
    else:
        for coll, count in results.items():
            print(f"  Collection '{coll}': {count} new chunks indexed.")


def cmd_query(args):
    vdb = VectorDBManager()
    print(f"\n[+] Searching collection: '{args.collection}' for: \"{args.query}\"")
    chunks = vdb.query(
        collection_name=args.collection,
        query_text=args.query,
        n_results=args.top_k,
    )

    if not chunks:
        print(f"No documents indexed in collection '{args.collection}'. Run `python cli.py index` first.")
        return

    print(f"\n--- Retrieved Context ({len(chunks)} chunks) ---")
    for idx, c in enumerate(chunks, 1):
        meta = c["metadata"]
        print(f"[{idx}] {meta.get('title')} ({meta.get('url')})")
        print(f"    Distance: {c['distance']:.4f}" if c.get("distance") is not None else "")
        print(f"    Excerpt: {c['text'][:180].strip()}...\n")

    print("[+] Generating answer with Qwen (qwen2.5:1.5b)...")
    rag_resp = generate_rag_answer(query=args.query, retrieved_chunks=chunks)

    print("\n=== Qwen Answer ===")
    print(rag_resp.answer)

    print("\n=== Sources Cited ===")
    for src in rag_resp.sources:
        print(f"[{src['index']}] {src['title']} - {src['url']}")


def main():
    parser = argparse.ArgumentParser(description="WebRAG: Ingestion CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a web URL into dataset")
    ingest_parser.add_argument("url", help="Web URL to ingest")
    ingest_parser.add_argument(
        "--collection",
        default="default",
        help="Target subject/collection (e.g. finance, healthcare, tech_docs)",
    )
    ingest_parser.add_argument("--force", action="store_true", help="Force re-fetch and re-chunk")
    ingest_parser.set_defaults(func=cmd_ingest)

    # List command
    list_parser = subparsers.add_parser("list", help="List all processed pages in the catalog")
    list_parser.set_defaults(func=cmd_list)

    # Inspect chunks command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect chunks for a doc_id")
    inspect_parser.add_argument("doc_id", help="Document ID to inspect")
    inspect_parser.set_defaults(func=cmd_inspect)

    # Index command
    index_parser = subparsers.add_parser("index", help="Index all dataset chunks into ChromaDB")
    index_parser.add_argument("--force", action="store_true", help="Force re-indexing of all chunks")
    index_parser.set_defaults(func=cmd_index)

    # Query command
    query_parser = subparsers.add_parser("query", help="Query the RAG model")
    query_parser.add_argument("query", help="Question to ask the model")
    query_parser.add_argument(
        "--collection",
        default="default",
        help="Collection to search in (e.g. default, ai_tech, finance)",
    )
    query_parser.add_argument(
        "--top-k",
        type=int,
        default=4,
        help="Number of context chunks to retrieve (default: 4)",
    )
    query_parser.set_defaults(func=cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
