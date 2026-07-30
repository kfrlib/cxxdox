"""ElementTree helpers shared by the Markdown extensions."""

import xml.etree.ElementTree as etree
import re

from markdown.util import AtomicString

def normalize_symbol_name(name: str) -> str:
    """Remove redundant whitespace from a symbol's signature."""
    def is_identifier_character(character: str) -> bool:
        return character == '_' or character == '$' or character.isalnum()

    def replace_space(match: re.Match) -> str:
        left = name[match.start() - 1] if match.start() else ''
        right = name[match.end()] if match.end() < len(name) else ''
        # Keep the separator between two identifier characters, as in
        # ``const T``; whitespace next to punctuation is redundant.
        return ' ' if is_identifier_character(left) and is_identifier_character(right) else ''

    return re.sub(r'\s+', replace_space, name).strip()


def strip_default_namespace(full_name: str, default_namespace: str) -> str:
        """Rewrite a fully-qualified symbol name for display, given a default namespace.

        Rules (lookup is *not* affected -- this only changes what is rendered):
        - empty / unset ``default_namespace`` -> returned unchanged.
        - ``full_name`` equal to ``default_namespace`` -> returned unchanged
            (the namespace itself stays as-is, e.g. ``ns``).
        - ``full_name`` starts with ``default_namespace + "::"`` -> that prefix
            is stripped (e.g. ``ns::func`` -> ``func``).
        - otherwise -> the name is qualified with a leading ``::`` so it reads
            as a fully-qualified C++ reference (e.g. ``other::func`` -> ``::other::func``).
        """
        if not default_namespace or not full_name:
                return full_name
        if full_name == default_namespace:
                return full_name
        prefix = default_namespace + "::"
        if full_name.startswith(prefix):
                return full_name[len(prefix):]
        if not full_name.startswith("("):
            return "::" + full_name
        return full_name

def add_default_namespace(name: str, default_namespace: str) -> str:
    """Qualify a symbol name using the default namespace.

    Names beginning with ``::`` are treated as fully-qualified and have the
    leading scope operator removed. Other names are prefixed with the default
    namespace and ``::``. Empty names or namespaces are returned unchanged.
    """
    if not name or not default_namespace:
        return name
    if name.startswith("::"):
        return name[2:]
    if not name[0].isalpha():
        return name
    return default_namespace + "::" + name


def atomicize_subtree(el: etree.Element) -> etree.Element:
    """Mark literal text in an ElementTree fragment as opaque to Markdown.

    Use this after parsing a structural HTML fragment whose text nodes are
    literal, rather than Markdown that should receive another inline pass.
    """
    if el.text:
        el.text = AtomicString(el.text)
    if el.tail:
        el.tail = AtomicString(el.tail)
    for child in el:
        atomicize_subtree(child)
    return el
