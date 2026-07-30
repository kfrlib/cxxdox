import re
from xml.etree import ElementTree
from markdown import Extension, Markdown
from markdown.blockprocessors import BlockProcessor
from markdown.inlinepatterns import InlineProcessor
from markdown.util import AtomicString
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import fromstring
from mkdocs.structure.pages import Page
from typing import Callable
from cxxdox_plugin.doxygen import doxygen_to_html
from .highlight import cxx_tokens_to_html
from .logs import log
from .parser import Index, SymbolType
from .utils import atomicize_subtree, strip_default_namespace
from .identifiers import parse_cpp_identifier
import os
from pathlib import Path

from collections.abc import MutableSequence


class CxxSnippetProcessor(BlockProcessor):  # --8<-- "cxx:library.hpp"
    regex = re.compile(r"^-+8<-+ +\"cxx:(?P<filename>.+?)\" *$", flags=re.MULTILINE)
    def __init__(
        self,
        md: Markdown,
        index: Index,
        link_resolver: Callable[[str],str]
    ) -> None:
        super().__init__(parser=md.parser)
        self.md = md
        self.index = index
        self.link_resolver = link_resolver
        
    def test(self, parent: Element, block: str) -> bool:
        return bool(self.regex.search(block))
    
    def run(self, parent: Element, blocks: MutableSequence[str]) -> None:
        block = blocks.pop(0)
        match = self.regex.search(block)
        if match:
            if match.start() > 0:
                self.parser.parseBlocks(parent, [block[: match.start()]])
            block = block[match.end():]
            
            block, the_rest = self.detab(block)

            filename = match["filename"]

            if the_rest:
                # This block contained unindented line(s) after the first indented
                # line. Insert these lines as the first block of the master blocks
                # list for future processing.
                blocks.insert(0, the_rest)

def dummy_span(classes: str, text: str) -> Element:
    span = Element('span', {'class': classes})
    span.text = AtomicString(text)
    return span

class SymbolLinkProcessor(InlineProcessor):
    def __init__(
        self,
        index: Index,
        pattern: str,
        md: Markdown | None,
        link_resolver: Callable[[str],str],
        default_namespace: str = '',
    ) -> None:
        self.index = index
        self.link_resolver = link_resolver
        self.default_namespace = default_namespace
        super().__init__(pattern, md)

    @staticmethod
    def make_link(index: Index, link_resolver: Callable[[str],str], sym_id: str, flags: list[str], default_namespace: str = '') -> Element:
        emit_brief = 'brief' in flags
        emit_type = 'type' in flags
        emit_file = 'file' in flags
        nosig = 'nosig' in flags
        noscope = 'noscope' in flags
        wide = 'wide' in flags
        if not index.has_symbol(sym_id):
            log.error(f"Symbol ID not found in make_link: {sym_id}")
            return dummy_span('cxx-missing-symbol', '[unknown symbol]')
        sym = index[sym_id]
        full_name = sym.get('full_name', '')
        if full_name == '':
            log.warning(f"Symbol with empty full_name: {sym_id}")
        scope, name, tparams, params = parse_cpp_identifier(
            full_name if sym.get('type') == SymbolType.MACRO.value else strip_default_namespace(full_name, default_namespace)
        )
        if nosig:
            tparams = params = ''
        if noscope:
            scope = ''
        link = sym.get('permalink', None)
        link = link_resolver(link) if link is not None else None
        root_classes = ['cxx-symbol-link']
        if wide:
            root_classes.append('cxx-symbol-wide')
        root_el = Element('span', {'class': ' '.join(root_classes)})
        if emit_type:
            type_wrapper = Element('span', {'class': 'cxx-type'})
            type_code = Element('code')
            type_code.set('class', 'cxx-label-' + sym.get('type', 'unknown'))
            type_code.text = AtomicString(sym.get('type', '').replace('-', ' '))
            type_wrapper.append(type_code)
            type_wrapper.tail = AtomicString(' ')
            root_el.append(type_wrapper)
        link_el = Element('a', {'class': 'cxx-symbol-href'})
        link_el.set('href', (link or ''))
        root_el.append(link_el)
        if scope:
            scope_span = Element('span', {'class': 'cxx-symbol-scope'})
            scope_span.text = AtomicString(scope)
            link_el.append(scope_span)
        text_span = Element('span', {'class': 'cxx-symbol-name'})
        text_span.text = AtomicString(name + tparams + params)
        link_el.append(text_span)
        if emit_file and 'file' in sym:
            file_span = Element('span', {'class': 'cxx-symbol-file'})
            file_span.text = AtomicString(f' ({sym.get("file", "")}:{sym.get("line", "")})')
            root_el.append(file_span)
        
        brief_html = doxygen_to_html(sym.get('brief', ''), index, full_name or '', link_resolver, symbol_id=sym_id)
        brief_text = re.sub(r'<[^>]*>', '', brief_html)
        if emit_brief and 'brief' in sym:
            brief_el = atomicize_subtree(fromstring(f'<span class="cxx-inline-brief"> {brief_html}</span>'))
            root_el.append(brief_el)
        link_el.set('title', brief_text)
        return root_el

    @staticmethod
    def _is_wrapped_in_code_span(data: str, start: int, end: int) -> bool:
        # Detect `[[...]]` wrapped in a backtick code span, e.g. `[[...]]` or
        # `` [[...]] ``, allowing any number of backticks and surrounding spaces.
        # Look backwards from the match for the opening fence.
        i = start - 1
        while i >= 0 and data[i] in ' \t':
            i -= 1
        open_len = 0
        while i >= 0 and data[i] == '`':
            open_len += 1
            i -= 1
        if open_len == 0:
            return False
        # Look forwards from the match for the closing fence.
        j = end
        while j < len(data) and data[j] in ' \t':
            j += 1
        close_len = 0
        while j < len(data) and data[j] == '`':
            close_len += 1
            j += 1
        return close_len == open_len

    def handleMatch(self, m, data):
        # Skip `[[...]]` that is wrapped in backticks (inline code), e.g.
        # `[[...]]` or `` [[...]] ``. Let the lower-priority backtick processor
        # render it as code instead.
        start, end = m.start(0), m.end(0)
        if self._is_wrapped_in_code_span(data, start, end):
            return None, None, None
        sym_name: str = m.group('name') or ''
        if sym_name.startswith('`') and sym_name.endswith('`'):
            sym_name = sym_name[1:-1]
        flags = m.group('flags') or ''
        flags = flags.split(':')
        sym_id = ''
        if self.index.has_symbol(sym_name):
            sym_id = sym_name
        else:
            sym_id = self.index.simple_lookup_any(sym_name, self.default_namespace)
            if not sym_id:
                return dummy_span('cxx-missing-symbol', '[unknown symbol]'), m.start(0), m.end(0)
        return self.make_link(self.index, self.link_resolver, sym_id, flags, self.default_namespace), m.start(0), m.end(0)


