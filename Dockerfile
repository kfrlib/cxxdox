FROM alpine:3.20.3

RUN apk update
RUN apk add --no-cache python3 mkdocs-material py3-regex py3-requests py3-colorama py3-pip cmake make g++ git
RUN apk add --no-cache 'clang19-libs' 'clang19' 'clang19-extra-tools' --repository=http://dl-cdn.alpinelinux.org/alpine/edge/main

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip3 install --no-cache-dir mkdocs-glightbox

WORKDIR /opt/clang

RUN wget https://raw.githubusercontent.com/llvm/llvm-project/refs/tags/llvmorg-19.1.3/clang/bindings/python/clang/__init__.py
RUN wget https://raw.githubusercontent.com/llvm/llvm-project/refs/tags/llvmorg-19.1.3/clang/bindings/python/clang/cindex.py

WORKDIR /opt

ADD cparser.py .
ADD generator_markdown.py .
ADD generator.py .
ADD run_examples.py .
ADD common.py .

ADD run.sh .

RUN chmod +x run.sh

RUN ls -la /usr/lib/llvm19/lib

ENTRYPOINT ["/bin/sh", "/opt/run.sh"]

CMD [""]
