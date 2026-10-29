import unittest
from unittest.mock import Mock, patch

from webrag.index.embed import (
    EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBED_MODEL,
    get_embedding,
    get_embeddings_batch,
)


class EmbeddingBatchTests(unittest.TestCase):
    def test_bge_m3_is_the_default_embedding_model(self):
        self.assertEqual(DEFAULT_EMBED_MODEL, "bge-m3:latest")

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
                get_embeddings_batch(["first", "second"])


if __name__ == "__main__":
    unittest.main()
