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
from .extension import strip_default_namespace

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

def _plural(t: str) -> str:
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
    current_uri: str|None

    def __init__(self):
        self.index = Index()
        self.doc_pages = {}
        self.current_uri = None
        
    def _symbol_type_slug(self, sym) -> str:
        type = sym.get('type', 'unknown')
        type = type.replace('struct', 'class').replace('union', 'class')
        parent = sym.get('parent', None)
        if parent is not None:
            parent_sym = self.index[parent]
            parent_type = parent_sym.get('type', 'unknown')
            if SymbolType(parent_type) in SymbolType.classlike():
                type = 'member-' + type
        return _plural(type)

    def _map_symbols_to_pages(self, files: Files):
        """
        Assigns symbols to groups, and documentation pages. Generates unique permalinks for each symbol.
        """
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

        def gen_uri(id: str, sym: dict, group: str) -> str:
            full_name = sym.get('full_name', '')
            uri = full_name.lower()
            uri = re.sub(r'[^a-z0-9_\.]+', '.', uri)
            uri = uri.strip('.')
            uri = f"{self._symbol_type_slug(sym)}/{uri}"
            if group:
                uri = group + '/' + uri
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
            group: str = 'default'
            if sym.get('type', None) == SymbolType.NAMESPACE.value:
                group = '' # Namespaces are not tied to a file or group
            else:
                for g in self.config.groups:
                    if g.matches(sym.get('file', '')):
                        group = g.id
                        break
            sym.setdefault('group', group)

            top_level_parent_id = find_top_level_parent(id)
            top_level_sym = self.index[top_level_parent_id]
            if top_level_parent_id == id:
                self.index.set_permalink(id, f"{self.config.path_prefix}{gen_uri(id, sym, group)}.md")
            else:
                self.index.set_permalink(id, f"{self.config.path_prefix}{gen_uri(top_level_parent_id, top_level_sym, group)}.md#{gen_uri(id, sym, group)}")

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
        log.debug(f"CxxDoxPlugin configuration: {self.config}, dir: {dir}")

        for input_cfg in self.config.input:
            parser = Parser(self.index,
                clang_args=input_cfg.compile_options,
                ignored_file_patterns=input_cfg.exclude,
                ignored_symbol_patterns=input_cfg.exclude_symbols
            )
            parser.parse_glob(input_cfg.include, input_cfg.exclude, dir)
        
        config.extra_css.insert(0, self.css_filename)

        config.markdown_extensions.append(CxxDoxExtension(self.index, self.link_resolver, self.config.default_namespace)) # type: ignore[arg-type]

        return config    
    
    def _generate_list(self, title: str, sym_ids: list[str], desc = '') -> str:
        markdown = f"# {escape(title)}\n\n"

        if desc:
            markdown += desc + '\n\n'

        syms: list[dict] = [{**self.index[sym_id], 'id': sym_id} for sym_id in sym_ids]
        syms.sort(key=lambda x: re.sub(r'[^\w]', '', x.get('name', '').lower()))

        use_details = len(syms) >= 200
        letter = ''
        first = True
        for sym in syms:
            name = sym.get('name', '')
            first_letter = re.sub(r'[^\w]', '', name.upper())[0]
            if first_letter != letter:
                if letter:
                    if use_details:
                        markdown += '\n</details>\n\n'
                letter = first_letter
                if use_details:
                    opened = ' open' if not first else ''
                    markdown += f"\n<details name=\"symbols-index\" markdown=\"1\"{opened}>\n\n<summary markdown=\"block\">\n\n### {escape(letter)}\n\n</summary>\n\n"
                else:
                    markdown += f"\n### {escape(letter)}\n\n"
                first = False

            id: str = sym.get('id', '')

            file = sym.get('file')
            if file:
                file = f"({file}:{sym.get('line', '')})"
            
            markdown += f"- [[`{id}`:type:brief]]\n"

        if letter:
            if use_details:
                markdown += '\n</details>\n'

        return markdown

    def _generate_index(self, title: str, self_type: list[str], parent_type: list[str|None], group: str|None = None) -> str | None:
        sym_ids = self.index.lookup_by_type(self_type, parent_type, group=group)
        if not sym_ids:
            return None
        return self._generate_list(title, sym_ids)

    def on_files(self, files: Files, /, *, config: MkDocsConfig):

        generated_nav = []

        def add_nav(nav_path: list[str], full_uri: str):
            branch = generated_nav
            for part in nav_path[:-1]:
                new_branch = find_or_create_node(branch, part)
                if isinstance(new_branch, str):
                    for item in branch:
                        if isinstance(item, dict) and part in item:
                            item[part] = [new_branch]
                            new_branch = item[part]
                            break
                branch = new_branch

            branch.append({nav_path[-1]: full_uri}) # type: ignore[list-item]

        log.info('Generating symbol permalinks...')
        self._map_symbols_to_pages(files)

        low_rank = '---\nsearch:\n  boost: 0.5\n---\n\n'

        with open('out.json', 'w') as f:
            json.dump(self.index.dump(), f, indent='\t', sort_keys=True, default=lambda o: o.as_dict() if hasattr(o, 'as_dict') else str(o))

        log.info('Generating groups...')

        # Per-type index pages that should be replicated under each group.
        # The first entry (the project-wide "All Symbols" page) is excluded.
        # The namespaces page is also excluded because namespaces are not
        # tied to a file or group, so they only make sense project-wide.
        per_group_index_pages = index_pages[2:]

        for group in self.config.groups:
            log.info(f"Generating group page: {self.config.path_prefix}{group.id}/index.md")
            self.current_uri = f"{self.config.path_prefix}{group.id}/index.md"
            # The group's main index page carries the human-readable
            # title plus the description, so the per-group sub-pages
            # (variables, classes, ...) can stay focused on their
            # own headings.
            files.append(File.generated(config, f"{self.config.path_prefix}{group.id}/index.md", content=self._generate_list(group.title, self.index.lookup_group(group.id), group.description)))
            add_nav([group.title], f"{self.config.path_prefix}{group.id}/index.md")

            # Per-group per-type sub-pages (e.g. demo/variables/index.md)
            for page in per_group_index_pages:
                group_page_uri = f"{self.config.path_prefix}{group.id}/{page.name}"
                log.info(f"Generating group index page: {group_page_uri} ({page.title})")
                self.current_uri = group_page_uri
                content = self._generate_index(page.title, page.self_type, page.parent_type, group=group.id)
                if content is None:
                    log.info(f"Skipping empty group index page: {group_page_uri} ({page.title})")
                    continue
                files.append(File.generated(config, group_page_uri, content=low_rank+content))
                add_nav([group.title, page.title], group_page_uri)

        log.info('Generating project-wide index pages...')

        # Per-type index pages are normally generated per-group inside
        # {group_name}/. If no groups exist, fall back to project-wide
        # per-type pages so non-grouped projects still have them.
        # "All Symbols" and "Namespaces" are always project-wide because
        # namespaces are not scoped to a file or group.
        project_wide_pages = index_pages[:2]  # "All Symbols" and "Namespaces"

        for page in project_wide_pages:
            log.info(f"Generating index page: {self.config.path_prefix+page.name} ({page.title})")
            self.current_uri = self.config.path_prefix + page.name
            content = self._generate_index(page.title, page.self_type, page.parent_type)
            if content is None:
                log.info(f"Skipping empty index page: {self.config.path_prefix+page.name} ({page.title})")
                continue
            files.append(File.generated(config, f"{self.config.path_prefix+page.name}", content=low_rank+content))
            add_nav([page.title], self.config.path_prefix+page.name)

        log.info('Generating symbol pages...')

        for id, page in self.doc_pages.items():
            sym = self.index[id]
            group_id = sym.get('group', 'default')
            group = next((g for g in self.config.groups if g.id == group_id), None)
            group_title = group.title if group else 'Default'

            content = ''
            
            perma: str = self.index.symbol_permalink(id) or ""
            full_name = sym.get('full_name', '')
            type: str = sym.get('type') or 'unknown'
            if '#' in perma:
                perma = perma.split('#')[0]
            if page.full:
                content += f"# ::: {full_name}\n\n"
                log.debug(f"Generating symbol page {perma}: {full_name} ({id})")
            else:
                content += self._generate_list(f"Namespace {full_name}", self.index.lookup_children(id))

            files.append(File.generated(config, f"{perma}", content=content))
            slug = self._symbol_type_slug(sym)
            slug = name_mapping.get(slug, slug.replace('-', ' ').title())
            
            display_name = strip_default_namespace(full_name, self.config.default_namespace)
            nav_path = [
                group_title, 
                slug, 
                f'<code class="cxx-label-{type}">{type.replace("-", " ")}</code> {escape(display_name)}'
            ]
            if group_id == '':
                nav_path = nav_path[1:]  # Remove group title for namespaces
            add_nav(nav_path, perma)

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
