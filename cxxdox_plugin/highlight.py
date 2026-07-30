from enum import Enum
from dataclasses import dataclass
import re
from typing import Callable, Iterator

from cxxdox_plugin.index import Index, CxxToken, CxxTokenType
from .libclang21.cindex import TokenKind, Token, CursorKind, SourceRange, Cursor, TranslationUnit, SourceLocation, AccessSpecifier, Config as ClangConfig
from cxxdox_plugin.doxygen import escape

# C++23 type-specifier keywords.  Qualifiers such as const and volatile remain
# ordinary keywords; nullptr_t is a library type, not a keyword.
_TYPE_KEYWORDS = frozenset({
    'void', 'bool', 'char', 'char8_t', 'char16_t', 'char32_t', 'wchar_t',
    'signed', 'unsigned', 'short', 'int', 'long', 'float', 'double',
    'auto',
})

_STRING_OR_CHAR_LITERAL = re.compile(r'(?:u8|u|U|L)?(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', re.DOTALL)
_NUMBER_LITERAL = re.compile(
    r'(?:0[xX][0-9a-fA-F]+|0[bB][01]+|0[0-7]*|[0-9]+(?:\.[0-9]*)?|\.[0-9]+)'
    r'(?:[eEpP][+-]?[0-9]+)?[uUlLfFzZ]*'
)

_NAMESPACE_KINDS = frozenset({
    CursorKind.NAMESPACE, CursorKind.NAMESPACE_ALIAS,
    CursorKind.NAMESPACE_REF,
})
_FUNCTION_KINDS = frozenset({
    CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR,
    CursorKind.DESTRUCTOR, CursorKind.CONVERSION_FUNCTION,
    CursorKind.FUNCTION_TEMPLATE, CursorKind.OVERLOADED_DECL_REF,
})
_TYPE_KINDS = frozenset({
    CursorKind.STRUCT_DECL, CursorKind.UNION_DECL, CursorKind.CLASS_DECL,
    CursorKind.ENUM_DECL, CursorKind.TYPEDEF_DECL, CursorKind.CLASS_TEMPLATE,
    CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
    CursorKind.TYPE_ALIAS_DECL, CursorKind.TEMPLATE_TYPE_PARAMETER,
    CursorKind.TYPE_REF, CursorKind.TEMPLATE_REF, CursorKind.CXX_BASE_SPECIFIER,
})
_PREPROCESSOR_KINDS = frozenset({
    CursorKind.PREPROCESSING_DIRECTIVE, CursorKind.INCLUSION_DIRECTIVE,
})
_MACRO_KINDS = frozenset({
    CursorKind.MACRO_DEFINITION, CursorKind.MACRO_INSTANTIATION,
})

def identifier_token_type(cursor: Cursor) -> CxxTokenType:
    if cursor is not None and not cursor.is_null():
        kind = cursor.kind
        if kind in _NAMESPACE_KINDS:
            return CxxTokenType.IDENTIFIER_NAMESPACE
        if kind in _FUNCTION_KINDS:
            return CxxTokenType.IDENTIFIER_FUNCTION
        if kind in _TYPE_KINDS:
            return CxxTokenType.IDENTIFIER_CLASS
    return CxxTokenType.IDENTIFIER_VAR

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
        cursor = t.cursor
        if cursor is not None and not cursor.is_null() and cursor.kind in _PREPROCESSOR_KINDS:
            token_type = CxxTokenType.COMMENT_PREPROC
        elif cursor is not None and not cursor.is_null() and cursor.kind in _MACRO_KINDS:
            token_type = CxxTokenType.IDENTIFIER_MACRO
        elif t.kind == TokenKind.IDENTIFIER:
            token_type = identifier_token_type(t.cursor)
            ref = cursor_to_symbol_id(t.cursor)
        elif t.kind == TokenKind.KEYWORD:
            token_type = CxxTokenType.KEYWORD_TYPE if t.spelling in _TYPE_KEYWORDS else CxxTokenType.KEYWORD
        elif t.kind == TokenKind.LITERAL:
            if _STRING_OR_CHAR_LITERAL.fullmatch(t.spelling):
                token_type = CxxTokenType.LITERAL_STRING
            elif _NUMBER_LITERAL.fullmatch(t.spelling):
                token_type = CxxTokenType.LITERAL_NUMBER
            else:
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
