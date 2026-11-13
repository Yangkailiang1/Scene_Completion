"""Offline test support extracted without changing builder behavior."""

import io
import json


def sse(*rows, done=True):
    raw = "".join("data: " + json.dumps(r) + "\n\n" for r in rows) + (
        "data: [DONE]\n\n" if done else ""
    )
    return io.BytesIO(raw.encode())


__all__ = ["sse"]
