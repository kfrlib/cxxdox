from enum import Enum
from dataclasses import dataclass
from typing import Callable, Iterator

from cxxdox_plugin.index import Index, CxxToken, CxxTokenType
from .libclang21.cindex import TokenKind, Token, CursorKind, SourceRange, Cursor, TranslationUnit, SourceLocation, AccessSpecifier, Config as ClangConfig
from cxxdox_plugin.doxygen import escape

def cursor_to_symbol_id(cursor: Cursor) -> str|None:
    if cursor is None or cursor.is_null():
        return None
    if cursor.kind.is_declaration() or cursor.kind.is_reference():
        symbol_id = cursor.get_usr()
        if symbol_id:
            return symbol_id
        def_cursor = cursor.get_definition()
        if def_cursor is not None and def_cursor != cursor:
            return cursor_to_symbol_id(def_cursor)
    return None

def to_cxx_tokens(tokens: Iterator[Token], source: bytes, indent: int = 0) -> list[CxxToken]:
    result: list[CxxToken] = []

    last_pos = None
    for t in tokens:
        if last_pos is not None:
            if t.extent.start.offset > last_pos:
                gap = source[last_pos : t.extent.start.offset]
                gap = gap.replace(b'\r\n', b'\n')
                gap = gap.replace(b'\n' + indent * b' ', b'\n')
                result.append(CxxToken(type=CxxTokenType.WHITESPACE, spelling=gap.decode('utf-8')))

        ref: str|None = None
        if t.kind == TokenKind.IDENTIFIER:
            token_type = CxxTokenType.IDENTIFIER
            ref = cursor_to_symbol_id(t.cursor)
        elif t.kind == TokenKind.KEYWORD:
            token_type = CxxTokenType.KEYWORD
        elif t.kind == TokenKind.LITERAL:
            token_type = CxxTokenType.LITERAL
        elif t.kind == TokenKind.COMMENT:
            token_type = CxxTokenType.COMMENT
        elif t.kind == TokenKind.PUNCTUATION:
            token_type = CxxTokenType.PUNCTUATION
        else:
            token_type = CxxTokenType.UNKNOWN

        result.append(CxxToken(type=token_type, spelling=t.spelling, ref=ref))

        last_pos = t.extent.end.offset
    return result

def cxx_tokens_to_html(tokens: list[CxxToken], index: Index, ignore: set[str], link_resolver: Callable[[str],str]) -> str:
    html_parts: list[str] = []
    for token in tokens:
        if token.ref is not None and token.ref not in ignore and index.has_symbol(token.ref):
            link = link_resolver(index.symbol_permalink(token.ref) or "")
            html_parts.append(f'<a href="{link}"><span class="{token.type}">{escape(token.spelling)}</span></a>')
        else:
            html_parts.append(f'<span class="{token.type}">{escape(token.spelling)}</span>')
    return ''.join(html_parts)
