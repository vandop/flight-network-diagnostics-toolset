FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /tmp/server.requirements.txt
COPY clients/python/requirements.txt /tmp/client.requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/server.requirements.txt \
    && pip install -r /tmp/client.requirements.txt

COPY . /app

CMD ["bash"]
