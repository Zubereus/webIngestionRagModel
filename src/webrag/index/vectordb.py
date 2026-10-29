import json
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import chromadb
from tqdm import tqdm

from webrag.index.embed import (
    EMBEDDING_BATCH_SIZE,
    get_embedding,
    get_embeddings_batch,
)

DEFAULT_CHROMA_DIR = Path(
    os.getenv("WEBRAG_CHROMA_DIR", str(Path("data") / "chroma_bge_m3"))
)
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
RRF_K = 60
DEADLINE_SECTION_BOOST = 0.025


class VectorDBManager:
    def __init__(self, persist_dir: Path | str = DEFAULT_CHROMA_DIR):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

    def get_collection(self, collection_name: str):
        """Retrieve or create a collection by subject name."""
        # Chroma collection names must be valid alphanumeric/underscore
        clean_name = collection_name.strip().replace("-", "_").lower() or "default"
        return self.client.get_or_create_collection(
            name=clean_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_chunks_file(self, chunks_file: Path | str, force: bool = False) -> dict[str, int]:
        """
        Read chunks.jsonl, group by collection, compute embeddings,
        and upsert into ChromaDB.
        """
        chunks_path = Path(chunks_file)
        if not chunks_path.exists():
            return {}

        chunks_by_collection: dict[str, list[dict[str, Any]]] = {}

        with chunks_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                coll = chunk.get("collection") or "default"
                if coll not in chunks_by_collection:
                    chunks_by_collection[coll] = []
                chunks_by_collection[coll].append(chunk)

        results: dict[str, int] = {}

        for coll_name, chunks in chunks_by_collection.items():
            collection = self.get_collection(coll_name)
            existing_data = collection.get(include=["documents", "metadatas"])
            existing_by_id = {
                chunk_id: {
                    "document": document,
                    "metadata": metadata,
                }
                for chunk_id, document, metadata in zip(
                    existing_data.get("ids") or [],
                    existing_data.get("documents") or [],
                    existing_data.get("metadatas") or [],
                )
            }
            desired_ids = {chunk["chunk_id"] for chunk in chunks}
            desired_doc_ids = {chunk["doc_id"] for chunk in chunks}
            stale_ids = [
                chunk_id
                for chunk_id, existing in existing_by_id.items()
                if existing["metadata"].get("doc_id") in desired_doc_ids
                and chunk_id not in desired_ids
            ]

            pending = []
            for chunk in chunks:
                section_path = chunk.get("section_path", [])
                section_str = (
                    " > ".join(section_path)
                    if isinstance(section_path, list)
                    else str(section_path)
                )
                metadata = {
                    "doc_id": chunk["doc_id"],
                    "url": chunk["url"],
                    "title": chunk["title"],
                    "section_path": section_str,
                    "token_count": chunk.get("token_count", 0),
                    "fetched_at": chunk.get("fetched_at", ""),
                    "collection": coll_name,
                }
                existing = existing_by_id.get(chunk["chunk_id"])
                if (
                    force
                    or existing is None
                    or existing["document"] != chunk["text"]
                    or existing["metadata"] != metadata
                ):
                    pending.append({**chunk, "_vector_metadata": metadata})

            print(f"\n[+] Indexing {len(pending)} new or changed chunks into collection '{coll_name}'...")

            ids = []
            documents = []
            metadatas = []
            embedding_texts = []

            for chunk in pending:
                embedding_texts.append(chunk.get("embed_text") or chunk["text"])
                ids.append(chunk["chunk_id"])
                documents.append(chunk["text"])
                metadatas.append(chunk["_vector_metadata"])

            embeddings: list[list[float]] = []
            for start in tqdm(
                range(0, len(pending), EMBEDDING_BATCH_SIZE),
                desc=f"Embedding '{coll_name}'",
            ):
                batch_texts = embedding_texts[start : start + EMBEDDING_BATCH_SIZE]
                embeddings.extend(get_embeddings_batch(batch_texts))

            if pending:
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
            if stale_ids:
                collection.delete(ids=stale_ids)
            results[coll_name] = len(pending)

        return results

    def index_chunks(self, chunks: list[dict[str, Any]]) -> dict[str, int]:
        """Embed and upsert only the supplied chunks."""
        grouped: dict[str, list[dict[str, Any]]] = {}
        for chunk in chunks:
            collection_name = chunk.get("collection") or "default"
            grouped.setdefault(collection_name, []).append(chunk)

        results: dict[str, int] = {}
        for collection_name, items in grouped.items():
            collection = self.get_collection(collection_name)
            embeddings = get_embeddings_batch(
                [item.get("embed_text") or item["text"] for item in items]
            )
            collection.upsert(
                ids=[item["chunk_id"] for item in items],
                embeddings=embeddings,
                documents=[item["text"] for item in items],
                metadatas=[
                    {
                        "doc_id": item["doc_id"],
                        "url": item["url"],
                        "title": item["title"],
                        "section_path": " > ".join(item.get("section_path", [])),
                        "token_count": item.get("token_count", 0),
                        "fetched_at": item.get("fetched_at", ""),
                        "collection": collection_name,
                    }
                    for item in items
                ],
            )
            results[collection_name] = len(items)
        return results

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 4,
        retrieval_mode: str = "hybrid",
        doc_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query a collection using dense, BM25, or hybrid retrieval.
        """
        if retrieval_mode not in {"dense", "hybrid"}:
            raise ValueError(f"Unsupported retrieval mode: {retrieval_mode}")

        collection = self.get_collection(collection_name)
        if collection.count() == 0:
            return []

        where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        if where:
            scoped_corpus = collection.get(where=where, include=[])
            collection_count = len(scoped_corpus.get("ids") or [])
        else:
            collection_count = collection.count()
        if collection_count == 0:
            return []
        limit = min(n_results, collection_count)
        candidate_count = min(collection_count, max(limit * 5, 25))
        dense_results = self._dense_query(collection, query_text, candidate_count, where)
        if retrieval_mode == "dense":
            return dense_results[:limit]

        corpus = collection.get(where=where, include=["documents", "metadatas"])
        bm25_scores = self._bm25_scores(
            query_text,
            corpus.get("documents") or [],
            corpus.get("metadatas") or [],
        )
        dense_ranks = {
            item["chunk_id"]: rank
            for rank, item in enumerate(dense_results, start=1)
        }
        dense_by_id = {item["chunk_id"]: item for item in dense_results}
        bm25_scores_by_id = dict(zip(corpus["ids"], bm25_scores))
        bm25_ranks = {
            chunk_id: rank
            for rank, chunk_id in enumerate(
                sorted(
                    corpus["ids"],
                    key=bm25_scores_by_id.__getitem__,
                    reverse=True,
                ),
                start=1,
            )
        }
        combined: list[dict[str, Any]] = []

        for index, chunk_id in enumerate(corpus.get("ids") or []):
            bm25_score = bm25_scores[index]
            combined_score = self._rrf_score(
                dense_ranks.get(chunk_id), bm25_ranks.get(chunk_id)
            )
            metadata = (corpus.get("metadatas") or [])[index]
            combined_score += self._deadline_relevance_boost(query_text, metadata)
            item = dense_by_id.get(chunk_id)
            if item is None:
                item = {
                    "chunk_id": chunk_id,
                    "text": (corpus.get("documents") or [])[index],
                    "metadata": metadata,
                }
            item = dict(item)
            item["dense_score"] = (
                1.0 - item["distance"] if "distance" in item else None
            )
            item["bm25_score"] = bm25_score
            item["score"] = combined_score
            item["distance"] = 1.0 - combined_score
            combined.append(item)

        combined.sort(key=lambda item: item["distance"])
        return combined[:limit]

    def _dense_query(
        self, collection: Any, query_text: str, n_results: int, where: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        query_vector = get_embedding(query_text)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        return [
            {
                "chunk_id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "dense_score": 1.0 - results["distances"][0][i],
                "score": 1.0 - results["distances"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        folded = unicodedata.normalize("NFD", text.casefold())
        unaccented = "".join(
            character
            for character in folded
            if unicodedata.category(character) != "Mn"
        ).replace("đ", "d")
        return TOKEN_PATTERN.findall(unaccented)

    @classmethod
    def _bm25_scores(
        cls,
        query_text: str,
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> list[float]:
        tokenized_documents = [
            cls._tokens(
                f"{metadata.get('title', '')} "
                f"{metadata.get('section_path', '')} "
                f"{document}"
            )
            for document, metadata in zip(documents, metadatas)
        ]
        query_terms = cls._tokens(query_text)
        if "thoi" in query_terms and (
            "gian" in query_terms or "han" in query_terms
        ):
            query_terms = list(
                dict.fromkeys(
                    query_terms + cls._tokens("thời hạn giải quyết thời gian xử lý")
                )
            )
        document_count = len(tokenized_documents)
        if not query_terms or not document_count:
            return [0.0] * document_count

        document_frequency: dict[str, int] = {}
        for tokens in tokenized_documents:
            for term in set(tokens):
                document_frequency[term] = document_frequency.get(term, 0) + 1

        average_length = sum(len(tokens) for tokens in tokenized_documents) / document_count
        scores = []
        for tokens in tokenized_documents:
            frequencies: dict[str, int] = {}
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
            length = len(tokens)
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                idf = math.log(1 + (document_count - document_frequency.get(term, 0) + 0.5)
                                / (document_frequency.get(term, 0) + 0.5))
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * length / average_length)
                score += idf * frequency * 2.5 / denominator
            scores.append(score)
        return scores

    @classmethod
    def _deadline_relevance_boost(
        cls, query_text: str, metadata: dict[str, Any]
    ) -> float:
        query_tokens = cls._tokens(query_text)
        query_terms = set(query_tokens)
        if "thoi" not in query_terms or not query_terms.intersection({"gian", "han"}):
            return 0.0

        section_terms = set(cls._tokens(str(metadata.get("section_path", ""))))
        if not {"thoi", "han", "giai", "quyet"}.issubset(section_terms):
            return 0.0

        ignored_terms = {
            "thoi", "gian", "han", "giai", "quyet", "xu", "ly", "cho", "nguoi", "du",
            "tuoi", "tro", "len", "la", "bao", "nhieu", "lau", "nao",
            "cua", "ve", "o", "tai", "co", "viec",
        }
        subject_terms = [
            term for term in query_tokens
            if term not in ignored_terms and not term.isdecimal()
        ]
        if len(subject_terms) < 2:
            return 0.0

        query_bigrams = set(zip(subject_terms, subject_terms[1:]))
        title_tokens = cls._tokens(str(metadata.get("title", "")))
        title_bigrams = set(zip(title_tokens, title_tokens[1:]))
        title_overlap = len(query_bigrams & title_bigrams) / len(query_bigrams)
        if title_overlap < 0.75:
            return 0.0
        return DEADLINE_SECTION_BOOST * title_overlap

    @staticmethod
    def _rrf_score(dense_rank: int | None, bm25_rank: int | None) -> float:
        return (
            (1.0 / (RRF_K + dense_rank) if dense_rank else 0.0)
            + (1.0 / (RRF_K + bm25_rank) if bm25_rank else 0.0)
        )

    def delete_doc(self, doc_id: str, collection_name: str) -> None:
        self.get_collection(collection_name).delete(where={"doc_id": doc_id})

    def delete_all(self) -> None:
        for collection in self.client.list_collections():
            name = getattr(collection, "name", collection)
            self.client.delete_collection(name)
