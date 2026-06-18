from typing import Any, Callable, Tuple
from cxxdox_plugin.doxygen import doxygen_to_html, escape
import mkdocs.plugins
import logging
import os
import json
import re
from dataclasses import dataclass
from mkdocs.structure.files import File, Files
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.pages import Page
from mkdocs.structure.nav import Section
from mkdocs.structure import StructureItem
from .config import CxxDoxConfig
from .parser import Parser, Index, SymbolType
from .logs import log
from hashlib import md5
from mkdocs.utils import copy_file
from pathlib import Path
from .extension import CxxDoxExtension
from mkdocs.structure.nav import Navigation
from urllib.parse import urlparse
from pathlib import PurePosixPath
from mkdocs.utils import find_or_create_node

@dataclass
class IndexPage:
    name: str
    title: str
    self_type: list[str]
    parent_type: list[str|None]

name_mapping = {
    'namespaces': 'Namespaces',
    'classes': 'Classes, Structs & Unions',
    'member-classes': 'Member Classes, Structs & Unions',
    'functions': 'Functions',
    'member-functions': 'Member Functions',
    'variables': 'Variables',
    'member-variables': 'Member Variables',
    'typedefs': 'Type Aliases',
    'member-typedefs': 'Member Type Aliases',
    'enums': 'Enumerations',
    'member-enums': 'Member Enumerations',
    'concepts': 'Concepts',
    'deduction-guides': 'Deduction Guides',
    'macros': 'Macros',
    'groups': 'Groups',
}
index_pages = [
    IndexPage("index.md", "All Symbols", SymbolType.all(), SymbolType.all_and_none()),
    IndexPage("namespaces/index.md", "Namespaces", [SymbolType.NAMESPACE.value], SymbolType.all_and_none()),
    IndexPage("classes/index.md", "Classes, Structs & Unions", SymbolType.classlike(), SymbolType.namespace_scope()),
    IndexPage("member-classes/index.md", "Member Classes, Structs & Unions", SymbolType.classlike(), SymbolType.classlike()),
    IndexPage("functions/index.md", "Functions", [SymbolType.FUNCTION.value], SymbolType.namespace_scope()),
    IndexPage("member-functions/index.md", "Member Functions", [SymbolType.FUNCTION.value], SymbolType.classlike()),
    IndexPage("variables/index.md", "Variables", [SymbolType.VARIABLE.value], SymbolType.namespace_scope()),
    IndexPage("member-variables/index.md", "Member Variables", [SymbolType.VARIABLE.value], SymbolType.classlike()),
    IndexPage("typedefs/index.md", "Type Aliases", [SymbolType.TYPEDEF.value], SymbolType.namespace_scope()),
    IndexPage("member-typedefs/index.md", "Member Type Aliases", [SymbolType.TYPEDEF.value], SymbolType.classlike()),
    IndexPage("enums/index.md", "Enumerations", [SymbolType.ENUM.value], SymbolType.namespace_scope()),
    IndexPage("member-enums/index.md", "Member Enumerations", [SymbolType.ENUM.value], SymbolType.classlike()),
    IndexPage("concepts/index.md", "Concepts", [SymbolType.CONCEPT.value], SymbolType.all_and_none()),
    IndexPage("deduction-guides/index.md", "Deduction Guides", [SymbolType.DEDUCTION_GUIDE.value], SymbolType.all_and_none()),
    IndexPage("macros/index.md", "Macros", [SymbolType.MACRO.value], SymbolType.all_and_none()),
]

@dataclass 
class DocPage:
    id: str
    full: bool = False

def plural(t: str) -> str:
    if t.endswith('y'):
        return t[:-1] + 'ies'
    elif t.endswith('s') or t.endswith('x') or t.endswith('z') or t.endswith('ch') or t.endswith('sh'):
        return t + 'es'
    else:
        return t + 's'

