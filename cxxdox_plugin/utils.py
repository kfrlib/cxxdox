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


def wrap_name(name: str) -> str:
    if not name.startswith('::'):
        name = '::' + name
    if not name.endswith('::'):
        name += '::'
    return name


def share_prefix(first: str, second: str) -> bool:
    return first.startswith(second) or second.startswith(first)


def strip_params(full_name: str) -> str:
    if full_name.endswith(')::'):
        return re.sub(r'\(.*\)::$', '::', full_name)
    if full_name.endswith(')'):
        return re.sub(r'\(.*\)$', '', full_name)
    return full_name


def strip_tparams(full_name: str) -> str:
    if full_name.endswith('>::'):
        return re.sub(r'\<.*\>::$', '::', full_name)
    if full_name.endswith('>'):
        return re.sub(r'\<.*\>$', '', full_name)
    return full_name


def strip_scope(full_name: str) -> str:
    """Remove the scope prefix outside function and template arguments."""
    paren_depth = 0
    template_depth = 0
    last_scope = -1
    index = 0

    while index < len(full_name):
        character = full_name[index]
        if character == '(':
            paren_depth += 1
        elif character == ')' and paren_depth:
            paren_depth -= 1
        elif character == '<':
            template_depth += 1
        elif character == '>' and template_depth:
            template_depth -= 1
        elif (
            character == ':'
            and index + 1 < len(full_name)
            and full_name[index + 1] == ':'
            and not paren_depth
            and not template_depth
        ):
            last_scope = index
            index += 1
        index += 1

    return full_name[last_scope + 2:] if last_scope >= 0 else full_name


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
