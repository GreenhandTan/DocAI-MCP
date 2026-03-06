FROM docker.1ms.run/library/python:3.11-slim

WORKDIR /app

ARG USE_CN_MIRROR=0
ARG PIP_INDEX_URL=https://pypi.org/simple

RUN if [ "$USE_CN_MIRROR" = "1" ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi

RUN apt-get update -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 \
    && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt -i ${PIP_INDEX_URL}

COPY . .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "3000"]
