import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import chromadb
from chromadb.config import Settings

from webrag.index.vectordb import VectorDBManager
from webrag.models import Chunk
from webrag.store.catalog import StorageManager


class VectorDBRetrievalTests(unittest.TestCase):
    @staticmethod
    def make_vector_chunk(doc_id, ordinal, collection="default", text=None):
        text = text or f"chunk {ordinal}"
        return {
            "chunk_id": f"{doc_id}:{ordinal}",
            "doc_id": doc_id,
            "ordinal": ordinal,
            "text": text,
            "embed_text": text,
            "section_path": [],
            "token_count": len(text.split()),
            "url": "https://example.org/page",
            "title": "Example page",
            "fetched_at": "2026-01-01",
            "collection": collection,
        }

    @staticmethod
    def make_vector_manager(temp_dir):
        manager = object.__new__(VectorDBManager)
        manager.client = chromadb.EphemeralClient(settings=Settings(allow_reset=True))
        manager.client.reset()
        manager.embedding_cache_path = Path(temp_dir) / "embedding-cache.sqlite3"
        return manager

    def test_clear_embedding_cache_removes_database_adjacent_to_chroma(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = object.__new__(VectorDBManager)
            manager.embedding_cache_path = Path(temp_dir) / "embedding-cache.sqlite3"
            manager.embedding_cache_path.touch()

            manager.clear_embedding_cache()

            self.assertFalse(manager.embedding_cache_path.exists())

    def test_index_chunks_persists_optional_page_metadata(self):
        chunk = self.make_vector_chunk("doc-1", 0, text="page content")
        chunk.update(page=3, ocr=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_vector_manager(temp_dir)
            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.1, 0.2]],
            ):
                manager.index_chunks([chunk])
            indexed = manager.get_collection("default").get(
                include=["metadatas"],
            )

        self.assertEqual(indexed["metadatas"][0]["page"], 3)
        self.assertIs(indexed["metadatas"][0]["ocr"], True)

    def test_tokens_match_vietnamese_with_or_without_diacritics(self):
        self.assertEqual(
            VectorDBManager._tokens("hộ chiếu"),
            VectorDBManager._tokens("ho chieu"),
        )

    def test_accented_and_unaccented_d_queries_retrieve_same_passage(self):
        collection = Mock()
        collection.count.return_value = 2
        collection.get.return_value = {
            "ids": ["procedure:0", "fees:0"],
            "documents": [
                "Đơn trình báo mất hộ chiếu phổ thông.",
                "Thông tin về lệ phí cấp hộ chiếu.",
            ],
            "metadatas": [
                {"title": "Thủ tục xuất nhập cảnh"},
                {"title": "Lệ phí"},
            ],
        }
        manager = object.__new__(VectorDBManager)
        manager.get_collection = Mock(return_value=collection)

        with patch.object(manager, "_dense_query", return_value=[]):
            accented_result = manager.query(
                "default", "đơn trình báo", n_results=1, retrieval_mode="hybrid"
            )
            unaccented_result = manager.query(
                "default", "don trinh bao", n_results=1, retrieval_mode="hybrid"
            )

        self.assertEqual([item["chunk_id"] for item in accented_result], ["procedure:0"])
        self.assertEqual(
            [item["chunk_id"] for item in unaccented_result], ["procedure:0"]
        )

    def test_bm25_uses_section_path_to_rank_processing_deadline(self):
        collection = Mock()
        collection.count.return_value = 2
        collection.get.return_value = {
            "ids": ["procedure:0", "procedure:1"],
            "documents": [
                "08 Ngày làm việc nộp hồ sơ trực tuyến qua Cổng dịch vụ công.",
                "Người đề nghị nộp hộ chiếu và tờ khai theo quy định.",
            ],
            "metadatas": [
                {
                    "title": "Cấp hộ chiếu phổ thông",
                    "section_path": "Thời hạn giải quyết",
                },
                {
                    "title": "Cấp hộ chiếu phổ thông",
                    "section_path": "Thành phần hồ sơ",
                },
            ],
        }
        manager = object.__new__(VectorDBManager)
        manager.get_collection = Mock(return_value=collection)

        with patch.object(manager, "_dense_query", return_value=[]):
            results = manager.query(
                "immigration",
                "Thời gian cấp hộ chiếu cho người đủ 14 tuổi trở lên",
                n_results=2,
                retrieval_mode="hybrid",
            )

        self.assertEqual(results[0]["chunk_id"], "procedure:0")
        self.assertGreater(results[0]["bm25_score"], results[1]["bm25_score"])

    def test_deadline_section_boost_requires_matching_subject_and_heading(self):
        query = "Thời gian cấp hộ chiếu cho người đủ 14 tuổi trở lên"
        matching = VectorDBManager._deadline_relevance_boost(
            query,
            {
                "title": "Cấp hộ chiếu phổ thông ở trong nước",
                "section_path": "Thời hạn giải quyết",
            },
        )
        unrelated = VectorDBManager._deadline_relevance_boost(
            query,
            {
                "title": "Trình báo mất hộ chiếu phổ thông",
                "section_path": "Thời hạn giải quyết",
            },
        )
        wrong_section = VectorDBManager._deadline_relevance_boost(
            query,
            {
                "title": "Cấp hộ chiếu phổ thông ở trong nước",
                "section_path": "Thành phần hồ sơ",
            },
        )

        self.assertGreater(matching, unrelated)
        self.assertEqual(unrelated, 0)
        self.assertEqual(wrong_section, 0)

    def test_reindex_five_chunks_to_three_removes_stale_vector_and_jsonl_rows(self):
        old_metadata = {
            "doc_id": "doc-1",
            "url": "https://example.org/page",
            "title": "Old title",
            "section_path": "Old section",
            "token_count": 1,
            "fetched_at": "2026-01-01",
            "collection": "default",
        }
        def make_chunk(ordinal):
            return Chunk(
                chunk_id=f"doc-1:{ordinal}",
                doc_id="doc-1",
                ordinal=ordinal,
                text=f"new chunk {ordinal}",
                embed_text=f"New title > New section: new chunk {ordinal}",
                section_path=["New section"],
                token_count=3,
                url="https://example.org/page",
                title="New title",
                fetched_at="2026-01-02",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_vector_manager(temp_dir)
            collection = manager.get_collection("default")
            collection.upsert(
                ids=[f"doc-1:{ordinal}" for ordinal in range(5)],
                embeddings=[[0.1, 0.2] for _ in range(5)],
                documents=[f"old chunk {ordinal}" for ordinal in range(5)],
                metadatas=[old_metadata.copy() for _ in range(5)],
            )
            storage = StorageManager(Path(temp_dir))
            storage.append_chunks([make_chunk(ordinal) for ordinal in range(5)])
            storage.remove_doc_files("doc-1")
            storage.append_chunks([make_chunk(ordinal) for ordinal in range(3)])
            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.1, 0.2] for _ in range(3)],
            ) as embed:
                result = manager.index_chunks_file(storage.chunks_file)
            saved_chunks = [
                json.loads(line)
                for line in storage.chunks_file.read_text(encoding="utf-8").splitlines()
            ]
            indexed_chunks = collection.get(include=["documents", "metadatas"])

        self.assertEqual(result, {"default": 3})
        self.assertEqual(embed.call_count, 1)
        self.assertEqual(len(embed.call_args.args[0]), 3)
        self.assertEqual(
            [chunk["chunk_id"] for chunk in saved_chunks],
            ["doc-1:0", "doc-1:1", "doc-1:2"],
        )
        self.assertEqual(
            set(indexed_chunks["ids"]),
            {"doc-1:0", "doc-1:1", "doc-1:2"},
        )
        self.assertEqual(
            set(indexed_chunks["documents"]),
            {"new chunk 0", "new chunk 1", "new chunk 2"},
        )

    def test_replace_doc_embedding_failure_keeps_old_chunks(self):
        old_chunk = self.make_vector_chunk("doc-1", 0, text="old content")
        new_chunk = self.make_vector_chunk("doc-1", 0, text="new content")

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_vector_manager(temp_dir)
            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.1, 0.2]],
            ):
                manager.index_chunks([old_chunk])

            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                side_effect=RuntimeError("embedding failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "embedding failed"):
                    manager.replace_doc("doc-1", "default", [new_chunk])

            indexed = manager.get_collection("default").get(
                where={"doc_id": "doc-1"},
                include=["documents"],
            )

        self.assertEqual(indexed["ids"], ["doc-1:0"])
        self.assertEqual(indexed["documents"], ["old content"])

    def test_replace_doc_removes_stale_chunks_when_new_version_is_shorter(self):
        old_chunks = [
            self.make_vector_chunk("doc-1", ordinal, text=f"old {ordinal}")
            for ordinal in range(5)
        ]
        new_chunks = [
            self.make_vector_chunk("doc-1", ordinal, text=f"new {ordinal}")
            for ordinal in range(3)
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_vector_manager(temp_dir)
            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.1, 0.2] for _ in range(5)],
            ):
                manager.index_chunks(old_chunks)

            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.3, 0.4] for _ in new_chunks],
            ):
                manager.replace_doc("doc-1", "default", new_chunks)

            indexed = manager.get_collection("default").get(
                where={"doc_id": "doc-1"},
                include=["documents"],
            )

        self.assertEqual(indexed["ids"], ["doc-1:0", "doc-1:1", "doc-1:2"])
        self.assertEqual(indexed["documents"], ["new 0", "new 1", "new 2"])

    def test_replace_doc_is_idempotent_for_the_same_chunks(self):
        chunks = [self.make_vector_chunk("doc-1", 0, text="same content")]

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_vector_manager(temp_dir)
            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.1, 0.2]],
            ) as embed:
                manager.replace_doc("doc-1", "default", chunks)
                manager.replace_doc("doc-1", "default", chunks)

            indexed = manager.get_collection("default").get(
                where={"doc_id": "doc-1"},
                include=["documents"],
            )

        self.assertEqual(embed.call_count, 2)
        self.assertEqual(indexed["ids"], ["doc-1:0"])
        self.assertEqual(indexed["documents"], ["same content"])

    def test_replace_doc_cleans_old_collection_only_after_new_index_succeeds(self):
        old_chunk = self.make_vector_chunk(
            "doc-1", 0, collection="collection-a", text="old content"
        )
        new_chunk = self.make_vector_chunk(
            "doc-1", 0, collection="collection-b", text="new content"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_vector_manager(temp_dir)
            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                return_value=[[0.1, 0.2]],
            ):
                manager.index_chunks([old_chunk])

            with patch(
                "webrag.index.vectordb.get_embeddings_batch",
                side_effect=[
                    RuntimeError("embedding failed"),
                    [[0.3, 0.4]],
                ],
            ):
                with self.assertRaisesRegex(RuntimeError, "embedding failed"):
                    manager.replace_doc("doc-1", "collection-b", [new_chunk])

                old_after_failure = manager.get_collection("collection-a").get(
                    where={"doc_id": "doc-1"},
                    include=["documents"],
                )
                manager.replace_doc("doc-1", "collection-b", [new_chunk])

            old_after_success = manager.get_collection("collection-a").get(
                where={"doc_id": "doc-1"},
                include=["documents"],
            )
            new_after_success = manager.get_collection("collection-b").get(
                where={"doc_id": "doc-1"},
                include=["documents"],
            )

        self.assertEqual(old_after_failure["documents"], ["old content"])
        self.assertEqual(old_after_success["ids"], [])
        self.assertEqual(new_after_success["documents"], ["new content"])


if __name__ == "__main__":
    unittest.main()
