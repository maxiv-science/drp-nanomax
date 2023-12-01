FROM python:3

WORKDIR /tmp

COPY . /tmp

RUN python -m pip --no-cache-dir install -r requirements.txt

CMD ["dranspose"]