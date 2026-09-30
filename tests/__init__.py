"""Test support for importing the repository's packaged Skill tools."""

import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SKILL_SCRIPTS = _REPOSITORY_ROOT / ".cac" / "tools"
if str(_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL_SCRIPTS))
