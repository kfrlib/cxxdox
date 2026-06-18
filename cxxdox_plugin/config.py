
from mkdocs.config.config_options import Type, Optional, ListOfItems, SubConfig, Dir
from mkdocs.config.base import Config

class InputDict(Config):
    include = ListOfItems(Type(str))
    exclude = ListOfItems(Type(str), default=[])
    exclude_symbols = ListOfItems(Type(str), default=[])
    compile_options = ListOfItems(Type(str), default=[])
    hide_tokens = ListOfItems(Type(str), default=[])

class CxxDoxConfig(Config):
    title = Type(str, default="CxxDox Documentation")
    input = ListOfItems(SubConfig(InputDict))
    path_prefix = Type(str, default="cxxdox/")
    symbol_prefixes = ListOfItems(Type(str), default=[])
    root = Dir(default=".")
