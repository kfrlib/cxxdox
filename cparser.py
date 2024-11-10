#!/usr/bin/env python

import glob
import yaml
import sys
import argparse
import cparser
import generator
import json
from clang.cindex import Index, CursorKind, Config
import codecs
import re
import os
from typing import List, Dict
from common import remove_padding

file_cache = {}


rules = [
    [r'[@\\]c\s+(\S+)', 'inlinecode', 1],
    [r'[@\\]ref\s+(\S+)', 'ref', 1],
    [r'\s*[@\\]code(.*?)\s+[@\\]endcode\s*', 'blockcode', 1],
    [r'\\f\\\((.*?)\\f\\\)', 'inlinemath', 1],
    [r'\\f\$(.*?)\\f\$', 'inlinemath', 1],
    [r'\$(.*?)\$', 'inlinemath', 1],
    [r'\s*\\f\[(.*?)\\f\]\s*', 'blockmath', 1],
    
    [r'[@\\]concept\s+', 'concept', 0],
    [r'[@\\]class\s+', 'class', 0],
    [r'[@\\]struct\s+', 'struct', 0],
    [r'[@\\]fn\s+', 'function', 0],
    [r'[@\\]enum\s+', 'enum', 0],
    [r'[@\\]typedef\s+', 'typedef', 0],
    
    [r'[@\\]param\s+(\S+)', 'param', 1],
    [r'[@\\]tparam\s+(\S+)', 'tparam', 1],

    [r'[@\\](?:throws?|exceptions?)\s+(\S+)', 'exceptions', 1],
    [r'[@\\](?:details|remark)\s+', 'details', 0],
    [r'[@\\](?:threadsafe|threadsafety)\s+', 'threadsafety', 0],
    [r'[@\\]note\s+', 'note', 0],
    [r'[@\\](?:see|sa)\s+', 'note', 0],
    [r'[@\\]returns?\s+', 'return', 0],
]

def parse_description(s):
    if isinstance(s, str):
        for rule in rules:
            m = re.search(rule[0], s, re.MULTILINE | re.DOTALL)
            if m is not None:
                prefix = s[:m.start()]
                match = remove_padding(m.group(1)).strip() if rule[2] > 0 else ''
                postfix = s[m.end():]
                return parse_description([prefix, {rule[1]: match}, postfix])

        return s
    elif isinstance(s, List):
        r = []
        for ss in s:
            if isinstance(ss, str):
                rr = parse_description(ss)
                if isinstance(rr, str):
                    if len(rr) > 0:
                        r.append(rr.strip())
                else:
                    r.extend(rr)
            else:
                r.append(ss)
        return r
    else:
        return s


def clean_text(str):
    str = str.replace('\t', '    ')
    str = str.replace('\r', '')
    return str



def get_location(node):
    if node is None:
        return ''
    if node.location is None:
        return ''
    if node.location.file is None:
        return ''
    return node.location.file.name


def get_location_line(node):
    if node is None:
        return -1
    if node.location is None:
        return -1
    return node.location.line


def get_source(cursor):
    assert cursor.extent.start.file.name == cursor.extent.end.file.name
    filename = cursor.extent.start.file.name
    if filename not in file_cache:
        file_cache[filename] = codecs.open(
            filename, 'r', encoding="utf-8").read()

    file_content = file_cache[filename].encode('utf-8')
    bytes = ' ' * (cursor.extent.start.column - 1) + clean_text(
        file_content[cursor.extent.start.offset:cursor.extent.end.offset].decode('utf-8'))
    return remove_padding(bytes)


def clean_comment(s):
    s = s.strip()
    if s.startswith('///<'):
        return remove_padding(s[4:])
    elif s.startswith('/**<'):
        return remove_padding(s[4::-2])
    elif s.startswith('///'):
        return remove_padding(re.sub(r'^\s*///', '', s, flags=re.MULTILINE))
    elif s.startswith('/**'):
        return remove_padding(re.sub(r'^\s*\*( |$)', '', s[3:-2], flags=re.MULTILINE))
    return s


