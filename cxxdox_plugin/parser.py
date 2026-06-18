from dataclasses import dataclass
from enum import Enum
import json
from os import path
import re
import logging
import fnmatch
from typing import Tuple

from cxxdox_plugin.index import CxxToken, CxxTokenType
from cxxdox_plugin.highlight import to_cxx_tokens
from .libclang21.cindex import Index as ClangIndex, CursorKind, SourceRange, Cursor, TokenGroup, TranslationUnit, SourceLocation, AccessSpecifier, Config as ClangConfig
from cxxdox_plugin.doxygen import parse_doxygen_comment
from .logs import log
from .index import *
import glob
from ctypes import cast, POINTER, c_ubyte, c_uint

# Set library file for libclang: libclang21/libclang.{dll,so,dylib}
ClangConfig.set_library_path(path.join(path.dirname(__file__), 'libclang21'))

verbose = True

def map_cursor_to_symbol_type(cursor: Cursor) -> SymbolType|None:
    if cursor.kind == CursorKind.NAMESPACE:
        return SymbolType.NAMESPACE
    elif cursor.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, CursorKind.FUNCTION_TEMPLATE]:
        if cursor.spelling.startswith('<deduction guide'):
            return SymbolType.DEDUCTION_GUIDE
        return SymbolType.FUNCTION
    elif cursor.kind == CursorKind.CONSTRUCTOR:
        return SymbolType.CONSTRUCTOR
    elif cursor.kind == CursorKind.DESTRUCTOR:
        return SymbolType.DESTRUCTOR
    elif cursor.kind == CursorKind.CONVERSION_FUNCTION:
        return SymbolType.OPERATOR
    elif cursor.kind in [CursorKind.CLASS_DECL, CursorKind.CLASS_TEMPLATE, CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION]:
        return SymbolType.CLASS
    elif cursor.kind == CursorKind.STRUCT_DECL:
        return SymbolType.STRUCT
    elif cursor.kind == CursorKind.UNION_DECL:
        return SymbolType.UNION
    elif cursor.kind in [CursorKind.TYPEDEF_DECL, CursorKind.TYPE_ALIAS_DECL, CursorKind.USING_DECLARATION, CursorKind.TYPE_ALIAS_TEMPLATE_DECL]:
        return SymbolType.TYPEDEF
    elif cursor.kind == CursorKind.ENUM_DECL:
        return SymbolType.ENUM
    elif cursor.kind == CursorKind.ENUM_CONSTANT_DECL:
        return SymbolType.ENUM_CONSTANT
    elif cursor.kind in [CursorKind.VAR_DECL, CursorKind.FIELD_DECL]:
        return SymbolType.VARIABLE
    elif cursor.kind == CursorKind.CONCEPT_DECL:
        return SymbolType.CONCEPT
    elif cursor.kind == CursorKind.MACRO_DEFINITION:
        return SymbolType.MACRO
    elif cursor.kind == CursorKind.UNEXPOSED_DECL:
        decl_ptr = cursor.data[0]  # pointer to Decl
        if not decl_ptr:
            raise ValueError("Decl pointer is NULL")

        # cast pointer to a byte pointer for raw memory access
        byte_ptr = cast(decl_ptr, POINTER(c_ubyte))

        # read byte at offset 28
        decl_kind = byte_ptr[28] & 0x7F
        if decl_kind == 69:
            log.warning(f"Unexposed decl kind: {decl_kind} for cursor {cursor.spelling} ({cursor.kind})")
            return SymbolType.VARIABLE
    return None

def cursor_as_dict(cursor):
    return {
        'kind': str(cursor.kind),
        'spelling': cursor.spelling,
        'displayname': cursor.displayname,
        'type': cursor.type,
        'get_num_template_arguments': cursor.get_num_template_arguments(),
        'location': {
            'file': str(cursor.location.file.name) if cursor.location.file else None,
            'line': cursor.location.line,
            'column': cursor.location.column,
        },
        'extent': {
            'start': {
                'file': str(cursor.extent.start.file.name) if cursor.extent.start.file else None,
                'line': cursor.extent.start.line,
                'column': cursor.extent.start.column,
            },
            'end': {
                'file': str(cursor.extent.end.file.name) if cursor.extent.end.file else None,
                'line': cursor.extent.end.line,
                'column': cursor.extent.end.column,
            },
        },
        'access_specifier': str(cursor.access_specifier),
        'is_definition': cursor.is_definition(),
        'raw_comment': cursor.raw_comment,
        'usr': cursor.get_usr(),
    }

