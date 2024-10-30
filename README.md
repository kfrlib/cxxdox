# CxxDox - Documentation Generator for C++ with Minimal Configuration

CxxDox is a documentation generator for C++ projects that creates markdown files compatible with `mkdocs` or directly rendered HTML files. This tool is designed to be highly compatible with DOXYGEN syntax and is built with Python and libclang to run in a Docker environment.

Using `libclang` allows CxxDox to handle complex, template-heavy C++ projects and support the latest C++ standards. This integration ensures reliable parsing of advanced templates, metaprogramming, and new language features, allowing CxxDox to generate accurate documentation even for projects using cutting-edge C++ constructs.

Current libclang version: `19` (C++20 and c++23 support)

## Features

- Parses C++ headers, extracting functions, variables, and types, and generates `mkdocs`-compatible Markdown files.
- Autolinks to the repository (including commit hash).
- Supports math rendering and syntax highlighting.
- Generates code snippets, optionally runs them, and includes output in the documentation.
- Automatically generates an alphabetical index.

### Requirements

To use CxxDox, you’ll only need Docker.

If you want to render md files manually you’ll need mkdocs or mkdocs-material with the following plugins:
  - `codehilite`
  - `pymdownx.arithmatex` (uses KaTeX for fast math rendering)

### Example Projects

CxxDox is created and used for projects [KFR - C++ DSP library](https://kfr.dev) and [Brisk GUI framework](https://github.com/brisklib/brisk).

## Getting Started

### Building and Running the Docker Container

To build and run the Docker container for CxxDox:

1. Clone your project and place it in the desired directory structure, as required by `run.sh`.
2. Use the following Docker commands to build the image and run the container, specifying the necessary arguments to generate HTML documentation.

#### Build Docker Image

```bash
docker build -t cxxdox .
```

#### Run the Docker Container

```bash
docker run --rm -v $(pwd)/src:/src -v $(pwd)/out:/out -v $(pwd)/data:/data cxxdox <doc_dir>
```

- **`<doc_dir>`**: Replace this with the path to your documentation directory inside `/src`, which contains the files to be documented along with the `cxxdox.yml` and `mkdocs.yml` config files.

### Configuring `cxxdox.yml`

The `cxxdox.yml` file is the main configuration file used to customize the behavior of CxxDox for your project. Below is a guide on how to set up `cxxdox.yml`:

#### Key Configuration Options

- **title**: The title of the documentation. 
  ```yaml
  title: Project Name
  ```

- **postprocessor.ignore**: A list of macros or qualifiers to ignore while parsing, ensuring specific elements aren't included in the documentation.
  ```yaml
  postprocessor:
    ignore: 
      - ALWAYS_INLINE
      - PUBLIC_EXPORT
      - ...
  ```

- **clang.arguments**: Compiler arguments passed to `libclang` to configure parsing. This can include flags for specific standards or preprocessor definitions.
  ```yaml
  clang:
    arguments: 
      - '-std=gnu++20'
      - '-DENABLE_AWESOME_FEATURE=1'
      - ...
  ```

- **input_directory**: Specifies the directory with the source files to document, relative to the `cxxdox.yml` location.
  ```yaml
  input_directory: ../include/your_project
  ```

- **masks**: Patterns to specify file types or names to be included in parsing (e.g., only header files).
  ```yaml
  masks: ['**/*.hpp']
  ```

- **repository**: Format for linking source files to the repository, enabling auto-linking to specific lines of code.
  ```yaml
  repository: https://github.com/your_project/repo/blob/{TAG}/path/to/file/{FILE}#L{LINE}
  ```

- **groups**: Defines categorized groups for organizing functions or classes within documentation.
  ```yaml
  groups:
    filter: "Filter API"
    array: "Array functions"
    ...
  ```

For a full example of a `cxxdox.yml`, refer to this configuration file: https://github.com/kfrlib/kfr/blob/main/docs/cxxdox.yml

### Usage Examples

#### Generating HTML Documentation for a Sample C++ Project

Assuming your project is in a folder named `my_cpp_project`, the following commands will generate the documentation and output it to `./out/site`:

```bash
docker run --rm -v $(pwd)/src:/src -v $(pwd)/out:/out -v $(pwd)/data:/data cxxdox my_cpp_project
```

This command will:
- Copy files from `/src/my_cpp_project/` to `/out`.
- Parse headers, generate Markdown files in `/out/docs`, and then use `mkdocs` to build the site in `/out/site`.

## Demo

View a live demo of the generated documentation [here](https://www.kfrlib.com/newdocs/index.html).

## Version

0.2-beta

## License

Licensed under the Apache License. See `LICENSE.TXT` for details.
