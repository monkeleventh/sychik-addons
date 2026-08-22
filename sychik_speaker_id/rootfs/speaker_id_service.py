"""
speaker_id_service.py — REST API for speaker identification (3 family members).

Endpoints
---------
GET  /health                       -> {status: "ok", profiles: [...], n: ...}
GET  /profiles                     -> [{id, name, n_samples, created_at}, ...]
POST /train                        -> multipart upload (file=<wav>) + form
                                     {speaker_id, name}    -> appends embedding
                                     to the profile (averaged if multiple).
POST /identify                     -> multipart upload (file=<wav>)
                                     -> {speaker_id, similarity, confidence,
                                         all_scores: {<id>: <score>}}
DELETE /profiles/{speaker_id}      -> remove a profile

Persistence
-----------
Profiles are stored under $DATA_DIR (default /data):
    profiles.json         metadata (id, name, created_at)
    embeddings/<id>.npy   numpy array of shape (n_samples, 256) — raw
                            embeddings, averaged at identify time

Threshold (cosine similarity) is configured via SIM_THRESHOLD env
(default 0.75 — tuned for resemblyzer's 256-d LDE embeddings).
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from resemblyzer import VoiceEncoder, preprocess_wav

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("speaker-id")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
EMB_DIR = DATA_DIR / "embeddings"
PROFILES_JSON = DATA_DIR / "profiles.json"
SIM_THRESHOLD = float(os.environ.get("SIM_THRESHOLD", "0.75"))
SAMPLE_RATE = 16000

DATA_DIR.mkdir(parents=True, exist_ok=True)
EMB_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SychiK Speaker ID", version="0.1.0")

# --------------------------------------------------------------------
# Voice encoder (singleton, ~50 MB on first import)
# --------------------------------------------------------------------

_encoder: Optional[VoiceEncoder] = None


def get_encoder() -> VoiceEncoder:
    global _encoder
    if _encoder is None:
        log.info("Loading resemblyzer VoiceEncoder (first call)…")
        _encoder = VoiceEncoder()
        log.info("VoiceEncoder ready")
    return _encoder


# --------------------------------------------------------------------
# Persistence helpers
# --------------------------------------------------------------------


def _load_profiles() -> dict[str, dict]:
    if not PROFILES_JSON.exists():
        return {}
    try:
        return json.loads(PROFILES_JSON.read_text(encoding="utf-8"))
    except Exception:
        log.exception("profiles.json is corrupt; starting fresh")
        return {}


def _save_profiles(profiles: dict[str, dict]) -> None:
    PROFILES_JSON.write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _embedding_path(speaker_id: str) -> Path:
    return EMB_DIR / f"{speaker_id}.npy"


def _load_embeddings(speaker_id: str) -> Optional[np.ndarray]:
    p = _embedding_path(speaker_id)
    if not p.exists():
        return None
    return np.load(p)


def _save_embedding(speaker_id: str, emb: np.ndarray) -> None:
    np.save(_embedding_path(speaker_id), emb)


# --------------------------------------------------------------------
# Audio helpers
# --------------------------------------------------------------------


def _decode_wav(raw: bytes) -> np.ndarray:
    """Read WAV/FLAC/OGG bytes, resample to 16 kHz mono, return float32."""
    data, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        from scipy.signal import resample_poly
        data = resample_poly(data, SAMPLE_RATE, sr).astype("float32")
    return data.astype("float32", copy=False)


def _compute_embedding(raw: bytes) -> np.ndarray:
    wav = _decode_wav(raw)
    if wav.size < SAMPLE_RATE // 2:  # less than 0.5 s
        raise HTTPException(
            status_code=400,
            detail=f"audio too short ({wav.size / SAMPLE_RATE:.2f}s); need ≥ 0.5s",
        )
    pp = preprocess_wav(wav, source_sr=SAMPLE_RATE)
    return get_encoder().embed_utterance(pp)


# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    profiles = _load_profiles()
    return {
        "status": "ok",
        "model": "resemblyzer-256d",
        "threshold": SIM_THRESHOLD,
        "n_profiles": len(profiles),
        "profiles": sorted(profiles.keys()),
    }


@app.get("/profiles")
def list_profiles() -> list[dict]:
    profiles = _load_profiles()
    out = []
    for sid, meta in sorted(profiles.items()):
        emb = _load_embeddings(sid)
        out.append({
            "id": sid,
            "name": meta.get("name", sid),
            "n_samples": int(emb.shape[0]) if emb is not None else 0,
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
        })
    return out


@app.post("/train")
async def train(
    file: UploadFile = File(...),
    speaker_id: str = Form(...),
    name: Optional[str] = Form(None),
) -> dict:
    speaker_id = speaker_id.strip().lower()
    if not speaker_id or not speaker_id.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="speaker_id must be alphanumeric (a-z, 0-9, _), e.g. 'me', 'wife', 'daughter'",
        )

    raw = await file.read()
    emb = _compute_embedding(raw)  # shape (256,)

    existing = _load_embeddings(speaker_id)
    if existing is None:
        stacked = emb.reshape(1, -1)
    else:
        stacked = np.vstack([existing, emb.reshape(1, -1)])
    _save_embedding(speaker_id, stacked)

    profiles = _load_profiles()
    now = datetime.now(timezone.utc).isoformat()
    if speaker_id not in profiles:
        profiles[speaker_id] = {
            "name": name or speaker_id,
            "created_at": now,
            "updated_at": now,
        }
    else:
        if name:
            profiles[speaker_id]["name"] = name
        profiles[speaker_id]["updated_at"] = now
    _save_profiles(profiles)

    log.info("Trained %s (%s) — %d samples now", speaker_id, name, stacked.shape[0])
    return {
        "speaker_id": speaker_id,
        "name": profiles[speaker_id]["name"],
        "n_samples": int(stacked.shape[0]),
        "embedding_dim": int(stacked.shape[1]),
    }


@app.post("/identify")
async def identify(file: UploadFile = File(...)) -> dict:
    profiles = _load_profiles()
    if not profiles:
        raise HTTPException(
            status_code=409,
            detail="no profiles enrolled yet — POST /train first",
        )

    raw = await file.read()
    emb = _compute_embedding(raw)  # (256,)

    scores: dict[str, float] = {}
    for sid in profiles:
        e = _load_embeddings(sid)
        if e is None or e.size == 0:
            continue
        c = e.mean(axis=0)
        c = c / (np.linalg.norm(c) + 1e-9)
        norm_emb = emb / (np.linalg.norm(emb) + 1e-9)
        scores[sid] = float(np.dot(c, norm_emb))

    if not scores:
        raise HTTPException(status_code=500, detail="no embeddings on disk")

    best_id = max(scores, key=scores.get)
    best_score = scores[best_id]
    detected = best_score >= SIM_THRESHOLD

    return {
        "speaker_id": best_id if detected else "unknown",
        "similarity": best_score,
        "confidence": max(0.0, min(1.0, (best_score + 1.0) / 2.0)),
        "threshold": SIM_THRESHOLD,
        "all_scores": dict(sorted(scores.items(), key=lambda kv: -kv[1])),
        "detected": detected,
    }


@app.delete("/profiles/{speaker_id}")
def delete_profile(speaker_id: str) -> dict:
    profiles = _load_profiles()
    if speaker_id not in profiles:
        raise HTTPException(status_code=404, detail=f"unknown speaker_id: {speaker_id}")
    profiles.pop(speaker_id, None)
    _save_profiles(profiles)
    p = _embedding_path(speaker_id)
    if p.exists():
        p.unlink()
    return {"deleted": speaker_id}