@dataclass
class Source:
    content: bytes
    group: str|None

class Parser:
    clang_args: list[str]
    index: Index
    clang_index: ClangIndex
    translation_unit: TranslationUnit
    file_path: str
    ignored_file_patterns: list[str]
    ignored_symbol_patterns: list[str]

    per_file_doc: dict[str, dict] = {}
    per_group_doc: dict[str, dict] = {}
    source_cache: dict[str, Source] = {} # Class variable to cache file contents

    def __init__(self, index: Index, clang_args: list[str] = [], ignored_file_patterns: list[str] = [], 
                 ignored_symbol_patterns: list[str] = []):
        self.index = index
        self.clang_args = clang_args
        self.ignored_file_patterns = ignored_file_patterns
        self.ignored_symbol_patterns = ignored_symbol_patterns
        self.clang_index = ClangIndex.create()

    @staticmethod
    def _extract_doc(raw_comment: str) -> list|None:
        if not raw_comment:
            return None
        raw_comment = raw_comment.strip().replace('\r\n', '\n').replace('\r', '\n')
        if raw_comment.startswith('///<'):
            raw_comment = raw_comment[4:]
        elif raw_comment.startswith('///'):
            raw_comment = raw_comment[3:]
            raw_comment = re.sub(r'\n\s*///', '\n', raw_comment)
        elif raw_comment.startswith('/**<') and raw_comment.endswith('*/'):
            raw_comment = raw_comment[4:-2]
        elif raw_comment.startswith('/**') and raw_comment.endswith('*/'):
            raw_comment = raw_comment[3:-2]
            raw_comment = re.sub(r'\n\s*\*', '\n', raw_comment)
        elif raw_comment.startswith('/*') and raw_comment.endswith('*/'):
            raw_comment = raw_comment[2:-2]
        elif raw_comment.startswith('//'):
            raw_comment = raw_comment[2:]
            raw_comment = re.sub(r'\n\s*//', '\n', raw_comment)

        return parse_doxygen_comment(raw_comment.strip())

    def _is_ignored(self, cursor: Cursor, fully_qualified_name: str) -> bool:
        if cursor.location.file is None:
            return False
        file_name = cursor.location.file.name
        for pattern in (self.ignored_file_patterns or []):
            if fnmatch.fnmatch(file_name, pattern):
                return True
        for pattern in (self.ignored_symbol_patterns or []):
            if fnmatch.fnmatch(fully_qualified_name, pattern):
                return True
        return False

    @staticmethod
    def _is_scope(cursor: Cursor) -> bool:
        return cursor.kind in [CursorKind.NAMESPACE, CursorKind.CLASS_DECL,
                CursorKind.STRUCT_DECL, CursorKind.UNION_DECL,
                CursorKind.CLASS_TEMPLATE, CursorKind.ENUM_DECL,
                CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION]
    
    @staticmethod
    def _read_source(file_name: str) -> Source:
        file_name = path.abspath(file_name)
        if file_name in Parser.source_cache:
            return Parser.source_cache[file_name]
        else:
            contents: bytes = b''
            with open(file_name, 'rb') as f:
                contents = f.read()
            Parser.source_cache[file_name] = Source(contents, Parser._parse_file_doc(contents))
            return Parser.source_cache[file_name]
    
    @staticmethod
    def _extract_file_source(translation_unit: TranslationUnit, file_name: str) -> list[CxxToken]|None:
        source = Parser._read_source(file_name).content
        tokens = TokenGroup.get_tokens(translation_unit, SourceRange.from_locations(
            SourceLocation.from_offset(translation_unit, file_name, 0),
            SourceLocation.from_offset(translation_unit, file_name, len(source))))
        result = to_cxx_tokens(tokens, source)
        return result
    
    @staticmethod
    def _extract_symbol_group(cursor: Cursor) -> str|None:
        if cursor.is_null():
            return None
        if raw_comment := cursor.raw_comment:
            raw_comment = raw_comment.strip()
            m = re.search(r'[@\\]ingroup\s+([^\s]+)', raw_comment)
            if m:
                return m.group(1)
        
        if cursor.semantic_parent is not None:
            return Parser._extract_symbol_group(cursor.semantic_parent)
        else:
            return None
        
    @staticmethod
    def _parse_file_doc(contents: bytes) -> str|None:
        if contents.find(b'addtogroup') == -1:
            return None
        source = contents.decode('utf-8', errors='ignore')

        file_group = None

        # find all comments: sequences of //... and /*...*/ in source:
        comments = re.findall(r"""
(?:
    //[^\n]*(?:\n[ \t]*//[^\n]*)*       # consecutive // comments
  |
    /\*[^*]*\*+(?:[^/*][^*]*\*+)*/     # /* ... */ block comments
)
""", source, re.VERBOSE)

        for comment in comments:
            comment = comment.replace('\r\n', '\n')
            if doc := Parser._extract_doc(comment):
                for item in doc:
                    if isinstance(item, dict) and 'addtogroup' in item:
                        Parser.per_group_doc[item['addtogroup']['name']] = item['addtogroup']
                        file_group = item['addtogroup']['name']
                        return item['addtogroup']['name']
        return file_group

    @staticmethod
    def _extract_group(cursor: Cursor) -> str|None:
        if group := Parser._extract_symbol_group(cursor):
            return group
        
        extent: SourceRange = cursor.extent
        start: SourceLocation = extent.start
        end: SourceLocation = extent.end
        if start.file is None or end.file is None:
            log.warning(f'Warning: Extent has no associated file: {cursor.spelling}')
            return None
        if start.file.name != end.file.name:
            log.warning(f'Warning: Extent spans multiple files: {cursor.spelling}')
            return None
        file_name = start.file.name
        source = Parser._read_source(file_name)
        return source.group

    @staticmethod
    def _extract_source(cursor: Cursor) -> list[CxxToken]|None:
        if cursor.kind in [CursorKind.TRANSLATION_UNIT, CursorKind.NAMESPACE]:
            return None
        
        extent: SourceRange = cursor.extent
        start: SourceLocation = extent.start
        end: SourceLocation = extent.end
        if start.file is None or end.file is None:
            log.warning(f'Warning: Extent has no associated file: {cursor.spelling}')
            return None
        if start.file.name != end.file.name:
            log.warning(f'Warning: Extent spans multiple files: {cursor.spelling}')
            return None
        file_name = start.file.name
        source = Parser._read_source(file_name).content

        extent = cursor.extent
        ellipsis = False
        if cursor.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD,
                           CursorKind.FUNCTION_TEMPLATE, CursorKind.CONVERSION_FUNCTION,
                           CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR, CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL,
                           CursorKind.UNION_DECL, CursorKind.CLASS_TEMPLATE,
                           CursorKind.ENUM_DECL, CursorKind.CONCEPT_DECL,
                           CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION]:
            # Shrink to exclude body (brace enclosed)
            lasttoken = None
            for token in cursor.get_tokens():
                if token.spelling == '{' and lasttoken is not None:
                    extent = SourceRange.from_locations(extent.start, lasttoken.extent.end)
                    ellipsis = True
                    break
                lasttoken = token

        indent = extent.start.column - 1
        
        tokens = TokenGroup.get_tokens(cursor.translation_unit, extent)
        result = to_cxx_tokens(tokens, source, indent)
        if ellipsis:
            result.append(CxxToken(CxxTokenType.PUNCTUATION, ' { … }'))
        return result

    def _fix_name(self, name: str) -> str:
        m = re.match(r'^\(unnamed (union|struct|enum) at (.*)(:\d+:\d+)\)', name)
        if m:
            name = '(Unnamed ' + m.group(1) + ' at ' + str(self._relative_path(m.group(2))) + m.group(3) + ')'
        m = re.match(r'^(union|struct|enum) \(unnamed at (.*)(:\d+:\d+)\)', name)
        if m:
            name = '(Unnamed ' + m.group(1) + ' at ' + str(self._relative_path(m.group(2))) + m.group(3) + ')'
        m = re.match(r'^\(anonymous (union|struct) at (.*)(:\d+:\d+)\)', name)
        if m:
            name = '(Anonymous ' + m.group(1) + ' at ' + str(self._relative_path(m.group(2))) + m.group(3) + ')'
        return name

    def _relative_path(self, full_path: str) -> str:
        return path.relpath(full_path, path.dirname(self.file_path)).replace('\\', '/')

    def parse(self, file_path: str):
        log.info(f'Parsing c/c++ file: {file_path}')
        saved_symbols = self.index.symbol_count
        self.file_path = file_path
        self.translation_unit = self.clang_index.parse(file_path, self.clang_args, 
                                                       options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES)
        if not self.translation_unit:
            log.warning(f'Unable to load input: {file_path}')
            self.file_path = ''
            return
        if not self.translation_unit.cursor:
            log.warning(f'Unable to get translation unit cursor: {file_path}')
            self.file_path = ''
            return

        if verbose and len(self.translation_unit.diagnostics):
            log.warning('------------DIAGNOSTICS---------------')
            for diag in self.translation_unit.diagnostics:
                log.warning(diag)
            log.warning('------------/DIAGNOSTICS---------------')
        self._parse_recursive(self.translation_unit.cursor)

        added_symbols = self.index.symbol_count - saved_symbols
        log.info(f'Added {added_symbols} symbols from {file_path}')

    def parse_glob(self, include_patterns: list[str], exclude_patterns: list[str], root_dir: str):
        files = []
        for pattern in include_patterns:
            matched = glob.glob(path.join(root_dir, pattern), recursive=True)
            files.extend(matched)
        for pattern in exclude_patterns:
            excluded = glob.glob(path.join(root_dir, pattern), recursive=True)
            files = [f for f in files if f not in excluded]
        files = set(files) # Remove duplicates
        for file in files:
            self.parse(file)

    @staticmethod
    def _split_brief(doc: list[str|dict]) -> tuple[str,list]:
        if not doc:
            return '', []
        for item in doc:
            if isinstance(item, str):
                brief = item.strip()
                if brief:
                    doc.remove(item)
                    return brief, doc
            elif isinstance(item, dict) and 'brief' in item:
                brief = item['brief']
                if isinstance(brief, str):
                    brief = brief.strip()
                if brief:
                    doc.remove(item)
                    return brief, doc
        return '', doc

    def _parse_recursive(self, cursor: Cursor, path: list = [], parent_id: str|None = None):
        rel_path = self._relative_path(str(cursor.location.file.name)) if cursor.location.file else None

        type = map_cursor_to_symbol_type(cursor)

        spelling: str = cursor.spelling
        displayname: str = cursor.displayname

        if type == SymbolType.DEDUCTION_GUIDE:
            spelling = spelling.removeprefix('<deduction guide for ').removesuffix('>')
            displayname = spelling.removeprefix('<deduction guide for ').replace('>(', '(')

        spelling = self._fix_name(spelling)
        spelling = re.sub(r'[^a-zA-Z0-9_]+', '_', spelling) # Ensure spelling is a C identifier
        displayname = self._fix_name(displayname)        

        fully_qualified_name: str = '::'.join(path + [displayname])

        if self._is_ignored(cursor, fully_qualified_name):
            return
        
        access_spec = ''
        if cursor.access_specifier == AccessSpecifier.PROTECTED:
            access_spec = 'protected'
        elif cursor.access_specifier == AccessSpecifier.PUBLIC:
            access_spec = 'public'
        elif cursor.access_specifier == AccessSpecifier.PRIVATE:
            return

        symbol_dict = {
            'type': str(type),
            'spelling': spelling,
            'name': displayname,
            'full_name': fully_qualified_name,
            'parent': parent_id,
        }
        if type is not None and not cursor.kind == CursorKind.NAMESPACE:
            if cursor.extent.start.file is None:
                return
            if not cursor.spelling:
                log.error(f"Cursor with no spelling: {cursor_as_dict(cursor)}")
                return
            if rel_path:
                symbol_dict['file'] = rel_path
                symbol_dict['line'] = cursor.location.line

                if src := Parser._extract_source(cursor):
                    symbol_dict['source'] = src
                
                if group := Parser._extract_group(cursor):
                    symbol_dict['group'] = group

            if doc := Parser._extract_doc(cursor.raw_comment):
                brief, details = Parser._split_brief(doc)
                symbol_dict['brief'] = brief
                symbol_dict['details'] = details
                
            if access_spec:
                symbol_dict['access'] = access_spec

            if cursor.is_definition():
                symbol_dict['is_definition'] = True

        if Parser._is_scope(cursor):
            parent_id = cursor.get_usr()
            path = path + [displayname]
            
        if type is not None:
            self.index.add_symbol(cursor.get_usr(), symbol_dict)

        for child in cursor.get_children():
            if child.location.is_in_system_header:
                continue
            if child.kind.is_statement() or child.kind.is_expression():
                continue
            self._parse_recursive(child, path, parent_id)

if __name__ == '__main__':
    dir = 'demo'
    index = Index()
    parser = Parser(index, 
                    clang_args=['-std=c++20', '-I'+dir+'/include'], 
                    ignored_file_patterns=['*/thirdparty/*'], 
                    ignored_symbol_patterns=['*::internal::*', 
                                             '*::internal_generic::*', 
                                             '*::intr::*', 
                                             '*::details::*', 
                                             '*::fn::*'])
    
    parser.parse(dir+'/library.hpp')
    
    with open('output.json', 'w') as f:
        json.dump(index.dump(), f, indent='\t', sort_keys=True)
