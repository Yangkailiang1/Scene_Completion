"""Direct-script worker entry point, including isolated embedded Python."""

import sys
from pathlib import Path

# A parent's sys.path edits are not inherited by a new interpreter. Windows
# embedded Python also ignores PYTHONPATH; bootstrap before any package import.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if __name__ == "__main__":
    from scene_completion.infrastructure.worker_runtime import main

    main()
