FROM alpine:3.16

RUN apk update && apk upgrade && apk add --no-cache python3 && python3 -m ensurepip && pip3 install --upgrade pip setuptools

RUN pip3 install mkdocs-material

RUN apk add --no-cache g++ cmake make 'clang-libs~=13.0' 'clang~=13.0'
RUN apk add --no-cache 'clang-extra-tools~=13.0'

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
