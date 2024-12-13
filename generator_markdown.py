from io import TextIOWrapper

import yaml
import generator
import argparse
import os
import json
import re
from typing import List, Dict
from common import remove_padding
import collections
from markdown.extensions.toc import slugify

def markdown_safe(s):
    return s.replace('>', r'\>')

labels = {
    "exceptions":"Exceptions",
    "details":"Details",
    "note":"Note",
    "threadsafety":"Thread safety",
}

def generate_descriptions(s):
    if isinstance(s, str):
        s = [s]
    md = ''
    for ss in s:
        if isinstance(ss, str):
            md += markdown_safe(ss)
        else:
            key = next(iter(ss))
            if key in ['concept', 'class', 'struct', 'function', 'typedef', 'enum']:
                pass # Skip
            elif key == 'inlinecode':
                md += ' `' + ss['inlinecode'] + '` '
            elif key == 'inlinemath':
                md += ' $' + ss['inlinemath'] + '$ '
            elif key == 'param':
                md += '<br/>\n**Param** `' + markdown_safe(ss['param']) + '` '
            elif key == 'return':
                md += '<br/>\n**Returns** '
            elif key == 'see':
                md += '<br/>\n**See** '
            elif key == 'tparam':
                md += '<br/>\n**Template param** `' + markdown_safe(ss['tparam']) + '` '
            elif key in ['exceptions', 'details', 'note', 'threadsafety']:
                md += '<br/>\n**' + markdown_safe(labels[key]) + '** '
            elif key == 'blockmath':
                md += '\n\n$$\n' + remove_padding(markdown_safe(ss['blockmath'])) + '\n$$\n\n'
            elif key == 'blockcode':
                md += '\n```c++\n' + \
                    remove_padding(markdown_safe(ss['blockcode'])) + '\n```\n'
            else:
                md += '(UNKNOWN ID: {})'.format(list(ss.items())[0])
    return md


def clang_format(code):
    import subprocess
    return subprocess.check_output(['clang-format', '-style={BasedOnStyle: llvm, ColumnLimit: 60}'], input=code, encoding='utf-8')

def clean_name(name:str, index):
    if 'namespace' in index:
        name = name.removeprefix(index['namespace'])
    if re.match(r'\(unnamed.*\)', name):
        name = '(unnamed)'
    if re.match(r'\(anonymous.*\)', name):
        name = '(anonymous)'
    return name

def make_title(item, index, long = True):
    name = clean_name(item['name'], index)
    qualifiedname = clean_name(item['qualifiedname'], index)
    if long and name != qualifiedname:
        return '`' + name + '` ' + item['type'] + ' (`' + qualifiedname + '`)'
    else:
        return '`' + qualifiedname + '` ' + item['type']

def generate_item(index, item, indent=0, item_header=[''], subitem=False):
    md = ''
    p = '    ' * indent

    if not subitem:
        md += '---\n'

    title = make_title(item, index)

    if title != item_header[0]:
        md += p + ('### ' if subitem else '## ') + title + '\n\n'
        item_header[0] = title
    if item['type'] not in ['enumerator']:
        md += generator.padding('```c++\n' + clang_format(item['definition']) +
                            '\n```\n\n', p=p, remove_empty_lines=False) + '\n'

    description = item['description']
    if isinstance(description, collections.abc.Mapping) and 'copy' in description:
        for it in index['index']:
            if it['qualifiedname'] == description['copy']:
                description = it['description']
                break

    description = generate_descriptions(description)
    md += generator.padding(description, p=p, remove_empty_lines=False) + '\n\n'
    if item['type'] not in ['enumerator'] and item['source'] != "":
        md += p+'??? abstract "Source code"\n'
        md += generator.padding('```c++\n' + item['source'] +
                                '\n```\n', p=p+'    ', remove_empty_lines=False) + '\n'
        url = index['repository'].replace(
            "{FILE}", item['file']).replace("{LINE}", str(item['line']))
        md += p+'    '+'[' + url + ']('+url+')\n'
        md += '\n\n'
    if 'content' in item:
        for it in item['content']:
            md += generate_item(index, it, indent, item_header, True)
        md += '\n'
    return md

def header(index, title: str):
    md = ''
    md += '# ' + title + '\n'
    md += '\n\n'
    return md

