"""Local BPE encodings for context admission. Never fetch assets at runtime."""

import base64
import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path

TOKENIZERS = ("auto", "o200k_base", "cl100k_base", "utf8_bytes")
DATA = Path(__file__).resolve().parents[1] / "tokenizer_data"


@lru_cache(maxsize=2)
def load_encoding(name):
    import tiktoken

    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf8"))
    spec = manifest[name]
    data = gzip.decompress((DATA / f"{name}.tiktoken.gz").read_bytes())
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError(f"Context tokenizer asset checksum mismatch: {name}")
    ranks = {}
    for row in data.splitlines():
        token, rank = row.split()
        ranks[base64.b64decode(token)] = int(rank)
    return tiktoken.Encoding(
        name=name, pat_str=spec["pattern"], mergeable_ranks=ranks, special_tokens={}
    )


def count_text(encoding, text):
    # Bound encoder work even for an unusually long, unbroken generated field.
    if len(text) <= 16384:
        return len(encoding.encode_ordinary(text))
    return sum(
        len(encoding.encode_ordinary(text[start : start + 16384]))
        for start in range(0, len(text), 16384)
    )


def resolve_encoding(model, requested):
    if requested not in TOKENIZERS:
        raise ValueError("unsupported context_tokenizer")
    if requested == "utf8_bytes":
        return None, None, "configured"

    from tiktoken import encoding_name_for_model

    try:
        known = encoding_name_for_model(model) if model else None
    except KeyError:
        known = None
    if known not in TOKENIZERS[1:3]:
        known = None
    name = (known or "o200k_base") if requested == "auto" else requested
    try:
        return load_encoding(name), name, "model_encoding" if name == known else "proxy"
    except (OSError, ValueError):
        # A damaged installation falls back conservatively and reports why.
        return None, name, "asset_unavailable"
