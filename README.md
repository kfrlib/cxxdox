# mkdocs-cxxdox

An [MkDocs] plugin that generates C++ API documentation directly from source using **libclang**. It parses headers with libclang, extracts Doxygen-style comments, and renders a browsable reference (namespaces, classes, functions, variables, typedefs, enums, concepts, macros, …) into your MkDocs site.

Features include:

- Cross-linked symbols with overload- and namespace-aware Doxygen references.
- Generated pages and navigation organized by configurable source-file groups.
- C++ source rendering with semantic syntax highlighting for types, functions, namespaces, macros, literals, and preprocessor directives.
- Optional links from declarations to the corresponding line in a Git web interface.
- Support for inline namespaces and display-only default-namespace shortening.

> **Status:** alpha. Pre-built wheels are distributed via GitHub Releases — not on PyPI.

---

## Installation

mkdocs-cxxdox ships as a platform-specific wheel that bundles the matching `libclang` binary, so there is nothing else to install.

### 1. Pick a wheel for your platform

Download the latest wheel from the [GitHub Releases page](https://github.com/kfrlib/cxxdox/releases):

| Platform    | Wheel tag                                       |
|-------------|-------------------------------------------------|
| Windows x64 | `mkdocs_cxxdox-*-py3-none-win_amd64.whl`        |
| Linux x64   | `mkdocs_cxxdox-*-py3-none-manylinux_x86_64.whl` |

### 2. Install with pip

```bash
pip install https://github.com/kfrlib/cxxdox/releases/download/v0.2.0/mkdocs_cxxdox-0.2.0-py3-none-win_amd64.whl
```

Replace the URL/version with the one matching your platform from the release assets. You can also download the file and install locally:

```bash
pip install mkdocs_cxxdox-0.2.0-py3-none-win_amd64.whl
```

### 3. (Recommended) Install the Material theme

The plugin works with any MkDocs theme, but it is designed for and tested with [mkdocs-material](https://squidfunk.github.io/mkdocs-material/):

```bash
pip install "mkdocs-cxxdox[material]"
# or, if installing from a wheel file:
pip install mkdocs_cxxdox-0.2.0-py3-none-win_amd64.whl "mkdocs-material>=9.1.15"
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

| Option            | Type      | Default                  | Description                                                                                        |
|-------------------|-----------|--------------------------|----------------------------------------------------------------------------------------------------|
| `title`           | `str`     | `"CxxDox Documentation"` | Title shown on the generated index pages.                                                          |
| `input`           | list      | **required**             | List of input groups (see below). Each group is a `SubConfig`.                                     |
| `path_prefix`     | `str`     | `"cxxdox/"`              | Directory under `docs/` where generated pages are placed. Use `auto/` to let the plugin derive it. |
| `root`            | `dir`     | `.`                      | Root directory used to resolve relative `include`/`exclude` paths.                                 |
| `groups`          | list      | `[]`                      | Optional source-file groups. Each group gets its own index and type pages.                         |
| `live_reload_cache` | `bool`  | `true`                    | During `mkdocs serve`, parse and generate the C++ reference once, then reuse it for later reloads. Restart the server after changing C++ inputs or cxxdox configuration. |
| `render_snippet_markers` | `bool` | `true` | Process `|||` markers in C/C++ fenced blocks and keep only their rendered sides. |
| `git_browse`      | `str`     | `""`                     | URL template for declaration links. Supports `{SHA}`, `{FILE_PATH}`, and `{LINE}` placeholders.  |
| `default_namespace` | `str`   | `""`                     | Namespace used only when displaying names; its prefix is omitted from matching symbols.           |

### Input group options (`input[i]`)

Each entry in `input` is a sub-config with:

| Option            | Type      | Default | Description                                                                               |
|-------------------|-----------|---------|-------------------------------------------------------------------------------------------|
| `include`         | list[str] | —       | Glob patterns of files to parse (relative to `root`). **Required.**                       |
| `exclude`         | list[str] | `[]`    | Glob patterns of files to skip.                                                           |
| `exclude_symbols` | list[str] | `[]`    | Glob patterns of symbol spellings to omit from the docs (e.g. `'*excluded_function()*'`). |
| `compile_options` | list[str] | `[]`    | Extra clang arguments (e.g. `-std=c++17`, `-Iinclude`, `-DMACRO=1`).                      |
| `hide_tokens`     | list[str] | `[]`    | Preprocessor tokens to hide from rendered source (e.g. `ALWAYS_INLINE`).                  |
| `inline_namespaces` | list[str] | `[]`  | Namespace names to treat as inline while resolving and displaying symbols.                 |

### Source-file groups

Groups assign declarations to separate documentation sections using gitignore-style file
patterns. Patterns support `*`, `**`, `?`, negation with `!`, rooted patterns beginning
with `/`, and comments beginning with `#`. The last matching pattern wins. A declaration
that does not match a configured group is placed in the default group.

```yaml
groups:
  - id: core
    title: Core API
    description: The main public API.
    file:
      - include/mylib/**
      - '!include/mylib/detail/**'
  - id: extensions
    title: Extensions
    file:
      - include/mylib/extensions/**
```

### Source-browser links

Set `git_browse` to a URL template to make each generated declaration location link to
the checked-out revision. The plugin resolves the current commit with `git rev-parse
HEAD` and substitutes the commit SHA, source path, and declaration line:

```yaml
git_browse: https://github.com/example/mylib/blob/{SHA}/{FILE_PATH}#L{LINE}
```

The URL is omitted when Git metadata or a declaration location is unavailable.

### Extracted code snippets

Snippet extraction is separate from the MkDocs build. Run `cxxdox-snippets`
with the Markdown directory to scan and the output directory to create. Every
C/C++ fenced block is written to a `.cpp` file matching its Markdown path;
the output directory is emptied first.

```text
cxxdox-snippets docs snippets
```

Within a C/C++ code block, use `|||` to separate the rendered and dumped
versions of a line. For example, `rendered text|||dumped text` emits each side
to its respective output; `rendered text|||` is render-only and `|||dumped
text` is dump-only. Lines without `|||` are emitted unchanged in both outputs.
To make several consecutive lines render-only, put a line containing at least
ten pipes before and after the region (a trailing space is also allowed). The
pipe marker lines themselves are omitted from both outputs. This is useful for
showing supporting declarations while extracting only the declaration that
follows them. A common indentation is removed before marker processing, so the
marker syntax also works inside an indented Markdown block:

```c++
  ||||||||||||
  template <typename T, size_t N>
  struct vec {};
  ||||||||||||
  void fn(vec<T, N>) {}
```

The rendered output contains all lines except the pipe markers; the dumped
snippet contains only `void fn(vec<T, N>) {}`. Snippets with no dumped content
are skipped; pages containing only skipped snippets produce no `.cpp` or `.c`
file.
The plugin applies this processing to fenced blocks when
`render_snippet_markers` is enabled. Doxygen `@code` blocks are rendered as
written and are not extracted.

### Full example

```yaml
plugins:
  - search
  - cxxdox:
      title: Demo library Reference
      path_prefix: auto/
      default_namespace: demo
      git_browse: https://github.com/example/demo/blob/{SHA}/{FILE_PATH}#L{LINE}
      groups:
        - id: public
          title: Public API
          file:
            - library.hpp
      input:
        - include:
            - library.hpp
          exclude: []
          exclude_symbols:
            - '*excluded_function()*'
          hide_tokens:
            - ALWAYS_INLINE
          inline_namespaces:
            - v1
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
2. Extracts the `libclang` binary and stages it into `cxxdox_plugin/libclang21/` with the platform-correct name (`libclang.dll` / `libclang.so`).
3. Extracts the **clang resource directory** (`lib/clang/<major>/include/`) — which contains builtin headers such as `stddef.h`, `stdarg.h`, `immintrin.h`, `arm_neon.h` etc. — from the Linux LLVM archive (the resource headers are target-independent, so one copy serves all platforms) and stages it into:
   - `cxxdox_plugin/libclang21/clang/<major>/` — used by the explicit `-resource-dir` argument
   - `cxxdox_plugin/lib/clang/<major>/` — used by libclang's implicit resource-dir discovery
4. Builds a platform-specific wheel with `setuptools`/`build` and validates it with `twine`.
5. Asserts that `stddef.h` and `immintrin.h` are present inside the produced wheel (packaging test).
6. Uploads the wheel as a build artifact and, on tagged releases, attaches it to the GitHub Release.

The bundled libclang version is controlled by a single `LLVM_VERSION` variable at the top of the workflow — change it in one place to bump every platform's binary and resource headers. The `libclang.dll`/`.so`/`.dylib` binaries and resource headers are **not** committed to git; they are pulled from the official LLVM release at build time.

### Why bundled resource headers matter

`stddef.h`, `stdarg.h`, `immintrin.h`, `arm_neon.h` etc. are **clang builtin headers** — they are not part of the system C library (glibc / MSVC CRT) and are not installed by packages like `clang-dev`. They live in clang's *resource directory* (`clang -print-resource-dir`). Without them, parsing any header that transitively includes `<cstddef>`, `<cstdio>`, or any SIMD intrinsics fails with a fatal diagnostic and produces a silently incomplete index.

By bundling the resource headers inside the wheel, cxxdox works correctly in any environment — including minimal CI containers with no system LLVM installed.

### `fail_on_parse_error` config option

The plugin now aborts the mkdocs build by default when clang reports a fatal diagnostic (e.g. a header file not found). To opt out and produce partial documentation anyway, add to your `mkdocs.yml`:

```yaml
plugins:
  - cxxdox:
      fail_on_parse_error: false
```

---

## License

Apache-2.0 WITH LLVM-exception (see [LICENSE.TXT](LICENSE.TXT)). The vendored `cindex.py` and bundled `libclang` binary are part of the LLVM Project, distributed under the same license.

[MkDocs]: https://www.mkdocs.org/