def footer(index: Dict):
    repository = index['repository'].replace(
        '{FILE}', '').replace('{LINE}', '')
    md = '\n----\n'
    md += '<small>Auto-generated from sources, Revision {0}, [{1}]({1})</small>'.format(
        index['git_tag'], re.sub(r'^([^\#]+).*', r'\1', repository))
    return md

def generate_group(index: Dict, groupItems: List[Dict], title: str):
    md = header(index, title)

    for item in groupItems:
        md += generate_item(index, item)

    md += footer(index)
    return md

def group_for(item, index):
    return item['file'] if index['groups'] == 'auto' else (item['group'] or 'default')

def path_for(group):
    return f"auto/{group}.md"

def traverse(target_index, source_index):
    for item in source_index:
        target_index.append(item)
        if 'content' in item:
            traverse(target_index, item['content'])

def generate_index(index, sortedIndex: List[Dict]):
    md=''
    letter=''
    item_header=''
    for item in sortedIndex:
        if item['name'] != item_header:
            item_header = item['name']
            l: str = item['name'][0].capitalize()
            if l != letter:
                md += '## ' + l + '\n\n'
                letter = l
            md += '[{}]({}.md#{})\n\n'.format(make_title(item, index),
                                                     group_for(item, index), slugify(make_title(item, index), '-'))
    return md

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Generate Markdown documentation from C++ index')
    parser.add_argument('index_path', help='path to generated index (JSON)')
    parser.add_argument('output_path',
                        help='directory where generated documentation will be written')
    parser.add_argument(
        '--refindex', help='generate alphabetical index', action='store_true')
    parser.add_argument('--mkdocs', help='path to mkdocs config')

    args = parser.parse_args()

    index = json.load(open(args.index_path, "r", encoding="utf-8"))

    files: Dict[str,TextIOWrapper] = {}

    toc: Dict = {}

    auto_toc = index['groups'] == 'auto'
    
    mkdocs_config={}
    if auto_toc:
        mkdocs_config = yaml.unsafe_load(open(args.mkdocs, 'r', encoding='utf-8'))

    for item in index['index']:
        group = group_for(item, index)
        gpath = path_for(group)
        print(f'Generating markdown for {item["name"]} in {group}...')
        if not group in files:
            wpath = os.path.join(args.output_path, gpath)
            os.makedirs(os.path.dirname(wpath), exist_ok=True)
            files[group] = open(wpath, 'w', encoding='utf-8')
            title = 'File `' + group + '`' if auto_toc else group
            files[group].write( header(index, title) )
            spath = group.split('/')
            if auto_toc:
                current = toc
                for key in spath[:-1]:
                    current = current.setdefault(key, {})
                current[spath[-1]] = gpath

        files[group].write(generate_item(index, item))

    if auto_toc:        
        mkdocs_nav = mkdocs_config["nav"]
        print(mkdocs_nav)
        for v in mkdocs_nav:
            if 'Reference' in v:
                v['Reference'] = toc

        print(mkdocs_nav)
        mkdocs_config["nav"] = mkdocs_nav
        yaml.dump(mkdocs_config, open(args.mkdocs, "w", encoding='utf-8'), sort_keys=False)

    for k, file in files.items():
        file.write(footer(index))

    # if index['groups'] == 'auto':
    #     pass
    # else:
    #     groups = generator.groupList(index['index'])

    #     group_names = index['groups'] or dict()

    #     for g in groups:
    #         print('Generating {}...'.format(g))
    #         groupItems = generator.filterIndex(index['index'], g)
    #         groupItems.sort(key=lambda x: x['name'])
    #         g = g or 'default'
    #         md = generate_group(index,
    #                             groupItems, (group_names[g] if g in group_names else g))
            
    #         if md.startswith('---\n'):
    #             md = md[4:]

    #         wpath = os.path.join(args.output_path, g + '.md')
    #         print('Writing' + wpath + '...')
    #         open(wpath, 'w', encoding='utf-8').write(md)

    if args.refindex:
        print('Generating index...')
        sortedIndex=[]
        traverse(sortedIndex, index['index'])
        sortedIndex.sort(key=lambda x: (not x['name'][0].isalpha(), x['name'].lower()))

        md = '# Index\n\n'
        md += generate_index(index, sortedIndex)

        open(os.path.join(args.output_path, 'auto/refindex.md'),
             'w', encoding='utf-8').write(md)
