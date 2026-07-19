#!/usr/bin/env python3
"""Search out.json for symbols by spelling or full name."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def find_matches(
    data: dict[str, Any], query: str, field: str
) -> list[dict[str, Any]]:
    """Return objects whose *field* contains *query*."""
    matches: list[dict[str, Any]] = []
    for obj in data.values():
        if not isinstance(obj, dict):
            continue

        if query in str(obj.get(field, "")):
            match = dict(obj)
            match.pop("source", None)
            matches.append(match)
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search out.json by spelling or full_name."
    )
    parser.add_argument("substring", help="Substring to search for")
    parser.add_argument(
        "--index",
        type=Path,
        required=True,
        help="Path to the JSON index file to search",
    )
    args = parser.parse_args()

    with args.index.open(encoding="utf-8") as stream:
        data = json.load(stream)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected the top-level JSON value to be an object: {args.index}"
        )

    matches = find_matches(data, args.substring, "spelling")
    if not matches:
        matches = find_matches(data, args.substring, "full_name")

    for match in matches:
        print(json.dumps(match, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
