"""ElementTree helpers shared by the Markdown extensions."""

import xml.etree.ElementTree as etree

from markdown.util import AtomicString


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