class CxxDoxPlugin(mkdocs.plugins.BasePlugin[CxxDoxConfig]):
    css_filename: str = "assets/cxxdox.css"

    index: Index
    doc_pages: dict[str, DocPage]
    groups: set[str]
    current_uri: str|None

    def __init__(self):
        self.index = Index()
        self.doc_pages = {}
        self.current_uri = None
        self.groups = set()

    def _map_symbols_to_pages(self, files: Files):
        names: dict[str,dict[str,str]] = {}
        def unique_name(id, name: str) -> str:
            if name not in names:
                names[name] = {id: name}
                return name
            d = names[name]
            if id in d:
                return d[id]
            i = 1
            while True:
                new_name = f"{name}~{i}"
                if new_name not in d.values():
                    d[id] = new_name
                    return new_name
                i += 1                

        def gen_uri(id, sym: dict) -> str:
            full_name = sym.get('full_name', '')
            type = sym.get('type', 'unknown')
            type = type.replace('struct', 'class').replace('union', 'class')
            parent = sym.get('parent', None)
            if parent is not None:
                parent_sym = self.index[parent]
                parent_type = parent_sym.get('type', 'unknown')
                if SymbolType(parent_type) in SymbolType.classlike():
                    type = 'member-' + type
            uri = full_name.lower()
            uri = re.sub(r'[^a-z0-9_\.]+', '.', uri)
            uri = uri.strip('.')
            uri = f"{plural(type)}/{uri}"
            return unique_name(id, uri)

        def find_top_level_parent(id: str) -> str:
            sym = self.index[id]
            parent_id = sym.get('parent', None)
            if parent_id is None:
                return id
            parent = self.index[parent_id]
            if parent.get('type', None) == SymbolType.NAMESPACE.value:
                return id
            return find_top_level_parent(parent_id)

        all = self.index.all_symbols()

        for id in all:
            sym = self.index[id]
            if group := sym.get('group', ''):
                self.groups.add(group)
            top_level_parent_id = find_top_level_parent(id)
            top_level_sym = self.index[top_level_parent_id]
            if top_level_parent_id == id:
                self.index.set_permalink(id, f"{self.config.path_prefix}{gen_uri(id, sym)}.md")
            else:
                self.index.set_permalink(id, f"{self.config.path_prefix}{gen_uri(top_level_parent_id, top_level_sym)}.md#{gen_uri(id, sym)}")

            page = self.doc_pages.setdefault(top_level_parent_id, DocPage(top_level_parent_id, full=sym.get('type') != SymbolType.NAMESPACE.value))

    def on_post_build(self, *, config: MkDocsConfig) -> None:
        css_physical_path = os.path.join(os.path.dirname(__file__), self.css_filename)
        copy_file(css_physical_path, os.path.join(config.site_dir, self.css_filename))

    def on_page_markdown(self, markdown: str, /, *, page: Page, config: MkDocsConfig, files: Files) -> str | None:
        self.current_uri = page.file.src_uri

    def on_page_content(self, html: str, /, *, page: Page, config: MkDocsConfig, files: Files) -> str | None:
        return html.replace('<b class="LAUyl5Cz5B"></b>', '')

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:

        dir = os.path.join(config.docs_dir, self.config.root)
        log.info(f"CxxDoxPlugin configuration: {self.config}, dir: {dir}")

        for input_cfg in self.config.input:
            parser = Parser(self.index,
                clang_args=input_cfg.compile_options,
                ignored_file_patterns=input_cfg.exclude,
                ignored_symbol_patterns=input_cfg.exclude_symbols
            )
            parser.parse_glob(input_cfg.include, input_cfg.exclude, dir)
        
        config.extra_css.insert(0, self.css_filename)

        config.markdown_extensions.append(CxxDoxExtension(self.index, self.link_resolver)) # type: ignore[arg-type]

        return config    
    
    def _generate_list(self, title: str, sym_ids: list[str], desc = '') -> str:
        markdown = f"# {escape(title)}\n\n"

        if desc:
            markdown += desc + '\n\n'

        syms: list[dict] = [{**self.index[sym_id], 'id': sym_id} for sym_id in sym_ids]
        syms.sort(key=lambda x: re.sub(r'[^\w]', '', x.get('name', '').lower()))

        letter = ''
        for sym in syms:
            name = sym.get('name', '')
            first_letter = re.sub(r'[^\w]', '', name.upper())[0]
            if first_letter != letter:
                letter = first_letter
                markdown += f"\n### {escape(letter)}\n\n"

            id: str = sym.get('id', '')

            file = sym.get('file')
            if file:
                file = f"({file}:{sym.get('line', '')})"
            
            markdown += f"- [[`{id}`:type:brief]]\n"

        return markdown

    def _generate_index(self, title: str, self_type: list[str], parent_type: list[str|None]) -> str:
        sym_ids = self.index.lookup_by_type(self_type, parent_type)
        return self._generate_list(title, sym_ids)

    def on_files(self, files: Files, /, *, config: MkDocsConfig):

        generated_nav = []
        def add_nav(full_uri: str, title: str):
            uri = full_uri.removeprefix(self.config.path_prefix)
            nav_path_parts = PurePosixPath(uri).parent.parts

            branch = generated_nav
            for part in nav_path_parts:
                part = name_mapping.get(part, part)
                branch = find_or_create_node(branch, part)

            branch.append({title: full_uri})
        
        log.info('Generating symbol permalinks...')
        self._map_symbols_to_pages(files)

        low_rank = '---\nsearch:\n  boost: 0.5\n---\n\n'

        with open('out.json', 'w') as f:
            json.dump(self.index.dump(), f, indent='\t', sort_keys=True, default=lambda o: o.as_dict() if hasattr(o, 'as_dict') else str(o))

        if self.groups:
            log.info('Generating groups...')

            groups_list = low_rank + "# Groups\n\n"
            for group in sorted(self.groups):
                groups_list += f"- [{group}]({group}.md)\n"
                group_desc = ''
                group_title = group
                if group_info := Parser.per_group_doc.get(group):
                    if title := group_info.get('title', ''):
                        group_title = title
                        groups_list += title + '\n\n'
                    if desc := group_info.get('desc', ''):
                        group_desc = doxygen_to_html(desc, self.index, '', self.link_resolver) + '\n\n'

                log.info(f"Generating group page: {self.config.path_prefix}groups/{group}.md")
                self.current_uri = f"{self.config.path_prefix}groups/{group}.md"
                files.append(File.generated(config, f"{self.config.path_prefix}groups/{group}.md", content=self._generate_list(f"Group: {group}", self.index.lookup_group(group), group_desc)))
                add_nav(f"{self.config.path_prefix}groups/{group}.md", group_title)

            files.append(File.generated(config, f"{self.config.path_prefix}groups/index.md", content=groups_list))
            add_nav(f"{self.config.path_prefix}groups/index.md", "Groups")

        log.info('Generating index pages...')

        for page in index_pages:
            log.info(f"Generating index page: {self.config.path_prefix+page.name} ({page.title})")
            self.current_uri = self.config.path_prefix + page.name
            files.append(File.generated(config, f"{self.config.path_prefix+page.name}", content=low_rank+self._generate_index(page.title, page.self_type, page.parent_type)))
            add_nav(self.config.path_prefix+page.name, page.title)

        log.info('Generating symbol pages...')

        for id, page in self.doc_pages.items():
            sym = self.index[id]

            content = ''
            
            perma: str = self.index.symbol_permalink(id) or ""
            full_name = sym.get('full_name', '')
            type: str = sym.get('type') or 'unknown'
            if '#' in perma:
                perma = perma.split('#')[0]
            if page.full:
                content += f"# ::: {full_name}\n\n"
                log.info(f"Generating symbol page {perma}: {full_name} ({id})")
            else:
                content += self._generate_list(f"Namespace {full_name}", self.index.lookup_children(id))

            files.append(File.generated(config, f"{perma}", content=content))
            add_nav(perma, f'<code class="cxx-label-{type}">{type.replace("-", " ")}</code> {escape(full_name)}')


        def attach(node: list|dict|str, parent: list|None = None) -> bool:
            if isinstance(node, list):
                for n in node:
                    if attach(n, node):
                        return True
                return False
            title = ''
            link = ''
            if isinstance(node, dict):
                items: list[Tuple[str,Any]] = list(node.items()) # type: ignore[var-annotated]
                if len(items) != 1:
                    return False
                first = items[0]
                if isinstance(first[1], list):
                    return attach(first[1])
                title, link = first
            elif isinstance(node, str):
                link = node
            if link == self.config.path_prefix + 'index.md':
                if not parent:
                    log.error(f'{self.config.path_prefix}index.md found at top level:', title)
                    return False
                parent.extend(generated_nav)
                return True
            return False

        if config.nav is not None:
            if not attach(config.nav):
                log.error(f'Failed to attach generated nav to {self.config.path_prefix}index.md: not found')

        return files
    
    @staticmethod
    def relative_url_path(src: str, dest: str) -> str:
        dest_parts = urlparse(dest)
        src_parts = urlparse(src)

        src_path = PurePosixPath(src_parts.path)
        dest_path = PurePosixPath(dest_parts.path)

        rel_path = dest_path.relative_to(src_path.parent) if src_path != dest_path else PurePosixPath('.')

        if dest_parts.fragment:
            rel_path = f"{rel_path}#{dest_parts.fragment}"

        return str(rel_path)
    
    def link_resolver(self, abs_path: str) -> str:
        if '*' in abs_path:
            abs_path = abs_path.replace('*', self.config.path_prefix)
        if self.current_uri is not None:
            result = os.path.relpath(abs_path, start=os.path.dirname(self.current_uri)).replace('\\', '/')
            return result
        return abs_path
