#!/usr/bin/env python
"""Search extracted Markdown from every frozen snapshot."""

from __future__ import annotations

import argparse
import re
import sys

from snapshot_utils import Snapshot, fold_accents_with_offsets, load_snapshots


REGEX_SYNTAX = frozenset(".^$*+?{}[]\\|()")


def fold_regex_literals(regex: str) -> str:
    folded = []
    index = 0
    while index < len(regex):
        character = regex[index]
        if character == "\\" and index + 1 < len(regex):
            folded.append(regex[index:index + 2])
            index += 2
        elif character in REGEX_SYNTAX:
            folded.append(character)
            index += 1
        else:
            folded.append(fold_accents_with_offsets(character)[0])
            index += 1
    return "".join(folded)


def search_snapshots(
    pages: list[Snapshot],
    regex: str,
    url_contains: str | None = None,
    fold: bool = False,
) -> list[tuple[Snapshot, str]]:
    try:
        searchable_regex = fold_regex_literals(regex) if fold else regex
        pattern = re.compile(searchable_regex, re.IGNORECASE)
    except re.error as error:
        raise ValueError(f"Invalid regular expression {regex!r}: {error}") from error

    results = []
    for page in pages:
        if url_contains and url_contains.casefold() not in page.url.casefold():
            continue
        if fold:
            searchable, offsets = fold_accents_with_offsets(page.markdown)
            matches = []
            for match in pattern.finditer(searchable):
                if match.start() == match.end():
                    continue
                start = offsets[match.start()]
                end = offsets[match.end() - 1] + 1
                matches.append((start, end))
        else:
            matches = [
                (match.start(), match.end())
                for match in pattern.finditer(page.markdown)
                if match.start() != match.end()
            ]

        for start, end in matches:
            left = max(0, start - 75)
            right = min(len(page.markdown), end + 75)
            context = " ".join(page.markdown[left:right].split())
            results.append((page, context))
    return results


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("regex", help="Regular expression to search in extracted Markdown.")
    parser.add_argument("--url-contains", help="Only search snapshot URLs containing this text.")
    parser.add_argument("--fold", action="store_true", help="Ignore accents while matching.")
    args = parser.parse_args()

    try:
        results = search_snapshots(load_snapshots(), args.regex, args.url_contains, args.fold)
    except ValueError as error:
        parser.error(str(error))
    if not results:
        print("No matches.")
        return 0
    for page, context in results:
        print(f"{page.url}\t{page.title}\t{context}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
