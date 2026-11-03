import sys
from pathlib import Path

from scene_completion.manager.manager_runtime import main

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if __name__ == "__main__":
    main()