def replace_macros(s: str, macros: Dict):
    for key, value in macros.items():
        s = re.sub(r'\b'+key+r'\b', value, s)
    return s


def same_location(x, y):
    return x == y


def class_name(node):

    template = []
    for c in node.get_children():
        if c.kind in [CursorKind.TEMPLATE_TYPE_PARAMETER, CursorKind.TEMPLATE_NON_TYPE_PARAMETER]:
            template.append(get_source(c))
    if template:
        template = 'template <' + ', '.join(template) + '>'
    else:
        template = ''

    return template + node.spelling


def source_to_definition(source):
    source = re.sub(r'^(.*?)\{.*', r'\1', source, flags=re.DOTALL).strip()
    return source


def parse_index(root_path, index: List[Dict], node, root_location, group: str, ns: str = '', macros={}, include_source=False):

    source = ''
    if node.brief_comment is not None:
        source = get_source(node)
        definition = source_to_definition(replace_macros(source, macros))

        entity: Dict = {}

        if node.kind in [CursorKind.FUNCTION_TEMPLATE, CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR, CursorKind.CONVERSION_FUNCTION, CursorKind.USING_DECLARATION]:
            entity['type'] = 'function'
            entity['name'] = node.spelling
            entity['definition'] = definition
        elif node.kind in [CursorKind.CLASS_TEMPLATE, CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION]:
            entity['type'] = 'class'
            entity['name'] = node.spelling
            entity['definition'] = class_name(node)
            entity['content'] = []
        elif node.kind in [CursorKind.ENUM_DECL]:
            entity['type'] = 'enum'
            entity['name'] = node.spelling
            entity['definition'] = definition
            entity['content'] = []
        elif node.kind in [CursorKind.ENUM_CONSTANT_DECL]:
            entity['type'] = 'enumerator'
            entity['name'] = node.spelling
            entity['definition'] = definition
        elif node.kind in [CursorKind.TYPEDEF_DECL, CursorKind.TYPE_ALIAS_DECL, CursorKind.TYPE_ALIAS_TEMPLATE_DECL]:
            entity['type'] = 'typedef'
            entity['name'] = node.spelling
            entity['definition'] = re.sub(r'(^|\s+)using\s+', r'', definition)
        elif node.kind in [CursorKind.VAR_DECL, CursorKind.UNEXPOSED_DECL, CursorKind.FIELD_DECL]:
            entity['type'] = 'variable'
            entity['name'] = node.spelling
            entity['definition'] = definition
        elif node.kind in [CursorKind.NAMESPACE]:
            entity['type'] = 'namespace'
            entity['name'] = node.displayname
            entity['definition'] = definition
            entity['source'] = definition + ' { ... }'
        elif node.kind in [CursorKind.CONCEPT_DECL]:
            entity['type'] = 'concept'
            entity['name'] = node.displayname
            entity['definition'] = definition
            entity['source'] = definition + ' { ... }'
        elif node.kind in [CursorKind.FRIEND_DECL]:
            print("ignored: {}".format(node.kind))
            return
        else:
            print('warning: Unknown cursor kind: {} for {}'.format(
                node.kind, node.displayname))
            return

        entity['qualifiedname'] = re.sub('^::', '', ns + '::' + entity['name'])
        if 'source' not in entity:
            entity['source'] = source

        if not include_source:
            entity['source'] = ""
        entity['file'] = os.path.relpath(
            get_location(node), root_path).replace('\\', '/')
        entity['line'] = get_location_line(node)
        description = clean_comment(clean_text(node.raw_comment))

        m = re.match(r'[@\\]copybrief\s+([a-zA-Z0-9:\._-]+)',
                     description.strip())
        if m:
            copyFrom = m.group(1)
            description = {"copy": copyFrom}
        else:
            description = re.sub(r'\s*@brief\s*', '', description)
            description = parse_description(description)

        entity['description'] = description

        index.append(entity)

        entity['group'] = group

        if 'content' in entity:
            index = entity['content']

    if node.kind == CursorKind.NAMESPACE:
        ns += ns+'::'+node.spelling

    if node.kind in [CursorKind.CLASS_TEMPLATE, CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION]:
        ns += ns+'::'+node.spelling

    if node.kind in [CursorKind.ENUM_DECL]:
        ns += ns+'::'+node.spelling

    for c in node.get_children():
        if same_location(get_location(c), root_location):
            parse_index(root_path, index, c, root_location, group, ns, macros)


