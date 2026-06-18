# mkdocs-cxxdox

An [MkDocs] plugin that generates C++ API documentation directly from source using **libclang**. It parses headers with libclang, extracts Doxygen-style comments, and renders a browsable reference (namespaces, classes, functions, variables, typedefs, enums, concepts, macros, …) into your MkDocs site.

> **Status:** alpha. Pre-built wheels are distributed via GitHub Releases — not on PyPI.

---

## Installation

mkdocs-cxxdox ships as a platform-specific wheel that bundles the matching `libclang` binary, so there is nothing else to install.

### 1. Pick a wheel for your platform

Download the latest wheel from the [GitHub Releases page](https://github.com/kfrlib/cxxdox/releases):

| Platform            | Wheel tag                |
|---------------------|--------------------------|
| Windows x64         | `mkdocs_cxxdox-*-win_amd64.whl`   |
| Linux x64           | `mkdocs_cxxdox-*-manylinux_x86_64.whl` |

### 2. Install with pip

```bash
pip install https://github.com/kfrlib/cxxdox/releases/download/v0.1.3/mkdocs_cxxdox-0.1.3-win_amd64.whl
```

Replace the URL/version with the one matching your platform from the release assets. You can also download the file and install locally:

```bash
pip install mkdocs_cxxdox-0.1.3-cp312-none-win_amd64.whl
```

### 3. (Recommended) Install the Material theme

The plugin works with any MkDocs theme, but it is designed for and tested with [mkdocs-material](https://squidfunk.github.io/mkdocs-material/):

```bash
pip install "mkdocs-cxxdox[material]"
# or, if installing from a wheel file:
pip install mkdocs_cxxdox-0.1.3-win_amd64.whl "mkdocs-material>=9.1.15"
```

### Requirements

- Python ≥ 3.9
- `mkdocs` ≥ 1.5 (installed automatically)
- `parsimonious` (installed automatically)
- No system LLVM/Clang installation required — `libclang` is bundled inside the wheel.

---

## Quick start

1. Add the plugin to your `mkdocs.yml`:

```yaml
plugins:
  - search
  - cxxdox:
      title: My Library Reference
      input:
        - include:
            - include/mylib.hpp
          exclude: []
          compile_options:
            - -std=c++20
            - -Iinclude
```

2. Point `include` at the header(s) you want documented (paths are relative to `mkdocs.yml`).

3. Build the site:

```bash
mkdocs serve
# or
mkdocs build
```

The generated reference appears under the configured `path_prefix` (default `cxxdox/`).

---

## Configuration reference

All options live under the `cxxdox:` plugin key in `mkdocs.yml`.

### Top-level options

| Option            | Type       | Default                  | Description                                                                 |
|-------------------|------------|--------------------------|-----------------------------------------------------------------------------|
| `title`           | `str`      | `"CxxDox Documentation"`  | Title shown on the generated index pages.                                  |
| `input`           | list       | **required**              | List of input groups (see below). Each group is a `SubConfig`.             |
| `path_prefix`     | `str`      | `"cxxdox/"`               | Directory under `docs/` where generated pages are placed. Use `auto/` to let the plugin derive it. |
| `symbol_prefixes` | list[str]  | `[]`                      | Only emit symbols whose qualified name starts with one of these prefixes (e.g. `ns`, `ns::inl`). |
| `root`            | `dir`      | `.`                       | Root directory used to resolve relative `include`/`exclude` paths.        |

### Input group options (`input[i]`)

Each entry in `input` is a sub-config with:

| Option              | Type       | Default | Description                                                                 |
|---------------------|------------|---------|-----------------------------------------------------------------------------|
| `include`           | list[str]  | —       | Glob patterns of files to parse (relative to `root`). **Required.**         |
| `exclude`           | list[str]  | `[]`    | Glob patterns of files to skip.                                             |
| `exclude_symbols`   | list[str]  | `[]`    | Glob patterns of symbol spellings to omit from the docs (e.g. `'*excluded_function()*'`). |
| `compile_options`   | list[str]  | `[]`    | Extra clang arguments (e.g. `-std=c++17`, `-Iinclude`, `-DMACRO=1`).        |
| `hide_tokens`       | list[str]  | `[]`    | Preprocessor tokens to hide from rendered source (e.g. `ALWAYS_INLINE`).   |

### Full example

```yaml
plugins:
  - search
  - cxxdox:
      title: Demo library Reference
      path_prefix: auto/
      symbol_prefixes:
        - ns
        - ns::inl
      input:
        - include:
            - library.hpp
          exclude: []
          exclude_symbols:
            - '*excluded_function()*'
          hide_tokens:
            - ALWAYS_INLINE
          compile_options:
            - -std=c++17
            - -DMACRO=1
```

### Recommended Markdown extensions

The generated pages use admonitions, code fences, and KaTeX math. A working set is:

```yaml
markdown_extensions:
  - attr_list
  - admonition
  - footnotes
  - meta
  - md_in_html
  - toc:
      permalink: true
  - pymdownx.arithmatex:
      generic: true
  - pymdownx.inlinehilite
  - pymdownx.superfences
  - pymdownx.highlight
  - pymdownx.details
  - pymdownx.tabbed:
      alternate_style: true
```

---

## Demo

A complete, runnable example lives in the [`demo/`](demo/) directory, including `demo/library.hpp`, `demo/library.cpp`, and `demo/mkdocs.yml`. To try it:

```bash
cd demo
mkdocs serve
```

---

## How wheels are built

Pre-built wheels are produced by the CI workflow in [`.github/workflows/build.yml`](.github/workflows/build.yml). For each platform it:

1. Downloads the official LLVM release archive from the [`llvm/llvm-project`](https://github.com/llvm/llvm-project/releases) GitHub releases (e.g. `LLVM-21.1.6-Linux-X64.tar.xz`, `clang+llvm-21.1.6-x86_64-pc-windows-msvc.tar.xz`).
2. Extracts only the `libclang` binary and stages it into `cxxdox_plugin/libclang21/` with the platform-correct name (`libclang.dll` / `libclang.so`).
3. Builds a platform-specific wheel with `setuptools`/`build` and validates it with `twine`.
4. Uploads the wheel as a build artifact and, on tagged releases, attaches it to the GitHub Release.

The bundled libclang version is controlled by a single `LLVM_VERSION` variable at the top of the workflow — change it in one place to bump every platform's binary. The `libclang.dll`/`.so`/`.dylib` binaries are **not** committed to git; they are pulled from the official LLVM release at build time.

---

## License

Apache-2.0 WITH LLVM-exception (see [LICENSE.TXT](LICENSE.TXT)). The vendored `cindex.py` and bundled `libclang` binary are part of the LLVM Project, distributed under the same license.

[MkDocs]: https://www.mkdocs.org/
