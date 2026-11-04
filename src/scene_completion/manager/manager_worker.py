"""Direct-script manager entry point, including isolated embedded Python."""

import sys
from pathlib import Path

# Bootstrap in this interpreter; do not rely on the web parent's import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if __name__ == "__main__":
    from scene_completion.manager.manager_runtime import main

    main()
