import json
from typing import Callable
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from cxxdox_plugin.index import Index
from cxxdox_plugin.logs import log
import parsimonious.exceptions

def escape(text: str) -> str:
    if "&" in text:
        text = text.replace("&", "&amp;")
    if "<" in text:
        text = text.replace("<", "&lt;")
    if ">" in text:
        text = text.replace(">", "&gt;")
    if "\"" in text:
        text = text.replace("\"", "&quot;")
    return text

doxygen_grammar = Grammar(
    r"""
    _all                 = _newline* (_section _newline*)*
    _section             = brief / details / param / tparam / return / retval / note / see / code /
                           copybrief / remark / warning / copydoc / enum / class / struct / 
                           pre / post / exception / since / version / deprecated /
                           typedef / addtogroup / ingroup / _paragraph / anytag 
    _ws                  = ~r"[^\S\n]"
    _newline             = _ws* "\n" _ws*
    _word_text           = ~r"\S+" / ~r"\".*\""
    _tag_start           = "@" / "\\"
    _line_text           = ~r"[^\n]+"
    _paragraph_text      = ~r"([^@\\\$\n]|\n(?!\n))+"
    _paragraph           = (_paragraph_text / _inline)+
    _opt_paragraph       = ((_ws / "\n") (_paragraph_text / _inline)*)?
    
    _param_dir           = "[" ~r"in|out|in[ ,]?out|out[ ,]?in" "]"

    _inline              = ref / p / c / b / formula / md_formula / inline_formula1 / inline_formula2

    _code_content        = ~r"(?s).*?(?=@endcode|\\endcode|$)"
    _formula_content     = ~r"(?s).*?(?=@f\]|\\f\]|$)"s
    _inline_formula1_content = ~r"(?s).*?(?=@f\$|\\f\$|$)"
    _inline_formula2_content = ~r"(?s).*?(?=@\)|\\\)|$)"

    # Inlines
    b                    = _tag_start "b" _ws+ _word_text
    p                    = _tag_start "p" _ws+ _word_text
    c                    = _tag_start "c" _ws+ _word_text
    ref                  = _tag_start "ref" _ws+ _word_text
    formula              = _tag_start "f[" _formula_content _tag_start "f]"
    md_formula           = "$" ~r"(?s).*?(?=\$|$)" "$"
    inline_formula1      = _tag_start "f$" _inline_formula1_content _tag_start "f$"
    inline_formula2      = _tag_start "(" _inline_formula2_content _tag_start ")"

    # Sections
    brief                = _tag_start "brief" _opt_paragraph
    details              = _tag_start "details" _opt_paragraph
    param                = _tag_start "param" _param_dir? _ws* _word_text _opt_paragraph
    tparam               = _tag_start "tparam" _ws* _word_text _opt_paragraph
    return               = _tag_start ("returns" / "return") _opt_paragraph
    retval               = _tag_start "retval" _ws* _word_text _opt_paragraph
    note                 = _tag_start "note" _opt_paragraph
    see                  = _tag_start ("sa" / "see") _opt_paragraph
    code                 = _tag_start "code" _ws* _code_content _tag_start "endcode"
    copybrief            = _tag_start "copybrief" _ws+ _word_text
    remark               = _tag_start ("remarks" / "remark") _opt_paragraph
    warning              = _tag_start "warning" _opt_paragraph
    copydoc              = _tag_start "copydoc" _ws+ _word_text
    enum                 = _tag_start "enum" _ws+ _word_text
    class                = _tag_start "class" _ws+ _word_text
    struct               = _tag_start "struct" _ws+ _word_text
    pre                  = _tag_start "pre" _opt_paragraph
    post                 = _tag_start "post" _opt_paragraph
    exception            = _tag_start ("exceptions" / "exception" / "throws" / "throw") _ws* _word_text _opt_paragraph
    since                = _tag_start "since" _opt_paragraph
    version              = _tag_start "version" _opt_paragraph
    deprecated           = _tag_start "deprecated" _opt_paragraph
    typedef              = _tag_start "typedef" _ws+ _word_text
    addtogroup           = _tag_start ("addtogroup" / "defgroup") _ws+ _word_text _ws* _line_text* _opt_paragraph
    ingroup              = _tag_start "ingroup" _ws+ _word_text

    # Fallback
    anytag               = _tag_start ~r"\S+" _ws* _line_text*
    """)

