"""Program build provenance, independent of document source identities."""

import re
import subprocess
from pathlib import Path

from scene_completion.infrastructure.paths import PROGRAM_ROOT
from scene_completion.infrastructure.storage import read_json


def program_version(program=None):
    root = Path(program) if program is not None else PROGRAM_ROOT
    # The portable package owns VERSION.json above app/. A source checkout may
    # keep it in its root. Do not discover unrelated ancestors or infer a
    # program version from workflow inputs/document hashes.
    candidates = [root / "VERSION.json"]
    if root.name == "app":
        candidates.append(root.parent / "VERSION.json")
    for path in candidates:
        if path.is_file():
            value = read_json(path)
            commit = value.get("source_commit")
            if isinstance(commit, str) and re.fullmatch(r"[a-fA-F0-9]{7,64}", commit):
                return {
                    "source_commit": commit,
                    "origin": "VERSION.json",
                    "built_at": value.get("built_at"),
                    "platform": value.get("platform"),
                }
    if (root / ".git").exists():
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                timeout=2,
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
            ).strip()
            if re.fullmatch(r"[a-fA-F0-9]{40,64}", commit):
                return {"source_commit": commit, "origin": "git"}
        except (OSError, subprocess.SubprocessError):
            pass
    return {"source_commit": None, "origin": "unknown"}
