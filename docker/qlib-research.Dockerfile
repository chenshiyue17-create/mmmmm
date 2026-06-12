FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY vendor/qlib /workspace/vendor/qlib
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install lightgbm \
    && python -m pip install /workspace/vendor/qlib

CMD ["python", "-c", "import qlib, lightgbm; import qlib.data._libs.rolling; print('qlib-research: ready')"]