class CxxDoxProcessor(BlockProcessor):
    regex = re.compile(r"^(?P<heading>#{1,6} *)::: ?(?P<name>.+?) *$", flags=re.MULTILINE)

    def __init__(
        self,
        md: Markdown,
        index: Index,
        link_resolver: Callable[[str],str],
        git_browse_link: Callable[[dict], str | None],
    ) -> None:
        super().__init__(parser=md.parser)
        self.md = md
        self.index = index
        self.link_resolver = link_resolver
        self.git_browse_link = git_browse_link
        
    def test(self, parent: Element, block: str) -> bool:
        return bool(self.regex.search(block))

    def _symbol_doc(self, parent: Element, sym_id: str, heading_level: int, parent_group: str = '') -> None:
            
        sym: dict = self.index[sym_id]
        full_name = sym.get('full_name', '')

        context = full_name or ''

        has_source = 'source' in sym and sym['source']
        children = self.index.lookup_children(sym_id)

        link = self.index.symbol_permalink(sym_id)
        hash = ''
        if link is not None and '#' in link:
            hash = link.split('#')[-1]

        h_el = Element(f'h{max(heading_level,1)}', {'id': hash})
        h_code_el = Element('code', {'class': 'cxx-label-' + sym.get('type', 'unknown')})
        h_code_el.text = AtomicString(sym.get('type', '').replace('-', ' '))
        h_el.append(h_code_el)
        h_code_el.tail = AtomicString(' ' + sym.get('name', '') + ' ')

        group = sym.get('group', '')
        if group != '' and group != parent_group:
            group_a_el = Element('a', {'class': 'cxx-group', 'data-search-exclude': 'true'})
            group_a_el.text = AtomicString(group)
            group_a_el.set('href', self.link_resolver(f'*{group}/index.md'))
            group_a_el.set('title', f'Group: {group}')
            h_el.append(group_a_el)

        parent.append(h_el)

        if has_source:
            div_highlight = Element('div', {'class': 'highlight'})
            pre_el = Element('pre')
            src = sym.get('source', '')
            html_source = cxx_tokens_to_html(src, self.index, {sym_id}, self.link_resolver)
            code_el = atomicize_subtree(fromstring(f'<code>{html_source}</code>'))
            pre_el.append(Element('b', {'class': 'LAUyl5Cz5B'}))
            pre_el.append(code_el)
            div_highlight.append(pre_el)
            parent.append(div_highlight)

        contents_el = Element('div', {'class': 'cxx-contents'})
        brief_html = '<p>' + doxygen_to_html(sym.get('brief', ''), self.index, context, self.link_resolver, symbol_id=sym_id) + '</p>'
        contents_el.append(atomicize_subtree(fromstring(brief_html)))
        if 'details' in sym and sym['details']:
            details_html = '<p>' + doxygen_to_html(sym.get('details', ''), self.index, context, self.link_resolver, symbol_id=sym_id) + '</p>'
            contents_el.append(atomicize_subtree(fromstring(details_html)))

        parent.append(contents_el)
        
        if len(children) > 0:            
            children_el = Element('div', {'class': 'cxx-children'})
            contents_el.append(children_el)
            for child_id in children:
                self._symbol_doc(children_el, child_id, min(heading_level + 1, 6), group)

        full_name = sym.get('full_name', '')
        full_name_el = Element('div', {'class': 'cxx-full-name'})
        full_name_p_el = Element('p')
        full_name_el.append(full_name_p_el)
        full_name_p_el.text = AtomicString(f'Fully qualified name: ')
        full_name_code_el = Element('code')
        full_name_code_el.text = AtomicString(full_name)
        full_name_p_el.append(full_name_code_el)
        contents_el.append(full_name_el)

        file = sym.get("file","")
        if file != '':
            location_el = Element('div', {'class': 'cxx-location'})
            location_p_el = Element('p')
            location_el.append(location_p_el)            
            line = sym.get('line', '')
            source_url = self.git_browse_link(sym)
            location_p_el.text = AtomicString('Declared at ')
            if source_url is not None:
                source_link_el = Element('a', {
                    'href': source_url,
                    'target': '_blank',
                    'rel': 'noopener noreferrer',
                })
                source_link_el.text = AtomicString(f'{file}:{line}')
                location_p_el.append(source_link_el)
            else:
                location_p_el.text = AtomicString(f'Declared at {file}:{line}')
            contents_el.append(location_el)

    def run(self, parent: Element, blocks: MutableSequence[str]) -> None:
        block = blocks.pop(0)
        match = self.regex.search(block)

        if match:
            if match.start() > 0:
                self.parser.parseBlocks(parent, [block[: match.start()]])
            block = block[match.end():]
            
        block, the_rest = self.detab(block)

        if match:
            identifier = match["name"]
            heading_level = match["heading"].count("#")

            if self.index.has_symbol(identifier):
                sym_id = identifier
            else:
                sym_id = self.index.scoped_lookup('', identifier)

            if sym_id is None:
                log.warning(f"CxxDox symbol not found: {identifier}")
                return
            
            self._symbol_doc(parent, sym_id, heading_level)
        
        if the_rest:
            # This block contained unindented line(s) after the first indented
            # line. Insert these lines as the first block of the master blocks
            # list for future processing.
            blocks.insert(0, the_rest)


