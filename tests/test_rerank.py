import unittest
from unittest.mock import Mock, patch

from webrag.index.rerank import rerank_chunks, reranker_device


class RerankTests(unittest.TestCase):
    def test_rerank_sorts_by_cross_encoder_score_and_keeps_metadata(self):
        chunks = [
            {"chunk_id": "first", "text": "first passage", "metadata": {"title": "A"}},
            {"chunk_id": "second", "text": "second passage", "metadata": {"title": "B"}},
        ]
        model = Mock()
        model.predict.return_value = [0.2, 0.9]

        with patch(
            "webrag.index.rerank.get_reranker", return_value=model
        ) as get_reranker:
            results = rerank_chunks("question", chunks, 1)

        self.assertEqual([chunk["chunk_id"] for chunk in results], ["second"])
        self.assertEqual(results[0]["reranker_score"], 0.9)
        self.assertEqual(results[0]["metadata"], {"title": "B"})
        model.predict.assert_called_once_with(
            [
                ("question", "Title: A\nSection: \n\nfirst passage"),
                ("question", "Title: B\nSection: \n\nsecond passage"),
            ],
            batch_size=8,
            show_progress_bar=False,
        )
        get_reranker.assert_called_once_with("cpu", 256)

    def test_rerank_validates_output_count(self):
        with self.assertRaises(ValueError):
            rerank_chunks("question", [{"chunk_id": "first", "text": "passage"}], 0)

    def test_single_candidate_does_not_load_model(self):
        chunk = {"chunk_id": "only", "text": "passage"}

        with patch("webrag.index.rerank.get_reranker") as get_reranker:
            self.assertEqual(rerank_chunks("question", [chunk], 5), [chunk])

        get_reranker.assert_not_called()

    def test_device_uses_gpu_for_gemini_only_when_cuda_is_available(self):
        with patch("webrag.index.rerank.torch.cuda.is_available", return_value=True):
            self.assertEqual(reranker_device("gemini"), "cuda")
            self.assertIsNone(reranker_device("ollama"))

    def test_device_skips_production_reranking_without_cuda(self):
        with patch("webrag.index.rerank.torch.cuda.is_available", return_value=False):
            self.assertIsNone(reranker_device("gemini"))


if __name__ == "__main__":
    unittest.main()
