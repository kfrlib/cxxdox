FROM alpine:latest

RUN apk update && apk upgrade && apk add --no-cache python3 && python3 -m ensurepip && pip3 install --upgrade pip setuptools

RUN pip3 install mkdocs-material

RUN apk add --no-cache g++ cmake make

RUN apk add --no-cache 'clang-libs~=8.0' 'clang~=8.0' --repository=http://dl-cdn.alpinelinux.org/alpine/v3.10/main

WORKDIR /opt

ADD cparser.py .
ADD generator_markdown.py .
ADD generator.py .
ADD run_examples.py .

ADD clang ./clang

ADD run.sh .

RUN chmod +x run.sh

ENTRYPOINT ["/bin/sh", "/opt/run.sh"]

CMD [""]
