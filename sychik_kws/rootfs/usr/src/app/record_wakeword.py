"""
record_wakeword.py — record N samples of the wake word «Сычик» and
POST them to the running KWS service (/enroll).

Run from any machine that has Python + sounddevice; doesn't need to
be inside the add-on container.  The KWS service is exposed on
http://<ha-host>:10401 (LAN), so you can run this on a laptop while
sitting in front of the speaker.

Usage:
    python record_wakeword.py --speaker-id me --count 10
"""
from __future__ import annotations

import argparse
import io
import sys
import time

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--speaker-id", required=True)
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--seconds", type=float, default=2.5)
    p.add_argument("--label", default="сычик")
    p.add_argument("--api", default="http://127.0.0.1:10401",
                   help="KWS add-on REST API (http://<ha-host>:10401)")
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
    print(f"Will record {args.count} samples of «{args.label}» for speaker "
          f"«{args.speaker_id}» and POST to {args.api}/enroll")
    print("Press <Enter> when ready; you'll have", args.seconds, "s per take.")
    input()
    for i in range(args.count):
        input(f"  take {i+1}/{args.count} — press <Enter> to start, "
              f"say «{args.label}»...")
        time.sleep(0.3)  # tiny pause so the click is not captured
        audio = record(args.seconds)
        wav = to_wav_bytes(audio, 16000)
        try:
            r = requests.post(
                f"{args.api}/enroll",
                files={"file": (f"{args.speaker_id}_{i+1:02d}.wav", wav,
                                "audio/wav")},
                data={"label": args.label, "speaker_id": args.speaker_id},
                timeout=10,
            )
            r.raise_for_status()
            print("  ->", r.json())
        except Exception as e:
            print(f"  !! upload failed: {e}")
    print("Done. Now run train_kws.py to build the model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
