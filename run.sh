#!/bin/sh

# sources: /src
# docs: /src/$1
# index: /data
# output: /out
# md output: /out/docs
# html output: /out/site

mkdir -p /out/docs/auto

echo copy /src/${1}/. to /out
cp -a /src/${1}/. /out

python3 cparser.py --libclang /usr/lib/libclang.so.13 /src/${1}/cxxdox.yml /data/cxxindex.json

python3 generator_markdown.py --refindex /data/cxxindex.json /out/docs/auto

mkdir -p /out/fragments
python3 run_examples.py /out/docs /src/${1}/template /src

cd /out

mkdocs build
