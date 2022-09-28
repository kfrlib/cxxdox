import generator
import argparse
import os
import json
import re
from typing import List, Dict
from cparser import remove_padding
import collections


def generate_descriptions(s):
    if isinstance(s, str):
        s = [s]
    md = ''
    for ss in s:
        if isinstance(ss, str):
            md += ss
        else:
            if 'inlinecode' in ss:
                md += '`' + ss['inlinecode'] + '`'
            elif 'inlinemath' in ss:
                md += '$' + ss['inlinemath'] + '$'
            elif 'param' in ss:
                md += '<br/>**' + ss['param'] + '**'
            elif 'blockmath' in ss:
                md += '\n\n$$\n' + remove_padding(ss['blockmath']) + '\n$$\n\n'
            elif 'blockcode' in ss:
                md += '\n```c++\n' + \
                    remove_padding(ss['blockcode']) + '\n```\n'
            else:
                md += '(UNKNOWN ID: {})'.format(ss.items()[0])
    return md


def clang_format(code):
    import subprocess
    return subprocess.check_output(['clang-format', '-style={BasedOnStyle: llvm, ColumnLimit: 60}'], input=code, encoding='utf-8')


def generate_item(index, item, indent=0, item_header=['']):
    md = ''
    p = '    ' * indent

    if 'content' in item:
        md += p+'!!! info "' + item['name'] + '"\n'
        indent += 1
        p = '    ' * indent

    if item['name'] != item_header[0]:
        md += p+'## `' + item['name'] + '` ' + item['type'] + '\n\n'
        item_header[0] = item['name']
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
    if item['type'] not in ['enumerator']:
        md += p+'??? abstract "Source code"\n'
        md += generator.padding('```c++\n' + item['source'] +
                                '\n```\n', p=p+'    ', remove_empty_lines=False) + '\n'
        url = index['repository'].replace(
            "{FILE}", item['file']).replace("{LINE}", str(item['line']))
        md += p+'    '+'[' + url + ']('+url+')\n'
        md += '\n\n'
    if 'content' in item:
        for it in item['content']:
            md += generate_item(index, it, indent, item_header)
        md += '\n'
    return md


def generate_group(index, items: List[Dict], name):
    md = ''
    md += '# ' + name + '\n'
    md += '\n\n'

    for item in groupItems:
        md += generate_item(index, item)

    repository = index['repository'].replace(
        '{FILE}', '').replace('{LINE}', '')
    md += '\n----\n'
    md += '<small>Auto-generated from sources, Revision {0}, [{1}]({1})</small>'.format(
        index['git_tag'], re.sub(r'^([^\#]+).*', r'\1', repository))
    return md


def generate_index(index, sortedIndex: List[Dict]):
    md = '# Index\n\n'

    item_header = ''

    letter = ''
    for item in sortedIndex:
        if item['name'] != item_header:
            item_header = item['name']
            l: str = item['name'][0]
            if l != letter:
                md += '## ' + l.capitalize() + '\n\n'
                letter = l
            md += '[{} (C++ {})]({}.md#{})\n\n'.format(item['name'], item['type'],
                                                       item['group'] or 'default', item['name'] + '-' + item['type'])
    return md


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Generate Markdown documentation from C++ index')
    parser.add_argument('index_path', help='path to generated index (JSON)')
    parser.add_argument('output_path',
                        help='directory where generated documentation will be written')
    parser.add_argument(
        '--refindex', help='generate alphabetical index', action='store_true')

    args = parser.parse_args()

    index = json.load(open(args.index_path, "r", encoding="utf-8"))
    groups = generator.groupList(index['index'])

    group_names = index['groups'] or dict()

    for g in groups:
        print('Generating {}...'.format(g))
        groupItems = generator.filterIndex(index['index'], g)
        groupItems.sort(key=lambda x: x['name'])
        g = g or 'default'
        md = generate_group(index,
                            groupItems, (group_names[g] if g in group_names else g))

        wpath = os.path.join(args.output_path, g + '.md')
        print('Writing' + wpath + '...')
        open(wpath, 'w', encoding='utf-8').write(md)

    if args.refindex:
        print('Generating index...')
        sortedIndex = index['index'].copy()
        sortedIndex.sort(key=lambda x: x['name'])

        md = generate_index(index, sortedIndex)

        open(os.path.join(args.output_path, 'refindex.md'),
             'w', encoding='utf-8').write(md)
