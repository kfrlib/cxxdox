#!/usr/bin/env python3
"""Search out.json for symbols by spelling or full name.

The JSON file is loaded into an :class:`Index` and lookups are performed
through :meth:`Index._simple_lookup`, so the same resolution rules used
when generating documentation apply here (default namespace qualification,
template/parameter matching, macro handling, ...). All matches are
returned; ambiguous lookups are flagged with a remark.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from cxxdox_plugin.doxygen import doxygen_to_html
from cxxdox_plugin.identifiers import parse_cpp_identifier
from cxxdox_plugin.index import Index, SymbolType
from cxxdox_plugin.utils import strip_default_namespace


def load_index(path: Path) -> Index:
    """Build an :class:`Index` from a dumped ``out.json`` file."""
    with path.open(encoding="utf-8") as stream:
        import json
        data = json.load(stream)

    if not isinstance(data, dict):
        raise ValueError(f"Expected the top-level JSON value to be an object: {path}")

    index = Index()
    for sym_id, sym in data.items():
        if isinstance(sym, dict):
            index.symbols[sym_id] = sym

    return index


def _strip_tags(html_str: str) -> str:
    """Strip HTML tags, unescape entities, and collapse whitespace."""
    text = re.sub(r'<[^>]*>', ' ', html_str)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def _identity_link(permalink: str) -> str:
    return permalink


def _render_doc(block, index: Index, context: str) -> str:
    """Render a brief/details block to plain text via doxygen_to_html."""
    if not block:
        return ''
    html = doxygen_to_html(block, index, context, _identity_link)
    return _strip_tags(html)

def _display_name(sym: dict, default_namespace: str) -> str:
    """full_name with the default namespace stripped (the lookup name)."""
    full_name = sym.get('full_name', '')
    if sym.get('type') == SymbolType.MACRO.value:
        return full_name
    return strip_default_namespace(full_name, default_namespace)


def _name_without_params(display_name: str) -> str:
    scope, name, tparams, _ = parse_cpp_identifier(display_name)
    return scope + name + tparams


def _name_without_tparams(display_name: str) -> str:
    scope, name, _, _ = parse_cpp_identifier(display_name)
    return scope + name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search out.json by spelling or full_name via Index._simple_lookup."
    )
    parser.add_argument(
        "symbols",
        nargs="+",
        help="One or more symbol names to look up (e.g. 'global_function' or 'ns::fn')",
    )
    parser.add_argument(
        "--index",
        type=Path,
        required=True,
        help="Path to the JSON index file to search",
    )
    parser.add_argument(
        "--default-namespace",
        default="",
        help="Default namespace used to qualify unqualified lookups (default: none)",
    )
    args = parser.parse_args()

    index = load_index(args.index)

    for symbol in args.symbols:
        matches = index._simple_lookup(symbol, args.default_namespace)

        # A clearly delimited, machine-readable block per pattern so an LLM
        # consuming the output can split results unambiguously.
        print(f"=== PATTERN: {symbol} ===")
        if not matches:
            print("RESULT: null")
            print("=== END ===")
            continue

        print("RESULT:")
        for i, sym_id in enumerate(matches):
            if i > 0:
                print("  ---")
            sym = index[sym_id]
            display_name = _display_name(sym, args.default_namespace)
            context = sym.get('full_name', '') or display_name
            location = f"{sym.get('file', '')}:{sym.get('line', '')}" if sym.get('file') else ''

            print(f"  lookup_name: {display_name}")
            print(f"  name_no_params: {_name_without_params(display_name)}")
            print(f"  name_no_tparams: {_name_without_tparams(display_name)}")
            print(f"  brief: {_render_doc(sym.get('brief', ''), index, context)}")
            print(f"  details: {_render_doc(sym.get('details', []), index, context)}")
            print(f"  location: {location}")

        if len(matches) > 1:
            print("REMARK: Ambiguous lookup "
                  f"({len(matches)} matches for '{symbol}' "
                  f"in namespace '{args.default_namespace}')")
        print("=== END ===")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
