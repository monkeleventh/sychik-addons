#!/usr/bin/env python3
"""Tokenize Russian wake-word «сычик» into BPE tokens at build time."""
import os
import sentencepiece as spm

KEYWORD = "сычик"
BPE_MODEL = "/data/models/bpe.model"
KEYWORDS_FILE = "/app/keywords.txt"


def main() -> None:
    if not os.path.exists(BPE_MODEL):
        raise FileNotFoundError(
            f"BPE model not found at {BPE_MODEL} — Dockerfile COPY bpe.model step failed"
        )
    sp = spm.SentencePieceProcessor()
    sp.Load(BPE_MODEL)
    tokens = sp.EncodeAsPieces(KEYWORD)
    print(f"BPE tokens for «{KEYWORD}»:", tokens)
    if not all(
        sp.PieceToId(t) != 0 for t in tokens
    ):  # 0 = UNK in sentencepiece
        print(
            f"WARNING: some BPE tokens for «{KEYWORD}» are unknown to the model:"
            f" {tokens}"
        )
    os.makedirs(os.path.dirname(KEYWORDS_FILE), exist_ok=True)
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        f.write(" ".join(tokens) + "\n")
    print(f"Wrote {KEYWORDS_FILE}:", " ".join(tokens))


if __name__ == "__main__":
    main()
