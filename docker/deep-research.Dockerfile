FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install numpy pandas scikit-learn \
    && python -m pip install torch --index-url https://download.pytorch.org/whl/cpu

WORKDIR /workspace

CMD ["python", "-c", "import torch; print('deep-research: ready', torch.__version__)"]
