"""Local workbench CLI for humans and code agents. Start serve.py first."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from scene_completion.cli.main import entry

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"pipeline", "task", "evaluate", "inspect"}:
        from scene_completion.cli.task_commands import main

        raise SystemExit(main())
    raise SystemExit(entry())
