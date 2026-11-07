#!/usr/bin/env python
"""Interactively verify retrieval-gold cases against frozen local snapshots."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from snapshot_utils import (
    ROOT,
    Snapshot,
    load_snapshots,
    matching_pages,
    span_offsets,
    spans_from_case,
)


DEFAULT_DRAFT = ROOT / "bench" / "retrieval_gold_draft.jsonl"
VALID_TYPES = {"answerable", "near_miss", "off_topic", "ambiguous", "partial"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def normalized_url(url: str | None) -> str:
    return url.rstrip("/") if url else ""


def validate_answer_spans(markdown: str, spans: list[str], section_path_contains: str | None = None) -> None:
    if not spans:
        raise ValueError("Answerable case has no answer span.")
    missing = [
        span
        for span in spans
        if not span_offsets(markdown, span, section_path_contains)
    ]
    if missing:
        raise ValueError(f"Span does not match the extracted expected-page snapshot: {missing!r}")


def recompute_span_page_data(case: dict[str, Any], pages: list[Snapshot]) -> None:
    spans = spans_from_case(case)
    section = case.get("section_path_contains")
    hits = matching_pages(pages, spans, section)
    case["span_page_counts"] = [
        {
            "span": span,
            "snapshot_page_count": sum(
                bool(span_offsets(page.markdown, span, section))
                for page in pages
            ),
            "urls": [
                page.url
                for page in pages
                if span_offsets(page.markdown, span, section)
            ],
        }
        for span in spans
    ]
    case["pages_with_any_span_count"] = len(hits)
    expected_url = normalized_url(case.get("expected_url"))
    case["other_pages_with_same_answer"] = [
        {
            "url": page.url,
            "title": page.title,
            "matched_spans": matched_spans,
        }
        for page, matched_spans in hits.values()
        if normalized_url(page.url) != expected_url
    ]
    expected_page = next(
        (
            page
            for page in pages
            if normalized_url(page.snapshot_path) == normalized_url(case.get("snapshot_path"))
            or normalized_url(page.url) == expected_url
        ),
        None,
    )
    case["found_exact"] = bool(
        expected_page
        and spans
        and all(span_offsets(expected_page.markdown, span, section) for span in spans)
    )


def apply_span_edit(
    case: dict[str, Any],
    span_index: int,
    new_span: str,
    expected_markdown: str,
    pages: list[Snapshot],
) -> None:
    spans = spans_from_case(case)
    if not spans:
        spans = [""]
        span_index = 0
    if span_index < 0 or span_index >= len(spans):
        raise ValueError(f"Span number is out of range: {span_index + 1}")
    if not span_offsets(expected_markdown, new_span, case.get("section_path_contains")):
        raise ValueError("New span does not match the extracted expected-page snapshot.")

    previous_span = spans[span_index]
    if previous_span:
        old_spans = case.get("old_span")
        if old_spans is None:
            case["old_span"] = previous_span
        elif isinstance(old_spans, list):
            old_spans.append(previous_span)
        else:
            case["old_span"] = [old_spans, previous_span]

    spans[span_index] = new_span
    if len(spans) > 1 or isinstance(case.get("answer_any"), list):
        case["answer_any"] = spans
        case.pop("answer_span", None)
    else:
        case["answer_span"] = spans[0]
        case.pop("answer_any", None)
    case["status"] = "TODO: verify"
    case["acceptable_urls"] = []
    case["acceptable_urls_status"] = "TODO: verify"
    recompute_span_page_data(case, pages)


def display_context(markdown: str, span: str, section: str | None = None) -> list[str]:
    contexts = []
    for start, end in span_offsets(markdown, span, section):
        left, right = max(0, start - 150), min(len(markdown), end + 150)
        contexts.append(re.sub(r"\s+", " ", markdown[left:right]).strip())
    return contexts


def run_check_patterns(case: dict[str, Any], pages: list[Snapshot]) -> list[tuple[str, Snapshot, str]]:
    results = []
    for pattern_text in case.get("check_patterns", []):
        try:
            pattern = re.compile(pattern_text, re.IGNORECASE)
        except re.error as error:
            print(f"Invalid check_patterns regex {pattern_text!r}: {error}")
            continue
        pattern_results = []
        for page in pages:
            match = pattern.search(page.markdown)
            if not match:
                continue
            left = max(0, match.start() - 150)
            right = min(len(page.markdown), match.end() + 150)
            context = re.sub(r"\s+", " ", page.markdown[left:right]).strip()
            pattern_results.append((pattern_text, page, context))
            if len(pattern_results) >= 2:
                break
        results.extend(pattern_results)
        if len(results) >= 8:
            return results[:8]
    return results


def site_group_for_page(page: Snapshot) -> str:
    if "arxiv.org" in page.url:
        return "arXiv"
    if "fastapi.tiangolo.com" in page.url:
        return "FastAPI docs"
    if "dichvucong.bocongan.gov.vn" in page.url:
        return "Bo Cong an portal"
    if "wikipedia.org" in page.url:
        return "Wikipedia"
    if "docs.python.org" in page.url:
        return "Python docs"
    return page.url.split("/")[2]


def set_expected_page(case: dict[str, Any], page: Snapshot) -> None:
    case["expected_url"] = page.url
    case["snapshot_path"] = page.snapshot_path
    case["snapshot_exists"] = True
    case["expected_page_title"] = page.title
    case["site_group"] = site_group_for_page(page)
    case["acceptable_urls"] = []
    case["acceptable_urls_status"] = "TODO: verify"
    case.pop("expected_page_selection_required", None)


def choose_expected_page(case: dict[str, Any], pages: list[Snapshot]) -> None:
    print("Choose the expected page number:")
    for index, page in enumerate(pages, 1):
        print(f"  {index}. {page.url} — {page.title}")
    try:
        selected = int(input("> ").strip())
    except ValueError as error:
        raise ValueError("Enter one page number.") from error
    if selected < 1 or selected > len(pages):
        raise ValueError("Page number is out of range.")
    set_expected_page(case, pages[selected - 1])


def display_check_pattern_results(results: list[tuple[str, Snapshot, str]]) -> None:
    previous_pattern: str | None = None
    for pattern, page, context in results:
        if pattern != previous_pattern:
            print(f"  Pattern /{pattern}/:")
            previous_pattern = pattern
        print(f"    - {page.url} — {page.title}")
        print(f"      Context: {context}")


def display_case(case: dict[str, Any], pages: list[Snapshot]) -> None:
    print("\n" + "=" * 80)
    print(f"{case.get('id', '(no id)')} | {case.get('type', case.get('proposed_type', 'unlabeled'))}")
    print(f"Question: {case.get('question', '')}")
    print(f"Expected URL: {case.get('expected_url') or '(none)'}")
    if case.get("section_path_contains"):
        print(f"Section path contains: {case['section_path_contains']}")
    expected_page = next(
        (
            page
            for page in pages
            if normalized_url(page.snapshot_path) == normalized_url(case.get("snapshot_path"))
            or normalized_url(page.url) == normalized_url(case.get("expected_url"))
        ),
        None,
    )
    spans = spans_from_case(case)
    if spans:
        print("Answer span(s):")
        for index, span in enumerate(spans, 1):
            print(f"  {index}. {span}")
            contexts = display_context(
                expected_page.markdown if expected_page else "",
                span,
                case.get("section_path_contains"),
            )
            for context in contexts:
                print(f"     Context: {context}")
            if not contexts:
                print("     Context: no match in the extracted expected-page snapshot")
        hits = matching_pages(pages, spans, case.get("section_path_contains"))
        print("Pages containing span(s):")
        for page, matched_spans in hits.values():
            print(f"  - {page.url} — {page.title} [{'; '.join(matched_spans)}]")
        if not hits:
            print("  (none)")
        print("Other pages containing span(s):")
        others = [
            page
            for page in hits.values()
            if normalized_url(page[0].url) != normalized_url(case.get("expected_url"))
        ]
        for page, matched_spans in others:
            print(f"  - {page.url} — {page.title} [{'; '.join(matched_spans)}]")
        if not others:
            print("  (none)")
    else:
        if case.get("partial_evidence_span"):
            print(f"Partial evidence span: {case['partial_evidence_span']}")
            for context in display_context(
                expected_page.markdown if expected_page else "",
                case["partial_evidence_span"],
            ):
                print(f"  Context: {context}")
        print("Check-pattern results across snapshots (at most two per pattern, eight total):")
        results = run_check_patterns(case, pages)
        display_check_pattern_results(results)
        if not results:
            print("  (no matches)")
        print("Unanswerable-case evidence:")
        for item in case.get("unanswerable_snippets", []):
            print(f"  - {item.get('url', '(unknown URL)')}")
            print(f"    Terms: {', '.join(item.get('matched_terms', [])) or '(none)'}")
            print(f"    Context: {item.get('snippet', '')}")
    if expected_page is None:
        print(f"Snapshot: missing ({case.get('snapshot_path') or 'no path'})")
    else:
        print(f"Snapshot: {expected_page.snapshot_path}")
    print("[v]erified / [x] set expected page / [e]dit span / [u]pdate acceptable URLs / [t]ype change / [d]elete / [s]kip")


def update_acceptable_urls(case: dict[str, Any], pages: list[Snapshot]) -> None:
    spans = spans_from_case(case)
    hits = list(matching_pages(pages, spans, case.get("section_path_contains")).values())
    if not hits:
        raise ValueError("No pages contain any answer span.")
    print("Choose acceptable page numbers (comma-separated):")
    for index, (page, matched_spans) in enumerate(hits, 1):
        print(f"  {index}. {page.url} — {page.title} [{'; '.join(matched_spans)}]")
    selected_text = input("> ").strip()
    if not selected_text:
        raise ValueError("At least one acceptable URL must be selected.")
    try:
        selected = sorted({int(item.strip()) for item in selected_text.split(",")})
    except ValueError as error:
        raise ValueError("Enter comma-separated page numbers.") from error
    if any(number < 1 or number > len(hits) for number in selected):
        raise ValueError("One or more selected page numbers are out of range.")
    case["acceptable_urls"] = [
        {
            "url": hits[number - 1][0].url,
            "title": hits[number - 1][0].title,
            "matched_spans": hits[number - 1][1],
            "status": "verified",
        }
        for number in selected
    ]
    case["acceptable_urls_status"] = "verified"


def save_cursor(state_path: Path, case_id: str | None) -> None:
    state_path.write_text(json.dumps({"next_id": case_id}), encoding="utf-8")


def load_cursor(state_path: Path) -> str | None:
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))
        return value.get("next_id")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def filter_cases(
    cases: list[dict[str, Any]],
    types: list[str] | None = None,
    groups: list[str] | None = None,
    ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    return [
        case
        for case in cases
        if (not types or case.get("type") in types)
        and (not groups or case.get("site_group") in groups)
        and (not ids or case.get("id") in ids)
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--type", dest="types", action="append", choices=sorted(VALID_TYPES))
    parser.add_argument("--group", dest="groups", action="append", help="Filter by exact site_group value.")
    parser.add_argument("--id", dest="ids", action="append", help="Filter by case id; repeatable.")
    args = parser.parse_args()
    draft_path = args.draft.resolve()
    state_path = draft_path.parent / f".{draft_path.name}.state.json"
    all_cases = load_cases(draft_path)
    cases = filter_cases(all_cases, args.types, args.groups, args.ids)
    if not cases:
        print("No cases match these filters.")
        return 0
    pages = load_snapshots()

    cursor_id = load_cursor(state_path)
    start = next((i for i, case in enumerate(cases) if case.get("id") == cursor_id), 0)
    index = start
    visited: set[str] = set()
    current_id: str | None = None
    try:
        while len(visited) < len(cases):
            index %= len(cases)
            case = cases[index]
            case_id = case.get("id")
            if case.get("status") == "verified":
                visited.add(case_id)
                index += 1
                continue
            if case_id in visited:
                break
            current_id = case_id
            visited.add(case_id)
            display_case(case, pages)
            choice = input("> ").strip().lower()

            next_index = (index + 1) % len(cases)
            if choice == "v":
                if case.get("type") == "answerable":
                    expected_page = next(
                        (
                            page
                            for page in pages
                            if normalized_url(page.snapshot_path) == normalized_url(case.get("snapshot_path"))
                            or normalized_url(page.url) == normalized_url(case.get("expected_url"))
                        ),
                        None,
                    )
                    try:
                        if expected_page is None:
                            raise ValueError("Expected-page snapshot is missing.")
                        validate_answer_spans(
                            expected_page.markdown,
                            spans_from_case(case),
                            case.get("section_path_contains"),
                        )
                    except ValueError as error:
                        print(f"Cannot verify: {error}")
                        visited.discard(case_id)
                        continue
                    recompute_span_page_data(case, pages)
                    if (
                        case.get("pages_with_any_span_count", 0) > 1
                        and case.get("acceptable_urls_status") != "verified"
                    ):
                        print("Choose acceptable URLs with [u] before verifying this multi-page span.")
                        visited.discard(case_id)
                        continue
                case["status"] = "verified"
                write_cases(draft_path, all_cases)
            elif choice == "x":
                try:
                    choose_expected_page(case, pages)
                except ValueError as error:
                    print(f"Expected page was not changed: {error}")
                    visited.discard(case_id)
                    continue
                recompute_span_page_data(case, pages)
                write_cases(draft_path, all_cases)
            elif choice == "e":
                if case.get("expected_page_selection_required"):
                    print("Set the expected page with [x] before editing a span for this answerable case.")
                    visited.discard(case_id)
                    continue
                spans = spans_from_case(case)
                if len(spans) > 1:
                    print("Edit which span?")
                    for number, span in enumerate(spans, 1):
                        print(f"  {number}. {span}")
                    try:
                        span_index = int(input("> ").strip()) - 1
                    except ValueError:
                        print("Enter a span number.")
                        visited.discard(case_id)
                        continue
                else:
                    span_index = 0
                new_span = input("New verbatim answer span: ").strip()
                try:
                    expected_page = next(
                        (
                            page
                            for page in pages
                            if normalized_url(page.snapshot_path) == normalized_url(case.get("snapshot_path"))
                            or normalized_url(page.url) == normalized_url(case.get("expected_url"))
                        ),
                        None,
                    )
                    if expected_page is None:
                        raise ValueError("Expected-page snapshot is missing.")
                    apply_span_edit(case, span_index, new_span, expected_page.markdown, pages)
                except ValueError as error:
                    print(f"Span was not changed: {error}")
                    visited.discard(case_id)
                    continue
                write_cases(draft_path, all_cases)
            elif choice == "u":
                try:
                    update_acceptable_urls(case, pages)
                except ValueError as error:
                    print(f"Acceptable URLs were not changed: {error}")
                    visited.discard(case_id)
                    continue
                write_cases(draft_path, all_cases)
            elif choice == "t":
                new_type = input(f"New type ({', '.join(sorted(VALID_TYPES))}): ").strip()
                if new_type not in VALID_TYPES:
                    print("Invalid type; case was not changed.")
                    visited.discard(case_id)
                    continue
                was_answerable = case.get("answerable", False)
                case["type"] = case["proposed_type"] = new_type
                case["answerable"] = new_type == "answerable"
                if new_type == "answerable" and not was_answerable:
                    case["expected_page_selection_required"] = True
                elif new_type != "answerable":
                    case.pop("expected_page_selection_required", None)
                case["status"] = "TODO: verify"
                write_cases(draft_path, all_cases)
            elif choice == "d":
                all_cases.remove(case)
                cases.remove(case)
                write_cases(draft_path, all_cases)
                if not cases:
                    print("No cases remain.")
                    return 0
                next_index = index % len(cases)
            elif choice != "s":
                print("Choose v, x, e, u, t, d, or s.")
                visited.discard(case_id)
                continue

            next_case_id = cases[next_index].get("id") if cases else None
            save_cursor(state_path, next_case_id)
            current_id = next_case_id
            index = next_index
    except (EOFError, KeyboardInterrupt):
        save_cursor(state_path, current_id)
        print("\nVerification paused; resume state saved.")
        return 0

    remaining = [case for case in cases if case.get("status") != "verified"]
    if remaining:
        save_cursor(state_path, current_id)
        print("Verification paused; your progress and next case are saved.")
    else:
        save_cursor(state_path, None)
        print("All filtered cases are marked verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