def parse(index, root_path, filenames: List[str], clang_args: List[str], macros={}, include_source=False):

    for filename in filenames:
        print('Parsing ' + filename)

        group = ''
        with open(filename, 'r', encoding='utf-8') as strm:
            text = strm.read()
            m = re.search(r'@addtogroup\s+([a-zA-Z0-9_-]+)', text)
            if m:
                group = m.group(1)
            else:
                group = os.path.basename(os.path.dirname(filename))

        clangIndex = Index.create()
        cargs = [filename.replace('\\', '/')] + clang_args
        tu = clangIndex.parse(None, cargs)
        if not tu:
            print('Unable to load input')
            exit(1)

        if len(tu.diagnostics):
            print('------------DIAGNOSTICS---------------')
            for diag in tu.diagnostics:
                print(diag)
            print('------------/DIAGNOSTICS---------------')

        count = len(index)
        parse_index(root_path, index, tu.cursor,
                    tu.cursor.displayname, group, '', macros, include_source)
        print('    Found {} entities'.format(len(index) - count))

def convert_config(c):
    if 'masks' in c:
        return {**c, 'input': {
                    'include': [ os.path.join(c['input_directory'], x) for x in c['masks'] ],
                    'hide_tokens': c['postprocessor']['ignore'],
                    'compile_options': c['clang']['arguments']}}
    return c

if __name__ == '__main__':

    import subprocess

    parser = argparse.ArgumentParser(
        description='Parse C++ sources to generate index')
    parser.add_argument('config_path', help='path to configuration file (YML)')
    parser.add_argument('source_path', help='path to source directory')
    parser.add_argument('--output',
                        help='path where generated index will be written (JSON)')
    parser.add_argument('--libclang', help='libclang path (.dll or .so)')
    parser.add_argument(
        '--git', help='Retrieve commit hash and branch', action='store_true')

    args = parser.parse_args()

    if args.libclang:
        Config.set_library_file(args.libclang)

    clang_args = []

    config = None

    defaults = {
        'inputs': [
            {
                'include': ['**/*.hpp', 
                    '**/*.cpp', 
                    '**/*.cxx', 
                    '**/*.hxx', 
                    '**/*.h'],
                'hide_tokens': [],
                'compile_options': [],
            }
        ],
        'repository': '',
        'groups': {}, 
        'include_source': False
    }

    config = yaml.safe_load(open(args.config_path, 'r', encoding='utf-8'))
    
    config = convert_config(config)

    print(config)
    config = {**defaults, **config}

    git_tag = ''

    if args.git:
        try:
            git_tag = subprocess.check_output(
                ['git', 'describe', '--always', '--abbrev=0'], cwd=args.source_path).strip()
            git_tag = codecs.decode(git_tag)
            print('GIT:')
            print(git_tag)
        except:
            pass

    inputs = config['input']

    index = []
    for input in inputs:
        filenames = []
        for input_mask in input['include']:
            filenames += glob.glob(os.path.join(args.source_path, input_mask), recursive=True)

        print('Found', len(filenames), 'files')

        macros = input['hide_tokens']
        macros = {k: '' for k in macros}
        compile_options = input['compile_options']

        cparser.parse(index, args.source_path, filenames, compile_options, macros, config['include_source'])

    index = {'index': index, 'git_tag': git_tag, 'repository': config['repository'].replace(
        '{TAG}', git_tag), 'groups': config['groups']}
    json.dump(index, open(args.output, 'w', encoding='utf-8'), indent=4)
