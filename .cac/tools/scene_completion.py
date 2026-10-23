#!/usr/bin/env python3
"""Public scene workflow command line."""
from scene_completion.cli import main
if __name__=='__main__':
    import sys
    try:sys.exit(main())
    except (ValueError,OSError,KeyError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
