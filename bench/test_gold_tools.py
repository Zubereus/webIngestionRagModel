import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grep_snapshots import fold_regex_literals, search_snapshots
from snapshot_utils import Snapshot, load_snapshots, span_offsets
from verify_cases import (
    apply_span_edit,
    choose_expected_page,
    display_check_pattern_results,
    filter_cases,
    main,
    run_check_patterns,
    update_acceptable_urls,
    validate_answer_spans,
)


class GoldToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = load_snapshots()

    def test_span_guard_rejects_nonmatching_answer(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_answer_spans("Expected text here.", ["different text"])

    def test_span_guard_requires_every_answer_any_entry(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_answer_spans("first fact only", ["first fact", "missing fact"])

    def test_edit_recomputes_counts_and_other_pages(self):
        pages = [
            Snapshot("https://example.test/target", "target.html", "Target", "A revised fact is here."),
            Snapshot("https://example.test/other", "other.html", "Other", "A revised fact is here too."),
            Snapshot("https://example.test/third", "third.html", "Third", "Unrelated."),
        ]
        case = {
            "id": "test-case",
            "expected_url": "https://example.test/target",
            "snapshot_path": "target.html",
            "answer_span": "old fact",
            "status": "TODO: verify",
            "acceptable_urls": [{"url": "old"}],
            "acceptable_urls_status": "TODO: verify",
        }

        apply_span_edit(case, 0, "revised fact", pages[0].markdown, pages)

        self.assertEqual(case["old_span"], "old fact")
        self.assertEqual(case["answer_span"], "revised fact")
        self.assertEqual(case["status"], "TODO: verify")
        self.assertEqual(case["acceptable_urls"], [])
        self.assertEqual(case["acceptable_urls_status"], "TODO: verify")
        self.assertEqual(case["span_page_counts"][0]["snapshot_page_count"], 2)
        self.assertEqual(case["pages_with_any_span_count"], 2)
        self.assertEqual(case["other_pages_with_same_answer"][0]["url"], "https://example.test/other")

    def test_edit_rejects_nonmatching_span_without_changing_case(self):
        page = Snapshot("https://example.test/target", "target.html", "Target", "A known fact.")
        case = {
            "expected_url": page.url,
            "snapshot_path": page.snapshot_path,
            "answer_span": "known fact",
            "status": "TODO: verify",
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            apply_span_edit(case, 0, "missing fact", page.markdown, [page])
        self.assertEqual(case["answer_span"], "known fact")

    def test_grep_finds_known_snapshot_string(self):
        results = search_snapshots(self.pages, r"3\.0 million parameters")
        self.assertTrue(
            any(page.url == "https://arxiv.org/html/2510.09653v4" for page, _ in results)
        )

    def test_grep_fold_ignores_accents_in_text_and_regex(self):
        page = Snapshot("https://example.test", "example.html", "Example", "Thời hạn là 08 ngày.")
        self.assertEqual(search_snapshots([page], "thoi han", fold=True)[0][0], page)
        self.assertEqual(search_snapshots([page], "thời hạn", fold=True)[0][0], page)
        self.assertEqual(search_snapshots([page], "thoi han", fold=False), [])

    def test_grep_fold_preserves_regex_escape_case(self):
        regex = r"Thời\S+ hạn\D\W\B"
        self.assertEqual(fold_regex_literals(regex), r"thoi\S+ han\D\W\B")
        page = Snapshot("https://example.test", "example.html", "Example", "Thời-gian hạnx-yz")
        self.assertEqual(search_snapshots([page], r"thời\S+ hạn", fold=True)[0][0], page)

    def test_check_patterns_returns_at_most_two_hits_each_and_eight_total(self):
        patterns = [f"pattern-{index}" for index in range(6)]
        pages = [
            Snapshot(f"https://example.test/{index}", f"{index}.html", str(index),
                     " ".join(patterns) + " pattern-0 pattern-1")
            for index in range(4)
        ]
        results = run_check_patterns({"check_patterns": patterns}, pages)
        counts = {}
        for pattern, _, _ in results:
            counts[pattern] = counts.get(pattern, 0) + 1
        self.assertLessEqual(len(results), 8)
        self.assertTrue(all(count <= 2 for count in counts.values()))

    def test_check_pattern_results_are_grouped_under_pattern_headers(self):
        first = Snapshot("https://example.test/one", "one.html", "One", "First result.")
        second = Snapshot("https://example.test/two", "two.html", "Two", "Second result.")
        output = io.StringIO()
        with patch("sys.stdout", output):
            display_check_pattern_results([("needle", first, "first"), ("needle", second, "second")])
        lines = output.getvalue().splitlines()
        self.assertEqual(lines.count("  Pattern /needle/:"), 1)
        self.assertLess(lines.index("  Pattern /needle/:"), lines.index("    - https://example.test/one — One"))

    def test_expected_page_selection_sets_page_fields_without_changing_answerable(self):
        page = Snapshot(
            "https://fastapi.tiangolo.com/tutorial/first-steps/",
            "data/raw/fastapi.html",
            "First Steps",
            "Known page text",
        )
        case = {"answerable": False}
        with patch("builtins.input", return_value="1"):
            choose_expected_page(case, [page])
        self.assertEqual(case["expected_url"], page.url)
        self.assertEqual(case["snapshot_path"], page.snapshot_path)
        self.assertEqual(case["site_group"], "FastAPI docs")
        self.assertFalse(case["answerable"])

    def test_reclassified_answerable_case_requires_expected_page_before_span_edit(self):
        page = Snapshot("https://example.test/target", "target.html", "Target", "A known fact.")
        with tempfile.TemporaryDirectory() as directory:
            draft_path = Path(directory) / "draft.jsonl"
            original = {
                "id": "reclassified",
                "type": "near_miss",
                "answerable": False,
                "site_group": "test",
                "question": "Where is the fact?",
                "status": "TODO: verify",
            }
            draft_path.write_text(json.dumps(original) + "\n", encoding="utf-8")
            with (
                patch("sys.argv", ["verify_cases.py", "--draft", str(draft_path)]),
                patch("verify_cases.load_snapshots", return_value=[page]),
                patch("builtins.input", side_effect=["t", "answerable", EOFError]),
            ):
                self.assertEqual(main(), 0)
            saved = json.loads(draft_path.read_text(encoding="utf-8"))
            self.assertTrue(saved["expected_page_selection_required"])

            with (
                patch("sys.argv", ["verify_cases.py", "--draft", str(draft_path)]),
                patch("verify_cases.load_snapshots", return_value=[page]),
                patch("builtins.input", side_effect=["e", EOFError]),
            ):
                self.assertEqual(main(), 0)
            saved = json.loads(draft_path.read_text(encoding="utf-8"))
            self.assertNotIn("answer_span", saved)

            with (
                patch("sys.argv", ["verify_cases.py", "--draft", str(draft_path)]),
                patch("verify_cases.load_snapshots", return_value=[page]),
                patch("builtins.input", side_effect=["x", "1", EOFError]),
            ):
                self.assertEqual(main(), 0)
            saved = json.loads(draft_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["expected_url"], page.url)
            self.assertTrue(saved["answerable"])
            self.assertNotIn("expected_page_selection_required", saved)

            with (
                patch("sys.argv", ["verify_cases.py", "--draft", str(draft_path)]),
                patch("verify_cases.load_snapshots", return_value=[page]),
                patch("builtins.input", side_effect=["e", "known fact", EOFError]),
            ):
                self.assertEqual(main(), 0)
            saved = json.loads(draft_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["answer_span"], "known fact")

    def test_section_scoped_span_is_not_counted_outside_section(self):
        markdown = "## Lệ Phí\nKhông\n\n## Thành phần hồ sơ\nKhông"
        offsets = span_offsets(markdown, "không", "Lệ Phí")
        self.assertEqual(len(offsets), 1)

    def test_case_filters_match_type_group_and_id(self):
        cases = [
            {"id": "a", "type": "answerable", "site_group": "arXiv"},
            {"id": "b", "type": "near_miss", "site_group": "arXiv"},
            {"id": "c", "type": "answerable", "site_group": "FastAPI docs"},
        ]
        filtered = filter_cases(cases, ["answerable"], ["arXiv"], ["a", "c"])
        self.assertEqual([case["id"] for case in filtered], ["a"])

    def test_eof_saves_current_case_for_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            draft_path = Path(directory) / "draft.jsonl"
            draft_path.write_text(
                '{"id":"resume-me","type":"near_miss","site_group":"arXiv","status":"TODO: verify"}\n',
                encoding="utf-8",
            )
            with (
                patch("sys.argv", ["verify_cases.py", "--draft", str(draft_path)]),
                patch("verify_cases.load_snapshots", return_value=[]),
                patch("builtins.input", side_effect=EOFError),
            ):
                self.assertEqual(main(), 0)
            state_path = draft_path.parent / f".{draft_path.name}.state.json"
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["next_id"], "resume-me")

    def test_verifier_refuses_to_mark_nonmatching_answerable_case(self):
        page = Snapshot("https://example.test/target", "target.html", "Target", "A known fact.")
        with tempfile.TemporaryDirectory() as directory:
            draft_path = Path(directory) / "draft.jsonl"
            original = {
                "id": "guard-me",
                "type": "answerable",
                "answerable": True,
                "site_group": "test",
                "question": "Where is the missing fact?",
                "expected_url": page.url,
                "snapshot_path": page.snapshot_path,
                "status": "TODO: verify",
                "answer_span": "missing fact",
            }
            draft_path.write_text(json.dumps(original) + "\n", encoding="utf-8")
            with (
                patch("sys.argv", ["verify_cases.py", "--draft", str(draft_path)]),
                patch("verify_cases.load_snapshots", return_value=[page]),
                patch("builtins.input", side_effect=["v", EOFError]),
            ):
                self.assertEqual(main(), 0)
            saved = json.loads(draft_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "TODO: verify")

    def test_acceptable_url_picker_records_user_selection(self):
        pages = [
            Snapshot("https://example.test/one", "one.html", "First", "A shared fact."),
            Snapshot("https://example.test/two", "two.html", "Second", "A shared fact."),
        ]
        case = {"answer_span": "shared fact"}
        with patch("builtins.input", return_value="2"):
            update_acceptable_urls(case, pages)
        self.assertEqual(case["acceptable_urls"][0]["url"], pages[1].url)
        self.assertEqual(case["acceptable_urls_status"], "verified")


if __name__ == "__main__":
    unittest.main()
