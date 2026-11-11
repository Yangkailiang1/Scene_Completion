"""Prepare and finalize a case locally, without the workbench or its scheduler."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--case", required=True)
    prepare.add_argument("--phase", choices=("model", "existing", "test"), required=True)
    prepare.add_argument("--out", required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--draft", required=True)
    finish.add_argument("--output", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
    from scene_completion.analysis.imported_case_results import BUNDLE
    from scene_completion.analysis.standalone_case import finalize, input_phase
    from scene_completion.infrastructure.storage import write_json

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.command == "schema":
            result = BUNDLE
        elif args.command == "prepare":
            result = input_phase(args.input, args.case, args.phase)
            write_json(args.out, result)
            result = {
                "file": args.out,
                "phase": args.phase,
                "status": result.get("status", "ready"),
            }
        else:
            result = finalize(
                json.loads(Path(args.draft).read_text(encoding="utf-8-sig")), args.output
            )
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