def unwrap(list_or_str):
    if isinstance(list_or_str, list):
        if len(list_or_str) == 1:
            return unwrap(list_or_str[0])
        list_or_str = [unwrap(x) for x in list_or_str]
        list_or_str = [x for x in list_or_str if x]  # remove empty
        while len(list_or_str) > 1 and isinstance(list_or_str[0], str) and list_or_str[0].strip() == '':
            list_or_str.pop(0)
        while len(list_or_str) > 1 and isinstance(list_or_str[-1], str) and list_or_str[-1].strip() == '':
            list_or_str.pop()
        if len(list_or_str) > 1:
            if isinstance(list_or_str[0], str):
                list_or_str[0] = list_or_str[0].lstrip()
            if isinstance(list_or_str[-1], str):
                list_or_str[-1] = list_or_str[-1].rstrip()
        return list_or_str
    if hasattr(list_or_str, 'text'):
        return list_or_str.text.strip()
    return list_or_str

class DoxygenVisitor(NodeVisitor):
    def visit_brief(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'brief': unwrap(paragraph)}
    def visit_details(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'details': unwrap(paragraph)}
    def visit_param(self, node, visited_children):
        _, _, param_dir, _, param_name, paragraph = visited_children
        return {'param': {'name': param_name, 'dir': param_dir, 'desc': unwrap(paragraph)}}
    def visit_copybrief(self, node, visited_children):
        _, _, _, symbol_name = visited_children
        return {'copybrief': symbol_name}
    def visit_copydoc(self, node, visited_children):
        _, _, _, symbol_name = visited_children
        return {'copydoc': symbol_name}
    def visit_tparam(self, node, visited_children):
        _, _, _, param_name, paragraph = visited_children
        return {'tparam': {'name': param_name, 'desc': unwrap(paragraph)}}
    def visit_return(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'return': unwrap(paragraph)}
    def visit_retval(self, node, visited_children):
        _, _, _, retval_name, paragraph = visited_children
        return {'retval': {'name': retval_name, 'desc': unwrap(paragraph)}}
    def visit_since(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'since': unwrap(paragraph)}
    def visit_version(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'version': unwrap(paragraph)}
    def visit_deprecated(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'deprecated': unwrap(paragraph)}
    def visit_pre(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'pre': unwrap(paragraph)}
    def visit_post(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'post': unwrap(paragraph)}
    def visit__word_text(self, node, visited_children):
        return node.text.strip().strip('"')
    def visit_exception(self, node, visited_children):
        _, _, _, exc_name, paragraph = visited_children
        return {'exception': {'name': exc_name, 'desc': unwrap(paragraph)}}
    def visit_enum(self, node, visited_children):
        _, _, _, symbol_name = visited_children
        return {'enum': symbol_name}
    def visit_class(self, node, visited_children):
        _, _, _, symbol_name = visited_children
        return {'class': symbol_name}
    def visit_struct(self, node, visited_children):
        _, _, _, symbol_name = visited_children
        return {'struct': symbol_name}
    def visit_typedef(self, node, visited_children):
        _, _, _, symbol_name = visited_children
        return {'typedef': symbol_name}
    def visit_inline_formula1(self, node, visited_children):
        _, _, formula_content, _, _ = visited_children
        return {'inline_formula': formula_content.strip()}
    def visit_inline_formula2(self, node, visited_children):
        _, _, formula_content, _, _ = visited_children
        return {'inline_formula': formula_content.strip()}
    def visit_formula(self, node, visited_children):
        _, _, formula_content, _, _ = visited_children
        return {'formula': formula_content.strip()}
    def visit_md_formula(self, node, visited_children):
        _, formula_content, _ = visited_children
        return {'inline_formula': formula_content.strip()}
    def visit_note(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'note': unwrap(paragraph)}
    def visit_warning(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'warning': unwrap(paragraph)}
    def visit_see(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'see': unwrap(paragraph)}
    def visit_remark(self, node, visited_children):
        _, _, paragraph = visited_children
        return {'remark': unwrap(paragraph)}
    def visit_code(self, node, visited_children):
        _, _, _, code_content, _, _ = visited_children
        return {'code': code_content.strip()}
    def visit__paragraph(self, node, visited_children):
        f = unwrap(visited_children)
        return f
    def visit__paragraph_text(self, node, visited_children):
        return node
    def visit__param_dir(self, node, visited_children):
        return visited_children[1]
    def visit_p(self, node, visited_children):
        _, _, _, word = visited_children
        return {'p': word}
    def visit_b(self, node, visited_children):
        _, _, _, word = visited_children
        return {'b': word}
    def visit_c(self, node, visited_children):
        _, _, _, word = visited_children
        return {'c': word}
    def visit_ref(self, node, visited_children):
        _, _, _, word = visited_children
        return {'ref': word}
    def visit__section(self, node, visited_children):
        return unwrap(visited_children[0])
    def visit_addtogroup(self, node, visited_children):
        _, _, _, name, _, title, paragraph = visited_children
        return {'addtogroup': {'name': name, 'title': title, 'desc': unwrap(paragraph)}}
    def visit_ingroup(self, node, visited_children):
        _, _, _, name = visited_children
        return {'ingroup': name}
    def visit_anytag(self, node, visited_children):
        _, tagname, _, line_text = visited_children
        # tagname may already be unwrapped to a str by generic_visit
        tagname_str = tagname.text.strip() if hasattr(tagname, 'text') else str(tagname).strip()
        log.warning(f"Unsupported Doxygen tag '@{tagname_str}' in comment: {node.text.strip()!r}")
        return f"{node.text.strip()}"
    def generic_visit(self, node, visited_children):
        return unwrap(visited_children or node)

