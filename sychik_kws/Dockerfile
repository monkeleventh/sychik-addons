# SychiK KWS — Russian wake-word detector
# v1.1.1 - generate keywords.txt from bpe.model at build time
# Uses python:3.11-slim (multi-arch manifest, prebuilt wheels for all 5 HA architectures).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        "sherpa-onnx>=1.10" \
        "fastapi>=0.110" \
        "uvicorn[standard]>=0.27" \
        "numpy<2" \
        "soundfile" \
        "python-multipart" \
        "wyoming>=1.5" \
        "sentencepiece>=0.2.0" \
    && python -c "import sherpa_onnx; print('ok')"

WORKDIR /app
COPY rootfs/usr/src/app/ /app/

# Copy BPE model and a tokenization script, then generate keywords.txt
COPY bpe.model /data/models/bpe.model
COPY tokenize_kws.py /app/tokenize_kws.py
RUN mkdir -p /data/models && python /app/tokenize_kws.py

LABEL \
    io.hass.name="SychiK KWS" \
    io.hass.description="Russian wake-word detector for «Сычик»" \
    io.hass.type="addon" \
    io.hass.version="1.0.0" \
    org.opencontainers.image.title="SychiK KWS" \
    org.opencontainers.image.licenses="MIT"

EXPOSE 10400 10401

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:10401/health || exit 1

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "10401"]
