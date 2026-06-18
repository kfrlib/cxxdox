# CxxDox

**mkdocs-cxxdox** is an [MkDocs] plugin that generates C++ API documentation directly from source using **libclang**. It parses headers, extracts Doxygen-style comments, and renders a browsable reference — namespaces, classes, functions, variables, typedefs, enums, concepts, macros — into your MkDocs site.

> **Status:** alpha. Pre-built wheels are distributed via [GitHub Releases](https://github.com/kfrlib/cxxdox/releases).

## Installation

mkdocs-cxxdox ships as a platform-specific wheel that bundles the matching `libclang` binary — no system LLVM/Clang install is required.

```bash
pip install https://github.com/kfrlib/cxxdox/releases/download/v0.1.3/mkdocs_cxxdox-0.1.3-win_amd64.whl
```

For the best experience, pair it with the [Material](https://squidfunk.github.io/mkdocs-material/) theme:

```bash
pip install mkdocs_cxxdox-0.1.3-win_amd64.whl "mkdocs-material>=9.1.15"
```

Requirements: Python ≥ 3.9, `mkdocs` ≥ 1.5.

## Quick start

Add the plugin to your `mkdocs.yml`:

```yaml
plugins:
  - search
  - cxxdox:
      title: My Library Reference
      input:
        - include:
            - include/mylib.hpp
          compile_options:
            - -std=c++20
            - -Iinclude
```

Then build the site:

```bash
mkdocs serve   # or: mkdocs build
```

The generated reference appears under the configured `path_prefix` (default `cxxdox/`).

## Demo

This site is itself the demo. See the [Demo Library Reference](auto/index.md) for the generated documentation of the demo C++ library (`demo/library.hpp`, `demo/library.cpp`).

## Symbol reference syntax

CxxDox extends Markdown with `[[...]]` references that resolve to symbols in the generated reference. The general form is:

```
[[<symbol>[:<flag>[:<flag>...]]]]
```

Where `<flag>` is one of: `type`, `file`, `brief`. Wrap a symbol in backticks (`` ` ` ``) when its spelling contains characters that would otherwise be parsed as Markdown — e.g. parentheses, commas, or template parameters.

### Examples

> The `[[...]]` syntax below is a CxxDox extension and only renders as links in the generated MkDocs site — not on GitHub. The middle column shows the raw syntax to write in your Markdown, the right column shows what it resolves to in the built docs.

| Description | Syntax | Result |
|---|---|---|
| Simple reference | `[[ns::Color]]` | [[ns::Color]] |
| Add the symbol's type | `[[ns::Color:type]]` | [[ns::Color:type]] |
| Type and source file | `[[ns::Color:type:file]]` | [[ns::Color:type:file]] |
| Type, brief, and file | `[[ns::Color:type:file:brief]]` | [[ns::Color:type:file:brief]] |
| Function reference | `[[ns::to_name(Color):type:file:brief]]` | [[ns::to_name(Color):type:file:brief]] |
| USR-based reference | `` [[`c:@N@ns@Pair`:type:brief]] `` | [[`c:@N@ns@Pair`:type:brief]] |
| Reference by name | `[[Example]]` | [[Example]] |
| Reference by signature (backticked) | `` [[`fn1(std::byte, Color)`]] `` | [[`fn1(std::byte, Color)`]] |
| Reference by name only | `[[fn1]]` | [[fn1]] |
| Template class | `[[filter<T>]]` | [[filter<T>]] |
| Template method | `[[filter<T>::apply]]` | [[filter<T>::apply]] |
| Template method with signature | `` [[`filter<T>::apply(T *, size_t)`]] `` | [[`filter<T>::apply(T *, size_t)`]] |
| Free function | `[[global_function]]` | [[global_function]] |
| Specific overload (brief) | `` [[`abs(double)`:brief]] `` | [[`abs(double)`:brief]] |
| Specific overload (brief) | `` [[`abs(int)`:brief]] `` | [[`abs(int)`:brief]] |

## License

Apache-2.0 WITH LLVM-exception. See [LICENSE.TXT](https://github.com/kfrlib/cxxdox/blob/main/LICENSE.TXT). The vendored `cindex.py` and bundled `libclang` binary are part of the LLVM Project, distributed under the same license.

[MkDocs]: https://www.mkdocs.org/