def parse_doxygen_comment(comment: str) -> list:
    try:
        nodes = doxygen_grammar.parse(comment)

        visitor = DoxygenVisitor()
        result = visitor.visit(nodes)
        result = unwrap(result)
        if not isinstance(result, list):
            result = [result]
        return result
    except parsimonious.exceptions.IncompleteParseError as e:
        log.error(f"Error parsing doxygen comment: {e}")
        return [comment]

def wrap_p(s: str) -> str:
    s = s.strip()
    if not s.startswith('<p>') or not s.endswith('</p>'):
        s = f'<p>{s}</p>'
    return s

def doxygen_to_html(block: list|str, 
                    index: Index,
                    context: str,
                    link_resolver: Callable[[str], str]
                    ) -> str:
    if isinstance(block, str):
        return f'{escape(block)}'
    if isinstance(block, dict):
        block = [block]
    html_parts: list[str] = []
    table = None
    for item in block:
        if isinstance(item, str):
            if table:
                html_parts.append('</table>')
            table = None
            html_parts.append(f'{escape(item)}')
        elif isinstance(item, dict):
            if 'param' in item:
                if table != 'param':
                    if table:
                        html_parts.append('</table>')
                        table = None
                    html_parts.append(f'<table class="cxx-table"><caption>Parameters</caption>')
                param = item['param']

                html_parts.append(f'<tr><td>{escape(param["name"])}</td><td>{doxygen_to_html(param["desc"], index, context, link_resolver)}</td></tr>')
                table = 'param'
            elif 'tparam' in item:
                if table != 'tparam':
                    if table:
                        html_parts.append('</table>')
                        table = None
                    html_parts.append(f'<table class="cxx-table"><caption>Template parameters</caption>')
                tparam = item['tparam']

                html_parts.append(f'<tr><td>{escape(tparam["name"])}</td><td>{doxygen_to_html(tparam["desc"], index, context, link_resolver)}</td></tr>')
                table = 'tparam'
            elif 'return' in item:
                if table != 'return':
                    if table:
                        html_parts.append('</table>')
                        table = None
                    html_parts.append(f'<table class="cxx-table"><caption>Returns</caption>')
                html_parts.append(f'<tr><td></td><td>{doxygen_to_html(item["return"], index, context, link_resolver)}</td></tr>')
                table = 'return'
            elif 'retval' in item:
                if table != 'return':
                    if table:
                        html_parts.append('</table>')
                        table = None
                    html_parts.append(f'<table class="cxx-table"><caption>Returns</caption>')
                retval = item['retval']
                html_parts.append(f'<tr><td>{escape(retval["name"])}</td><td>{doxygen_to_html(retval["desc"], index, context, link_resolver)}</td></tr>')
                table = 'return'
            elif 'pre' in item:
                if table != 'pre':
                    if table:
                        html_parts.append('</table>')
                        table = None
                    html_parts.append(f'<table class="cxx-table"><caption>Preconditions</caption>')
                html_parts.append(f'<tr><td></td><td>{doxygen_to_html(item["pre"], index, context, link_resolver)}</td></tr>')
                table = 'pre'
            elif 'post' in item:
                if table != 'post':
                    if table:
                        html_parts.append('</table>')
                        table = None
                    html_parts.append(f'<table class="cxx-table"><caption>Postconditions</caption>')
                html_parts.append(f'<tr><td></td><td>{doxygen_to_html(item["post"], index, context, link_resolver)}</td></tr>')
                table = 'post'
            elif 'exception' in item:
                if table != 'exception':
                    if table:
                        html_parts.append('</table>')
                        table = None
                    html_parts.append(f'<table class="cxx-table"><caption>Exceptions</caption>')
                exception = item['exception']
                html_parts.append(f'<tr><td>{escape(exception["name"])}</td><td>{doxygen_to_html(exception["desc"], index, context, link_resolver)}</td></tr>')
                table = 'exception'
            else:
                if table:
                    html_parts.append('</table>')
                    table = None
                if 'b' in item:
                    html_parts.append(f' <strong>{escape(item["b"])}</strong> ')
                elif 'p' in item:
                    html_parts.append(f' <em>{escape(item["p"])}</em> ')
                elif 'c' in item:
                    html_parts.append(f' <code>{escape(item["c"])}</code> ')
                elif 'ref' in item:
                    sym_id = index.lookup_by_scoped_name(context, item['ref'])
                    if sym_id is not None:
                        permalink = index.symbol_permalink(sym_id)
                        permalink = link_resolver(permalink) if permalink is not None else '#'
                        html_parts.append(f' <a href="{permalink}"><code>{escape(item["ref"])}</code></a> ')
                    else:
                        log.warning(f"Doxygen reference not found: {item['ref']} in context {context}")
                        html_parts.append(f' <code class="cxx-not-found">{escape(item["ref"])}</code> ')
                elif 'copybrief' in item or 'copydoc' in item:
                    # @copybrief copies the brief paragraph from another symbol.
                    # @copydoc copies the entire documentation block (brief + details
                    # and all sections) from another symbol. The copied content is
                    # rendered inline, matching Doxygen behavior.
                    ref_name = item.get('copybrief') or item.get('copydoc')
                    sym_id = index.lookup_by_scoped_name(context, ref_name)
                    if sym_id is not None:
                        ref_sym = index[sym_id]
                        # Resolve refs inside the copied content using the referenced
                        # symbol's own scope as context.
                        ref_context = ref_sym.get('full_name', '') or context
                        if 'copybrief' in item:
                            copied = ref_sym.get('brief', '')
                            if copied:
                                html_parts.append(doxygen_to_html(copied, index, ref_context, link_resolver))
                            else:
                                log.warning(f"@copybrief target has no brief: {ref_name} in context {context}")
                        else:  # copydoc
                            copied_parts: list[str] = []
                            if ref_sym.get('brief'):
                                copied_parts.append(doxygen_to_html(ref_sym['brief'], index, ref_context, link_resolver))
                            if ref_sym.get('details'):
                                copied_parts.append(doxygen_to_html(ref_sym['details'], index, ref_context, link_resolver))
                            if copied_parts:
                                html_parts.append(' '.join(copied_parts))
                            else:
                                log.warning(f"@copydoc target has no documentation: {ref_name} in context {context}")
                    else:
                        log.warning(f"Doxygen reference not found: {ref_name} in context {context}")
                        html_parts.append(f' <code class="cxx-not-found">{escape(ref_name)}</code> ')
                elif 'enum' in item or 'class' in item or 'struct' in item or 'typedef' in item:
                    # Reference-style tags (@enum, @class, @struct, @typedef) that name a
                    # symbol. Render the name as a link (or plain code) instead of dropping it.
                    ref_name = item.get('enum') or item.get('class') or item.get('struct') or item.get('typedef')
                    sym_id = index.lookup_by_scoped_name(context, ref_name)
                    if sym_id is not None:
                        permalink = index.symbol_permalink(sym_id)
                        permalink = link_resolver(permalink) if permalink is not None else '#'
                        html_parts.append(f' <a href="{permalink}"><code>{escape(ref_name)}</code></a> ')
                    else:
                        log.warning(f"Doxygen reference not found: {ref_name} in context {context}")
                        html_parts.append(f' <code class="cxx-not-found">{escape(ref_name)}</code> ')
                elif 'inline_formula' in item:
                    html_parts.append(f' <span class="arithmatex">\\({escape(item["inline_formula"])}\\)</span> ')
                elif 'formula' in item:
                    html_parts.append(f'<div class="arithmatex">\\\\[\n{escape(item["formula"])}\n\\\\]</div>')
                elif 'note' in item:
                    html_parts.append(f'<div class="admonition note"><p class="admonition-title">Note</p> {wrap_p(doxygen_to_html(item["note"], index, context, link_resolver))}</div>')
                elif 'see' in item:
                    html_parts.append(f'<div class="cxx-see"><strong>See also:</strong> {doxygen_to_html(item["see"], index, context, link_resolver)}</div>')
                elif 'remark' in item:
                    html_parts.append(f'<div class="admonition note"><p class="admonition-title">Remark</p> {wrap_p(doxygen_to_html(item["remark"], index, context, link_resolver))}</div>')
                elif 'warning' in item:
                    html_parts.append(f'<div class="admonition warning"><p class="admonition-title">Warning</p> {wrap_p(doxygen_to_html(item["warning"], index, context, link_resolver))}</div>')
                elif 'deprecated' in item:
                    html_parts.append(f'<div class="admonition danger"><p class="admonition-title">Deprecated</p> {wrap_p(doxygen_to_html(item["deprecated"], index, context, link_resolver))}</div>')
                elif 'since' in item:
                    html_parts.append(f'<div class="admonition tip"><p class="admonition-title">Since</p> {wrap_p(doxygen_to_html(item["since"], index, context, link_resolver))}</div>')
                elif 'version' in item:
                    html_parts.append(f'<div class="admonition tip"><p class="admonition-title">Version</p> {wrap_p(doxygen_to_html(item["version"], index, context, link_resolver))}</div>')
                elif 'example' in item:
                    html_parts.append(f'<div class="admonition example"><p class="admonition-title">Example</p> {wrap_p(doxygen_to_html(item["example"], index, context, link_resolver))}</div>')
                elif 'details' in item:
                    html_parts.append(f'<div class="cxx-details">{wrap_p(doxygen_to_html(item["details"], index, context, link_resolver))}</div>')
                elif 'code' in item:
                    html_parts.append(f'<pre><code class="language-cpp">{escape(item["code"])}</code></pre>')
                elif 'ingroup' in item or 'addtogroup' in item:
                    pass
                else:
                    unhandled_key = next(iter(item.keys())) if isinstance(item, dict) and item else None
                    log.warning(f"Unhandled Doxygen tag '{unhandled_key}' in doxygen_to_html (context: {context}): {item!r}")
                    html_parts.append(escape(str(item)))
    if table:
        html_parts.append('</table>')
    return ''.join(html_parts)

if __name__ == "__main__":

    data = parse_doxygen_comment(
r"""@brief This is a demo library to showcase documentation features.
""")

    print(json.dumps(data, indent=4))
