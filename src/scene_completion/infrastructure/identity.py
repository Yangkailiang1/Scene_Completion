"""Stable content identities independent of file storage."""

import hashlib
import json


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf8")
    ).hexdigest()
