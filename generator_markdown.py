import generator
import argparse
import os
import json
import re
from typing import List, Dict
from common import remove_padding
import collections

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
                md += '`' + ss['inlinecode'] + '`'
            elif key == 'inlinemath':
                md += '$' + ss['inlinemath'] + '$'
            elif key == 'param':
                md += '<br/>Param **' + markdown_safe(ss['param']) + '** '
            elif key == 'return':
                md += '<br/>**Returns** '
            elif key == 'see':
                md += '<br/>**See** '
            elif key == 'tparam':
                md += '<br/>**' + markdown_safe(ss['tparam']) + '** '
            elif key in ['exceptions', 'details', 'note', 'threadsafety']:
                md += '<br/>**' + markdown_safe(labels[key]) + '** '
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


def generate_item(index, item, indent=0, item_header=[''], subitem=False):
    md = ''
    p = '    ' * indent

    if not subitem:
        md += '---\n'

    name = item['name']
    if re.match(r'\(unnamed.*\)', name):
        name = '(unnamed)'
    if re.match(r'\(anonymous.*\)', name):
        name = '(anonymous)'

    if name != item_header[0]:
        hdr = '### `' if subitem else '## `'
        md += p + hdr + name + '` ' + item['type'] + '\n\n'
        item_header[0] = name
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
        
        if md.startswith('---\n'):
            md = md[4:]

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
