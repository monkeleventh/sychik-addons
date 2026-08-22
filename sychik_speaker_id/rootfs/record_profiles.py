"""
record_profiles.py — record N takes per speaker and POST them to the
speaker ID add-on /train endpoint.

Run from any machine that has Python + sounddevice; doesn't need to
be inside the add-on container.  The Speaker ID service is exposed
on http://<ha-host>:8000 (LAN), so you can run this on a laptop.

Usage:
    python record_profiles.py --speaker-id me --name "Игорь" --count 5
    python record_profiles.py --speaker-id wife --name "Аня" --count 5
    python record_profiles.py --speaker-id daughter --name "Маша" --count 5
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--speaker-id", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--seconds", type=float, default=8.0)
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--save-local", default=None,
                   help="optional: directory to also save wav copies")
    return p.parse_args()


def record(seconds: float, sr: int = 16000) -> np.ndarray:
    print(f"  recording {seconds:.1f}s @ {sr} Hz ...", end="", flush=True)
    audio = sd.rec(int(seconds * sr), samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    print(" done")
    return audio.squeeze(-1)


def to_wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def main() -> int:
    args = parse_args()
    name = args.name or args.speaker_id
    print(f"Will record {args.count} takes of speaker «{name}» "
          f"({args.seconds:.0f}s each) and POST to {args.api}/train.")
    print("Vary what you say each take: weather, plans, news headlines, "
          "a question to the speaker, etc.")

    if args.save_local:
        out = Path(args.save_local) / args.speaker_id
        out.mkdir(parents=True, exist_ok=True)
    else:
        out = None

    for i in range(args.count):
        input(f"  take {i+1}/{args.count} — press <Enter>, then talk for "
              f"{args.seconds:.0f}s, then stay quiet for a beat …")
        time.sleep(0.4)
        audio = record(args.seconds)
        wav = to_wav_bytes(audio, 16000)
        try:
            r = requests.post(
                f"{args.api}/train",
                files={"file": (f"{args.speaker_id}_{i+1:02d}.wav", wav,
                                "audio/wav")},
                data={"speaker_id": args.speaker_id, "name": name},
                timeout=30,
            )
            r.raise_for_status()
            print("  ->", r.json())
        except Exception as e:
            print(f"  !! upload failed: {e}")
            continue
        if out:
            (out / f"take_{i+1:02d}.wav").write_bytes(wav)
            print(f"  saved local copy to {out / f'take_{i+1:02d}.wav'}")

    print("Done. Repeat for the other family members.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