class CxxDoxExtension(Extension):
    current_page: Page|None

    def __init__(
            self,
            index: Index,
            link_resolver: Callable[[str],str],
            git_browse_link: Callable[[dict], str | None],
            default_namespace: str = '',
            **kwargs: Any,
        ) -> None:
        self.index = index
        self.link_resolver = link_resolver
        self.git_browse_link = git_browse_link
        self.default_namespace = default_namespace
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown) -> None:
        md.parser.blockprocessors.register(
            CxxDoxProcessor(md, self.index, self.link_resolver, self.git_browse_link),
            "cxxdox_block_processor",
            priority=75,
        )
        md.parser.blockprocessors.register(
            CxxDoxProcessor(md, self.index, self.link_resolver, self.git_browse_link),
            "cxxdox_brief_processor",
            priority=75,
        )
        md.parser.blockprocessors.register(
            CxxSnippetProcessor(md, self.index, self.link_resolver),
            "cxxsnippet_processor",
            priority=80,
        )
        pattern   = r'\[\[(?P<name>`[^`]*`|(?:[^:\]\s`]+(?:::[^:\]\s`]+)*))(?::(?P<flags>(?:\w+(?::\w+)*)))?\]\]'
        md.inlinePatterns.register(
            SymbolLinkProcessor(self.index, pattern, md, self.link_resolver, self.default_namespace), 'cxx-symbol-link', 19000
        )
