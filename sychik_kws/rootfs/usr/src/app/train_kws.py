"""
train_kws.py — train (or fine-tune) a sherpa-onnx KWS model for the
Russian wake word «Сычик» from user recordings.

Run inside the add-on container:

    docker exec -it addon_sychik_kws python /usr/src/app/train_kws.py
    # or from the HAOS host:
    ha addons logs sychik_kws

If the add-on exposes a shell, you can also run this directly.  It
expects user recordings to be in /share/sychik_kws/models/enroll/.

Output: trained model files dropped into
/share/sychik_kws/models/:
    tokens.txt, encoder.onnx, decoder.onnx, joiner.onnx

The base model is from
https://k2-fsa.github.io/sherpa/onnx/kws.html — we fine-tune a small
pre-trained Russian KWS model on your recordings of «Сычик».
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

LOG = logging.getLogger("train_kws")

# Recommended small-footprint base model for Russian KWS.  If unavailable,
# you can swap to a multilingual one.
DEFAULT_BASE_REPO = "csukuangfj/sherpa-onnx-kws-zipformer-ru-ruslan-small"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--enroll-dir", required=True, type=Path,
                   help="Directory with <speaker_id>/*.wav subfolders")
    p.add_argument("--out-dir", required=True, type=Path,
                   help="Where to write the exported ONNX model")
    p.add_argument("--base-repo", default=DEFAULT_BASE_REPO,
                   help="HF repo with the pre-trained base model")
    p.add_argument("--keyword", default="сычик",
                   help="Spoken keyword (in Cyrillic)")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--device", default="cpu",
                   help="cpu or cuda (cuda requires GPU + torch+cuda)")
    return p.parse_args()


def check_inputs(enroll_dir: Path) -> list[Path]:
    if not enroll_dir.exists():
        sys.exit(f"enroll dir does not exist: {enroll_dir}")
    wavs = sorted(enroll_dir.rglob("*.wav"))
    if len(wavs) < 5:
        sys.exit(
            f"need at least 5 .wav files, found {len(wavs)} in {enroll_dir}. "
            f"Record more samples of «{KEYWORD}» first."
        )
    LOG.info("Found %d enrollment wavs", len(wavs))
    return wavs


def ensure_base_model(base_repo: str, work_dir: Path) -> Path:
    target = work_dir / "base"
    if (target / "tokens.txt").exists():
        LOG.info("Base model already cached at %s", target)
        return target
    LOG.info("Downloading base model %s into %s", base_repo, target)
    target.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=base_repo, local_dir=str(target))
    except Exception as e:
        sys.exit(
            f"failed to download {base_repo}: {e}\n"
            f"Pre-download manually with:\n"
            f"  huggingface-cli download {base_repo} --local-dir {target}"
        )
    return target


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    wavs = check_inputs(args.enroll_dir)

    work = args.out_dir.parent / "train_workdir"
    work.mkdir(exist_ok=True)
    base = ensure_base_model(args.base_repo, work)

    manifest = work / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as fh:
        for w in wavs:
            fh.write(json.dumps({
                "audio_filepath": str(w.resolve()),
                "text": args.keyword,
                "speaker": w.parent.name,
            }, ensure_ascii=False) + "\n")
    LOG.info("Wrote manifest with %d entries to %s", len(wavs), manifest)

    LOG.info("Fine-tuning base model on your recordings…")
    cmd = [
        sys.executable, "-m", "sherpa_onnx.kws.finetune",
        "--base-model", str(base),
        "--manifest",   str(manifest),
        "--out-dir",    str(work / "finetuned"),
        "--epochs",     str(args.epochs),
        "--batch-size", str(args.batch_size),
        "--lr",         str(args.lr),
        "--device",     args.device,
    ]
    LOG.info("$ %s", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        LOG.error("fine-tune failed (rc=%d). Inspect %s and re-run.", rc, work)
        return rc

    finetuned = work / "finetuned"
    for name in ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"):
        src = finetuned / name
        if not src.exists():
            LOG.error("Expected exported file missing: %s", src)
            return 1
        shutil.copy2(src, args.out_dir / name)
        LOG.info("Copied %s -> %s", src, args.out_dir / name)

    LOG.info("✔ Done. Restart the add-on to load the new model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
