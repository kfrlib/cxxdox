#!/bin/sh

# sources: /src
# docs: /src/$1
# index: /data
# output: /out
# md output: /out/docs
# html output: /out/site

set -e

mkdir -p /out/docs/auto

echo copy /src/${1}/. to /out
cp -a /src/${1}/. /out

export PATH=/usr/lib/llvm19/bin:$PATH

# On Alpine 3.20.3, some libclang symlinks are broken, so using the real path here
python3 cparser.py --libclang /usr/lib/llvm19/lib/libclang.so.19.1.2 --output /data/cxxindex.json --git /src/${1}/cxxdox.yml /src

python3 generator_markdown.py --refindex /data/cxxindex.json /out/docs/auto

mkdir -p /out/fragments
python3 run_examples.py /out/docs /src/${1}/template /src

cd /out

mkdocs build
