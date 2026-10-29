import unittest

from webrag.chunk.markdown import split_long_text


class SplitLongTextTests(unittest.TestCase):
    def test_preserves_table_and_list_line_boundaries(self):
        text = (
            "Hình thức nộp | Thời hạn giải quyết\n"
            "Trực tiếp | 08 Ngày làm việc\n"
            "Trực tuyến | 08 Ngày làm việc\n"
            "- Gửi hồ sơ qua bưu chính"
        )

        chunks = split_long_text(text, max_words=30, overlap_words=0)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)
        self.assertIn("Trực tiếp | 08 Ngày làm việc\nTrực tuyến", chunks[0])

    def test_splits_oversized_lines_and_retains_whole_line_overlap(self):
        text = (
            "Header one two\n"
            "Row A B C D\n"
            "Row E F G H\n"
            "A very long line with enough words to exceed a small chunk size"
        )

        chunks = split_long_text(text, max_words=7, overlap_words=2)

        self.assertGreater(len(chunks), 1)
        self.assertIn("Row A B C D", "\n".join(chunks))
        self.assertIn("A very long line with enough words", "\n".join(chunks))
        for chunk in chunks:
            self.assertLessEqual(len(chunk.split()), 7)

    def test_rejects_non_positive_chunk_size(self):
        with self.assertRaisesRegex(ValueError, "max_words"):
            split_long_text("some text", max_words=0)


if __name__ == "__main__":
    unittest.main()
