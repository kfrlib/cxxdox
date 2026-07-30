from dataclasses import dataclass
from enum import Enum
from .logs import log

from cxxdox_plugin.identifiers import parse_cpp_identifier
from .utils import add_default_namespace, normalize_symbol_name


class SymbolType(Enum):
    NAMESPACE       = 'namespace'
    FUNCTION        = 'function'
    CLASS           = 'class'
    STRUCT          = 'struct'
    UNION           = 'union'
    TYPEDEF         = 'typedef'
    ENUM            = 'enum'
    ENUM_CONSTANT   = 'enum-constant'
    VARIABLE        = 'variable'
    CONCEPT         = 'concept'
    DEDUCTION_GUIDE = 'deduction-guide'
    MACRO           = 'macro'
    CONSTRUCTOR     = 'constructor'
    DESTRUCTOR      = 'destructor'
    OPERATOR        = 'operator'

    def __str__(self):
        return self.value
    
    @staticmethod
    def all() -> list[str]:
        return [e.value for e in SymbolType]
    
    @staticmethod
    def classlike() -> list[str]:
        return [SymbolType.CLASS.value, SymbolType.STRUCT.value, SymbolType.UNION.value]
    
    @staticmethod
    def functionlike() -> list[str]:
        return [SymbolType.FUNCTION.value, SymbolType.CONSTRUCTOR.value, SymbolType.DESTRUCTOR.value, SymbolType.OPERATOR.value]
    
    @staticmethod
    def namespace_scope() -> list[str|None]:
        return [SymbolType.NAMESPACE.value, None]
    
    @staticmethod
    def all_and_none() -> list[str|None]:
        return [None] + [e.value for e in SymbolType]
    
@dataclass
class Namespace:
    type: SymbolType
    id: str
    spelling: str
    name: str
    full_name: str
    permalink: str
    parent: str|None

@dataclass
class Symbol:
    type: SymbolType
    id: str
    spelling: str
    name: str
    full_name: str
    file: str
    line: int
    is_definition: bool
    permalink: str
    parent: str|None
    source: list|None

class CxxTokenType(Enum):
    IDENTIFIER      = 'n'
    IDENTIFIER_NAMESPACE = 'nn'
    IDENTIFIER_FUNCTION  = 'nf'
    IDENTIFIER_CLASS     = 'nc'
    IDENTIFIER_VAR       = 'nv'
    IDENTIFIER_MACRO     = 'nx'
    KEYWORD         = 'k'
    KEYWORD_TYPE    = 'kt'
    LITERAL         = 'l'
    LITERAL_NUMBER  = 'm'
    LITERAL_STRING  = 's'
    COMMENT         = 'c'
    COMMENT_PREPROC = 'cp'
    PUNCTUATION     = 'p'
    UNKNOWN         = 'x'
    WHITESPACE      = 'w'

    def __str__(self):
        return self.value
    
@dataclass
class CxxToken:
    type: CxxTokenType
    spelling: str
    ref: str|None = None

    def as_dict(self) -> dict:
        return {
            'type': str(self.type),
            'spelling': self.spelling,
            'ref': self.ref
        }

