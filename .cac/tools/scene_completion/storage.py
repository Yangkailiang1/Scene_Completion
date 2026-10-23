"""Content identities and atomic JSON IO shared by the workflow."""
from __future__ import annotations
import hashlib,json,os,threading
from pathlib import Path

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode('utf8')).hexdigest()

def write_json(path: str | Path, value) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

