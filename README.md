# CXXDOX - Documentation generator for C++ with minimal configuration

* Generates markdown files for mkdocs or rendered html files
* Partially compatible with DOXYGEN syntax
* Built with python and libclang, works in docker (alpine image)
* Requires some mkdocs plugins:
    * `codehilite`
    * `pymdownx.arithmatex` (uses katex for fast math)
* Built for KFR - C++ DSP library (https://kfr.dev)

## Demo

https://www.kfrlib.com/newdocs/index.html

## Selected features

* Parses C++ headers, extracts functions, variables and types and generates mkdocs-compatible markdown files
* Auto link to repository (including commit hash)
* Builtin math
* Code snippets
* Can extract code snippets from `.md` files, build and run the code and create markdown files from it. (great for code examples with output)
* Automatic alphabetical index

## Version

0.1-alpha

## License

MIT License