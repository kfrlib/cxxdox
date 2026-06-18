from dataclasses import dataclass
from enum import Enum
import re


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
    KEYWORD         = 'k'
    LITERAL         = 'l'
    COMMENT         = 'c'
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

    symbol_prefixes: list[str] = []

    def __init__(self):
        self.symbols = {}

    def add_file(self, filename: str, tokens: list[CxxToken]):
        self.files[filename] = tokens

    def add_symbol(self, id: str, data: dict):
        if id in self.symbols:
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

    def lookup_by_scoped_name(self, namespace: str, name: str) -> str|None:
        def wrap_name(n: str) -> str:
            if not n.startswith('::'):
                n = '::' + n
            if not n.endswith('::'):
                n += '::'
            return n
        def share_prefix(a: str, b: str) -> bool:
            return a.startswith(b) or b.startswith(a)
        
        namespace = wrap_name(namespace)
        best_match = None
        best_depth = -1
        name = wrap_name(name)

        for id, sym in self.symbols.items():
            def test_symbol(full_name: str) -> bool:
                if not full_name.endswith(name):
                    return False
                # compare namespace part to the left of name suffix
                if not share_prefix(full_name[:-(len(name)-2)], namespace):
                    return False
                return True
            def strip_params(full_name: str) -> str:
                if full_name.endswith(')::'):
                    return re.sub(r'\(.*\)::$', '::', full_name)
                return full_name
            def strip_tparams(full_name: str) -> str:
                if full_name.endswith('>::'):
                    return re.sub(r'\<.*\>::$', '::', full_name)
                return full_name

            full_name: str = wrap_name(sym.get('full_name', ''))
            full_name_1 = strip_params(full_name)
            full_name_2 = strip_tparams(full_name_1)
            if not test_symbol(full_name) and not test_symbol(full_name_1) and not test_symbol(full_name_2):
                continue

            depth = full_name.count('::')
            if depth > best_depth:
                best_depth = depth
                best_match = id

        return best_match

    def lookup_by_type(self, self_type: list[str], parent_type: list[str|None] = [None]) -> list[str]:
        result = []
        for id, sym in self.symbols.items():
            if sym.get('type') in self_type:
                parent_id = sym.get('parent')
                if parent_id is None:
                    if None not in parent_type:
                        continue
                elif self.symbols.get(parent_id, {}).get('type') not in parent_type:
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
            if sym.get('group') == group:
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
