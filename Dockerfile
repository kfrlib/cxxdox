FROM alpine:3.20.3

RUN apk update
RUN apk add --no-cache python3 mkdocs-material
RUN apk add --no-cache g++ cmake make 'clang18-libs' 'clang18' 'clang18-extra-tools'
RUN apk add --no-cache py3-regex

WORKDIR /opt/clang

RUN wget https://raw.githubusercontent.com/llvm/llvm-project/refs/heads/release/18.x/clang/bindings/python/clang/__init__.py
RUN wget https://raw.githubusercontent.com/llvm/llvm-project/refs/heads/release/18.x/clang/bindings/python/clang/cindex.py
RUN wget https://raw.githubusercontent.com/llvm/llvm-project/refs/heads/release/18.x/clang/bindings/python/clang/enumerations.py

WORKDIR /opt

ADD cparser.py .
ADD generator_markdown.py .
ADD generator.py .
ADD run_examples.py .

ADD run.sh .

RUN chmod +x run.sh

ENTRYPOINT ["/bin/sh", "/opt/run.sh"]

CMD [""]
