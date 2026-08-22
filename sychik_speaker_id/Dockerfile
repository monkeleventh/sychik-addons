# SychiK Speaker ID — resemblyzer-based speaker identification
# v1.0.5 - force fresh rebuild (break cache for COPY rootfs layer)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libsndfile1 \
        ffmpeg \
        git \
    && rm -rf /var/lib/apt/lists/*

# --extra-index-url (не --index-url!) — torch ищем в PyTorch CDN,
# все остальные пакеты (resemblyzer, librosa, etc.) — в дефолтном PyPI
RUN pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==2.2.0" \
        "resemblyzer==0.1.4" \
        "numpy<1.26" \
        "scipy<1.13" \
        "librosa<0.10" \
        "soundfile" \
        "fastapi>=0.110" \
        "uvicorn[standard]>=0.27" \
        "python-multipart"

WORKDIR /app
COPY rootfs/ /app/

LABEL \
    io.hass.name="SychiK Speaker ID" \
    io.hass.description="Speaker identification via resemblyzer" \
    io.hass.type="addon" \
    io.hass.version="1.0.0" \
    org.opencontainers.image.title="SychiK Speaker ID" \
    org.opencontainers.image.licenses="MIT"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" || exit 1

CMD ["uvicorn", "speaker_id_service:app", "--host", "0.0.0.0", "--port", "8000"]