class Index:
    symbols: dict[str, dict]
    files: dict[str, list[CxxToken]]

    def __init__(self):
        self.symbols = {}

    def add_file(self, filename: str, tokens: list[CxxToken]):
        self.files[filename] = tokens

    def add_symbol(self, id: str, data: dict):
        if id in self.symbols:
            # A definition can be lexically nested differently from its
            # declaration (for example, an out-of-class member definition).
            # Preserve the declaration's semantic identity while accepting
            # the definition's source, documentation, and definition status.
            identity_keys = {
                'full_name', 'name', 'spelling', 'scope', 'params',
                'tparams', 'own_name', 'parent', 'type'
            }
            data = data.copy()
            for key in identity_keys:
                if self.symbols[id].get(key):
                    data[key] = self.symbols[id][key]

            # Overwrite if previous one wasn't definition but this one is
            if not self.symbols[id].get('is_definition', False) and data.get('is_definition', False):
                self.symbols[id] = data
            else:
                self.symbols[id].update(data)
        else:
            self.symbols[id] = data

    def all_symbols(self) -> list[str]:
        return sorted(list(self.symbols.keys()))

    def has_symbol(self, id: str) -> bool:
        return id in self.symbols

    def set_permalink(self, id: str, url: str) -> None:
        if id in self.symbols:
            self.symbols[id]['permalink'] = url

    def symbol_permalink(self, id: str) -> str|None:
        if id in self.symbols:
            return self.symbols[id].get('permalink', None)
        return None

    def lookup_by_permalink(self, permalink: str) -> list[str]:
        return [
            id for id, symbol in self.symbols.items()
            if symbol.get('permalink') == permalink
        ]

    excluded_types: set[str] = {SymbolType.DEDUCTION_GUIDE.value}

    def _simple_lookup(self, pattern: str, default_namespace: str) -> set[str]:
        # Macro names are not namespace-qualified in the same way as C++
        # symbols. Match their spelling before applying the default namespace.
        macro_matches = {
            id for id, sym in self.symbols.items()
            if sym.get('type') == SymbolType.MACRO.value
            and sym.get('spelling') == pattern
        }
        if macro_matches:
            return macro_matches

        pattern = add_default_namespace(pattern, default_namespace)

        search_scope, search_name, search_tparams, search_params = parse_cpp_identifier(pattern)

        matches = set()

        for id, sym in self.symbols.items():
            if sym.get('type') in self.excluded_types:
                continue
            scope = sym.get('scope', '')
            own_name = sym.get('own_name', '')
            tparams = sym.get('tparams', '')
            params = sym.get('params', '')
            if own_name != search_name or scope != search_scope:
                continue
            if search_tparams and normalize_symbol_name(tparams) != normalize_symbol_name(search_tparams):
                continue
            if not search_tparams and sym.get('specialization', False):
                continue
            if search_params and normalize_symbol_name(params) != normalize_symbol_name(search_params):
                continue
            matches.add(id)

        return matches

    def simple_lookup(self, pattern: str, default_namespace: str) -> str|None:
        matches = self._simple_lookup(pattern, default_namespace)

        if len(matches) == 1:
            return matches.pop()
        if len(matches) > 1:
            log.warning(f"Ambiguous lookup for pattern '{pattern}' in namespace '{default_namespace}': {[sym.get('full_name', '') for sym in (self.symbols[m] for m in matches)]}")
        else:
            log.error(f"No match found for pattern '{pattern}' in namespace '{default_namespace}'")
        return None
    
    def simple_lookup_any(self, pattern: str, default_namespace: str) -> str|None:
        matches = self._simple_lookup(pattern, default_namespace)

        if len(matches) == 1:
            return matches.pop()
        if len(matches) > 1:
            def strip_hash(url: str) -> str:
                return url.split('#')[0] if url else ''

            permalinks = [strip_hash(self.symbols[id].get('permalink', '')) for id in matches]
            types = [self.symbols[id].get('type') for id in matches]
            if len(set(permalinks)) == 1 and len(set(types)) == 1:
                return next(iter(matches))

            log.warning(f"Ambiguous lookup for pattern '{pattern}' in namespace '{default_namespace}': {[sym.get('full_name', '') for sym in (self.symbols[m] for m in matches)]}")
        else:
            log.error(f"No match found for pattern '{pattern}' in namespace '{default_namespace}'")
        return None

    def simple_lookup_link(self, pattern: str, default_namespace: str) -> str|None:
        matches = self._simple_lookup(pattern, default_namespace)
        if len(matches) == 0:
            log.error(f"No match found for pattern '{pattern}' in namespace '{default_namespace}'")
            return None
        if len(matches) == 1:
            return self.symbols[matches.pop()].get('permalink', None)

        def strip_hash(url: str) -> str:
            return url.split('#')[0] if url else ''

        # If all matches point to the same page, the ambiguity is harmless.
        permalinks = [strip_hash(self.symbols[id].get('permalink', '')) for id in matches]
        if len(set(permalinks)) == 1:
            return permalinks[0]

        log.warning(f"Ambiguous lookup link for pattern '{pattern}' in namespace '{default_namespace}': "
                    f"{[self.symbols[m].get('full_name', '') for m in matches]} with permalinks {permalinks}")
        return None
    
    def scoped_lookup_all(self, scope: str, name: str) -> set:
        scope = scope.strip().removeprefix('::').removesuffix('::')

        name_scope, search_name, search_tparams, search_params = parse_cpp_identifier(name)
        name_scope = name_scope.removesuffix('::')
        if name_scope:
            # A qualified Doxygen reference can be relative to an enclosing
            # namespace.  Find enclosing paths whose complete symbol name
            # ends in the qualified reference; e.g. from ns::kfr::fn::f,
            # kfr::get_first resolves to ns::kfr::get_first.  Do not append
            # the reference scope to every enclosing path: that would make
            # kfr::fn::get_first incorrectly match kfr::get_first.
            target_components = name_scope.split('::') + [search_name]
            context_components = scope.split('::') if scope else []
            candidate_scopes = []
            for depth in range(len(context_components), -1, -1):
                candidate_components = context_components[:depth]
                if (candidate_components + [search_name])[-len(target_components):] != target_components:
                    continue
                candidate_scope = '::'.join(candidate_components) + '::' if candidate_components else ''
                candidate_scopes.append(candidate_scope)

            # Also consider the explicitly qualified name from the global
            # namespace after relative enclosing-namespace candidates.
            global_scope = f"{name_scope}::"
            if global_scope not in candidate_scopes:
                candidate_scopes.append(global_scope)
        else:
            components = scope.split('::') if scope else []
            # Walk outward from the innermost scope to the global namespace,
            # mirroring C++ unqualified name lookup.
            candidate_scopes = [
                '::'.join(components[:depth]) + '::' if depth > 0 else ''
                for depth in range(len(components), -1, -1)
            ]

        for candidate_scope in candidate_scopes:

            matches = set()
            for id, sym in self.symbols.items():
                if sym.get('type') in self.excluded_types:
                    continue
                if sym.get('scope', '') != candidate_scope or sym.get('own_name', '') != search_name:
                    continue
                if (search_tparams and
                    normalize_symbol_name(sym.get('tparams', '')) != normalize_symbol_name(search_tparams)):
                    continue
                if not search_tparams and sym.get('specialization', False):
                    continue
                if (search_params and
                    normalize_symbol_name(sym.get('params', '')) != normalize_symbol_name(search_params)):
                    continue
                matches.add(id)

            if len(matches) == 0:
                continue

            return matches
        return set()
    
    def scoped_lookup(self, scope: str, name: str) -> str|None:
        ids = self.scoped_lookup_all(scope, name)
        if len(ids) > 1:
            log.warning(f"Ambiguous scoped lookup '{name}' in scope '{scope}': {[self.symbols[m].get('full_name', '') for m in ids]}")
            return None
        return ids.pop() if ids else None
    
    def scoped_lookup_link(self, scope: str, name: str) -> str|None:
        ids = self.scoped_lookup_all(scope, name)
        if len(ids) == 0:
            return None
        if len(ids) == 1:
            return self.symbols[ids.pop()].get('permalink', None)
        
        def strip_hash(url: str) -> str:
            return url.split('#')[0] if url else ''
    
        # if all matches have the same permalink (except hash), return that permalink
        permalinks = [strip_hash(self.symbols[id].get('permalink', '')) for id in ids]
        if len(set(permalinks)) == 1:
            return permalinks[0]
        
        log.warning(f"Ambiguous scoped lookup for link '{name}' in scope '{scope}': {[self.symbols[m].get('full_name', '') for m in ids]} with permalinks {permalinks}")
        return None

    def lookup_by_type(self, self_type: list[str], parent_type: list[str|None] = [None], group: str|None = None) -> list[str]:
        result = []
        for id, sym in self.symbols.items():
            if sym.get('type') in self_type:
                parent_id = sym.get('parent')
                if parent_id is None:
                    if None not in parent_type:
                        continue
                elif self.symbols.get(parent_id, {}).get('type') not in parent_type:
                    continue
                if group is not None:
                    sym_group = sym.get('group') or 'default'
                    if sym_group != group:
                        continue
                result.append(id)
        return result

    def lookup_children(self, parent_id: str|None) -> list[str]:
        result = []
        for id, sym in self.symbols.items():
            if sym.get('parent') == parent_id:
                result.append(id)
        return result
    
    def lookup_group(self, group: str) -> list[str]:
        result = []
        for id, sym in self.symbols.items():
            sym_group = sym.get('group') or 'default'
            if sym_group == group:
                result.append(id)
        return result

    def top_level_symbols(self) -> list[str]:
        return self.lookup_children(None)

    def __getitem__(self, name: str) -> dict:
        return self.symbols.get(name, {})

    def dump(self) -> dict:
        return self.symbols
    
    @property
    def symbol_count(self) -> int:
        return len(self.symbols)
