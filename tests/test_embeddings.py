from contextlib import closing
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from webrag.index.embed import (
    EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBED_MODEL,
    embedding_cache_path,
    get_embedding,
    get_embeddings_batch,
)


class EmbeddingBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temp_dir.name) / "embeddings.sqlite3"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bge_m3_is_the_default_embedding_model(self):
        self.assertEqual(DEFAULT_EMBED_MODEL, "bge-m3:latest")

    def test_embedding_cache_file_is_adjacent_to_chroma_directory(self):
        chroma_path = Path("data") / "chroma-test"

        self.assertEqual(
            embedding_cache_path(chroma_path),
            Path("data") / "chroma-test_embedding_cache.sqlite3",
        )

    def test_empty_input_does_not_make_an_ollama_request(self):
        with patch("webrag.index.embed.httpx.Client") as client_class:
            self.assertEqual(get_embeddings_batch([]), [])
            client_class.assert_not_called()

    def test_embeddings_are_requested_in_ordered_bounded_batches(self):
        texts = [f"chunk {index}" for index in range(EMBEDDING_BATCH_SIZE + 1)]
        first_vectors = [[float(index)] for index in range(EMBEDDING_BATCH_SIZE)]
        last_vector = [[float(EMBEDDING_BATCH_SIZE)]]

        client = Mock()
        client.post.side_effect = [
            Mock(json=Mock(return_value={"embeddings": first_vectors})),
            Mock(json=Mock(return_value={"embeddings": last_vector})),
        ]
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=None)

        with patch("webrag.index.embed.httpx.Client", return_value=context):
            result = get_embeddings_batch(
                texts,
                model="nomic-embed-text:latest",
                api_base="http://ollama.test",
                cache_path=self.cache_path,
            )

        self.assertEqual(result, first_vectors + last_vector)
        self.assertEqual(client.post.call_count, 2)
        self.assertEqual(
            client.post.call_args_list[0].kwargs["json"]["input"],
            [f"search_document: {text}" for text in texts[:EMBEDDING_BATCH_SIZE]],
        )
        self.assertEqual(
            client.post.call_args_list[1].kwargs["json"]["input"],
            [
                f"search_document: {text}"
                for text in texts[EMBEDDING_BATCH_SIZE:]
            ],
        )

    def test_query_embeddings_use_nomic_query_prefix(self):
        client = Mock()
        client.post.return_value = Mock(
            json=Mock(return_value={"embedding": [0.1, 0.2]})
        )
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=None)

        with patch("webrag.index.embed.httpx.Client", return_value=context):
            result = get_embedding("where to apply?", model="nomic-embed-text:latest")

        self.assertEqual(result, [0.1, 0.2])
        self.assertEqual(
            client.post.call_args.kwargs["json"],
            {
                "model": "nomic-embed-text:latest",
                "prompt": "search_query: where to apply?",
            },
        )

    def test_models_without_prefix_configuration_keep_text_unchanged(self):
        from webrag.index.embed import add_prefix

        self.assertEqual(add_prefix("sample", "bge-m3", "document"), "sample")
        self.assertEqual(add_prefix("sample", "bge-m3", "query"), "sample")

    def test_qwen3_embedding_uses_query_instruction_without_document_prefix(self):
        from webrag.index.embed import add_prefix

        self.assertEqual(
            add_prefix("passport time?", "qwen3-embedding:0.6b", "query"),
            "Instruct: Given a search query, retrieve relevant passages that answer "
            "the query\nQuery: passport time?",
        )
        self.assertEqual(
            add_prefix("passport passage", "qwen3-embedding:0.6b", "document"),
            "passport passage",
        )

    def test_unexpected_embedding_count_is_reported(self):
        client = Mock()
        client.post.return_value = Mock(
            json=Mock(return_value={"embeddings": [[0.1]]})
        )
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=None)

        with patch("webrag.index.embed.httpx.Client", return_value=context):
            with self.assertRaisesRegex(RuntimeError, "unexpected number"):
                get_embeddings_batch(
                    ["first", "second"],
                    cache_path=self.cache_path,
                )

    def test_cached_and_uncached_vectors_are_identical(self):
        expected = [[0.1, 0.2], [0.3, 0.4]]
        client = Mock()
        client.post.return_value = Mock(
            json=Mock(return_value={"embeddings": expected})
        )
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=None)

        with patch("webrag.index.embed.httpx.Client", return_value=context):
            uncached = get_embeddings_batch(
                ["first", "second"], cache_path=self.cache_path
            )

        with patch("webrag.index.embed.httpx.Client") as cached_client:
            cached = get_embeddings_batch(
                ["first", "second"], cache_path=self.cache_path
            )

        self.assertEqual(cached, uncached)
        cached_client.assert_not_called()

    def test_cache_key_uses_model_name_and_prefixed_document_text(self):
        context = Mock()
        client = Mock()
        client.post.return_value = Mock(
            json=Mock(return_value={"embeddings": [[1.0, 2.0]]})
        )
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=None)
        with patch("webrag.index.embed.httpx.Client", return_value=context):
            get_embeddings_batch(
                ["passage"],
                model="nomic-embed-text:latest",
                cache_path=self.cache_path,
            )

        with closing(sqlite3.connect(self.cache_path)) as connection:
            cached_key = connection.execute(
                "SELECT cache_key FROM embeddings"
            ).fetchone()[0]

        expected_key = hashlib.sha256(
            b"nomic-embed-text:latestsearch_document: passage"
        ).hexdigest()
        self.assertEqual(cached_key, expected_key)

    def test_only_cache_misses_are_requested_and_original_order_is_preserved(self):
        client = Mock()
        client.post.side_effect = [
            Mock(json=Mock(return_value={"embeddings": [[1.0, 1.5], [2.0, 2.5]]})),
            Mock(json=Mock(return_value={"embeddings": [[3.0, 3.5], [4.0, 4.5]]})),
        ]
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=None)
        with patch("webrag.index.embed.httpx.Client", return_value=context):
            get_embeddings_batch(
                ["cached-a", "cached-b"], cache_path=self.cache_path
            )

        miss_client = Mock()
        miss_client.post.return_value = Mock(
            json=Mock(return_value={"embeddings": [[8.0, 8.5], [9.0, 9.5]]})
        )
        miss_context = Mock()
        miss_context.__enter__ = Mock(return_value=miss_client)
        miss_context.__exit__ = Mock(return_value=None)
        stats = {}
        with patch("webrag.index.embed.httpx.Client", return_value=miss_context):
            result = get_embeddings_batch(
                ["missing-a", "cached-b", "missing-b", "cached-a"],
                cache_path=self.cache_path,
                cache_stats=stats,
            )

        self.assertEqual(
            miss_client.post.call_args.kwargs["json"]["input"],
            ["missing-a", "missing-b"],
        )
        self.assertEqual(
            result,
            [[8.0, 8.5], [2.0, 2.5], [9.0, 9.5], [1.0, 1.5]],
        )
        self.assertEqual(stats, {"hits": 2, "misses": 2, "total": 4})

    def test_changed_model_name_is_a_cache_miss(self):
        def mock_context(vector):
            client = Mock()
            client.post.return_value = Mock(
                json=Mock(return_value={"embeddings": [vector]})
            )
            context = Mock()
            context.__enter__ = Mock(return_value=client)
            context.__exit__ = Mock(return_value=None)
            return context, client

        first_context, _ = mock_context([1.0, 2.0])
        with patch(
            "webrag.index.embed.httpx.Client", return_value=first_context
        ):
            get_embeddings_batch(
                ["same text"],
                model="model-a",
                cache_path=self.cache_path,
            )

        second_context, second_client = mock_context([3.0, 4.0])
        with patch(
            "webrag.index.embed.httpx.Client", return_value=second_context
        ):
            result = get_embeddings_batch(
                ["same text"],
                model="model-b",
                cache_path=self.cache_path,
            )

        self.assertEqual(result, [[3.0, 4.0]])
        second_client.post.assert_called_once()

    def test_wrong_cached_dimension_is_treated_as_a_miss(self):
        context = Mock()
        client = Mock()
        client.post.return_value = Mock(
            json=Mock(return_value={"embeddings": [[5.0, 6.0]]})
        )
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=None)
        with patch("webrag.index.embed.httpx.Client", return_value=context):
            get_embeddings_batch(["text"], cache_path=self.cache_path)

        with closing(sqlite3.connect(self.cache_path)) as connection, connection:
            connection.execute("UPDATE embeddings SET dimension = 3")

        refreshed_context = Mock()
        refreshed_client = Mock()
        refreshed_client.post.return_value = Mock(
            json=Mock(return_value={"embeddings": [[7.0, 8.0]]})
        )
        refreshed_context.__enter__ = Mock(return_value=refreshed_client)
        refreshed_context.__exit__ = Mock(return_value=None)
        with patch(
            "webrag.index.embed.httpx.Client", return_value=refreshed_context
        ):
            result = get_embeddings_batch(["text"], cache_path=self.cache_path)

        self.assertEqual(result, [[7.0, 8.0]])
        refreshed_client.post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
