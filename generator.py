#!/usr/bin/env python

import re
from typing import List, Dict

def padding(str, p='    ', remove_empty_lines=True):
    """
        normalize newlines
        remove leading and trailing spaces
        collapse spaces
        collapse newlines
        pad lines
    """
    str = re.sub(r'[ \t]+\n', '\n', str)
    if remove_empty_lines:
        str = str.replace('\n\n', '\n')
        str = str.replace('\n\n', '\n')
    str = p + str.replace('\n', '\n' + p)
    return str


def filterIndex(index: List[Dict], group: str):
    filtered = []

    for item in index:
        if item['group'] == group:
            filtered.append(item)

    return filtered


def groupList(index: List[Dict]):
    groups = []

    for item in index:
        groups.append(item['group'])

    return list(set(groups))
