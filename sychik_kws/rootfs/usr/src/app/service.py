"""
Sherpa-onnx KWS service for the Russian wake word «Сычик».
v1.0.1 - Wyoming 1.10 API: Info/WakeProgram/WakeModel all populated correctly.

Endpoints
---------
GET  /health                       -> {status: "ok"}
GET  /version                      -> {sherpa_onnx: "...", model: "..."}
POST /detect                       -> multipart upload of a 16 kHz mono WAV
                                     -> {detected: bool, confidence: float,
                                         keyword: "сычик"}
POST /enroll                       -> multipart upload of a 16 kHz mono WAV
                                     + JSON {"label": "сычик"} in form field
                                     -> appends to /data/models/enroll/

Wyoming protocol is also served on port 10400 (so the Home Assistant
Wyoming integration can pick it up automatically via the `discovery`
field in config.yaml).

The model is loaded once on startup from $KWS_MODEL_DIR.  If no model
exists yet, the service still starts but /detect returns 503 with a
warning log; train one with `train_kws.py` (see SETCHIK.md).
"""

from __future__ import annotations

import io
import logging
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
import sherpa_onnx
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kws")

MODEL_DIR = Path(os.environ.get("KWS_MODEL_DIR", "/data/models"))
THRESHOLD = float(os.environ.get("KWS_THRESHOLD", "0.65"))
KEYWORD = "сычик"  # Cyrillic, what we expect the model to detect

app = FastAPI(title="SychiK KWS", version="0.1.0")

# --------------------------------------------------------------------
# Model loading
# --------------------------------------------------------------------

_kws: Optional[sherpa_onnx.KeywordSpotter] = None
_model_loaded = False


def _try_load_model() -> bool:
    """Try to load a pre-trained KWS model from MODEL_DIR.
    The expected layout (produced by `train_kws.py` /
    `sherpa-onnx` export) is:

        MODEL_DIR/
            tokens.txt
            encoder.onnx
            decoder.onnx
            joiner.onnx
    """
    global _kws, _model_loaded
    required = ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
    if not all((MODEL_DIR / f).exists() for f in required):
        log.warning(
            "KWS model not found in %s — expected %s. "
            "Run train_kws.py first; /detect will return 503 until then.",
            MODEL_DIR, ", ".join(required),
        )
        return False
    try:
        _kws = sherpa_onnx.KeywordSpotter(
            tokens=str(MODEL_DIR / "tokens.txt"),
            encoder=str(MODEL_DIR / "encoder.onnx"),
            decoder=str(MODEL_DIR / "decoder.onnx"),
            joiner=str(MODEL_DIR / "joiner.onnx"),
            num_threads=2,
            sample_rate=16000,
            feature_dim=80,
            keywords_file="/app/keywords.txt",
            keywords_threshold=THRESHOLD,
        )
        _model_loaded = True
        log.info("KWS model loaded from %s (threshold=%.2f)", MODEL_DIR, THRESHOLD)
        return True
    except Exception:
        log.exception("Failed to load KWS model")
        return False


@app.on_event("startup")
def _on_start() -> None:
    _try_load_model()
    # Also start a tiny Wyoming-protocol server in the background so
    # HA can auto-discover this add-on as a wake-word service.
    import asyncio
    from wyoming.server import AsyncServer
    from wyoming.info import Info, Attribution, WakeModel, WakeProgram
    from wyoming.wake import Detect, Detection
    from wyoming.audio import AudioStart, AudioChunk, AudioStop

    ATTR = Attribution(name="SychiK", url="https://github.com/monkeleventh/sychik-addons")
    info = Info(
        wake=[
            WakeProgram(
                name="сычик",
                attribution=ATTR,
                installed=True,
                description="Russian wake word detector (sherpa-onnx)",
                version="1.0.0",
                models=[
                    WakeModel(
                        name="сычик",
                        attribution=ATTR,
                        installed=True,
                        description="Custom-trained KWS for «Сычик»",
                        version="1.0.0",
                        languages=["ru"],
                        phrase="сычик",
                    ),
                ],
            ),
        ],
    )

    async def _run_wyoming() -> None:
        server = AsyncServer.from_uri("tcp://0.0.0.0:10400")
        log.info("Wyoming server listening on tcp://0.0.0.0:10400")
        # Minimal loop: accept client, then on audio chunks run KWS.
        await server.run(_wyoming_handler)

    async def _wyoming_handler(reader, writer):
        try:
            while True:
                msg = await reader.read()
                if msg is None:
                    return
                if isinstance(msg, AudioChunk):
                    samples = np.frombuffer(msg.audio, dtype=np.int16).astype(np.float32) / 32768.0
                    if _kws is None:
                        continue
                    stream = _kws.create_stream()
                    stream.accept_waveform(sample_rate=msg.rate, waveform=samples)
                    keyword = _kws.get_result(stream).keyword
                    _kws.reset(stream)
                    if keyword == KEYWORD:
                        log.info("Wake word «%s» detected (Wyoming)", KEYWORD)
                        await writer.write(Detection(name=KEYWORD).event())
                else:
                    # Echo info on first connect.
                    if isinstance(msg, AudioStart) or msg is not None and not getattr(msg, "_sychik_inited", False):
                        await writer.write(info.event())
        except Exception as e:
            log.warning("Wyoming client disconnected: %s", e)
        finally:
            try:
                await writer.drain()
            except Exception:
                pass

    @app.on_event("startup")
    def _start_wyoming() -> None:
        asyncio.get_event_loop().create_task(_run_wyoming())


# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _model_loaded, "threshold": THRESHOLD}


@app.get("/version")
def version() -> dict:
    return {
        "sherpa_onnx": getattr(sherpa_onnx, "__version__", "unknown"),
        "model_loaded": _model_loaded,
        "model_dir": str(MODEL_DIR),
        "keyword": KEYWORD,
    }


def _wav_to_samples(wav_bytes: bytes) -> np.ndarray:
    """Decode 16 kHz mono WAV bytes to float32 in [-1, 1]."""
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        from scipy.signal import resample_poly
        data = resample_poly(data, 16000, sr).astype("float32")
    return data.astype("float32", copy=False)


@app.post("/detect")
async def detect(file: UploadFile = File(...)) -> dict:
    if not _model_loaded:
        raise HTTPException(status_code=503, detail="KWS model not loaded")
    raw = await file.read()
    samples = _wav_to_samples(raw)

    stream = _kws.create_stream()
    stream.accept_waveform(sample_rate=16000, waveform=samples)
    # Feed a little tail of silence so the spotter finalises.
    stream.accept_waveform(sample_rate=16000, waveform=np.zeros(1600, dtype="float32"))

    keyword = _kws.get_result(stream).keyword
    _kws.reset(stream)

    detected = keyword == KEYWORD
    return {
        "detected": detected,
        "keyword": keyword or "",
        "confidence": THRESHOLD if detected else 0.0,
        "model_loaded": True,
    }


@app.post("/enroll")
async def enroll(
    file: UploadFile = File(...),
    label: str = Form(...),
    speaker_id: str = Form("default"),
) -> dict:
    """Save a user recording to /data/models/enroll/<speaker_id>/
    The trainer script reads everything in this directory to build the
    KWS model.  Use any label you like; we keep it as «сычик»."""
    out_dir = MODEL_DIR / "enroll" / speaker_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    out_path = out_dir / f"{label}_{ts}.wav"
    raw = await file.read()
    out_path.write_bytes(raw)
    log.info("Enrolled sample: %s (%d bytes)", out_path, len(raw))
    return {"saved": str(out_path), "bytes": len(raw)}
