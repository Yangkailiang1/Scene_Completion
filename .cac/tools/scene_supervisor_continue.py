"""Register a diagnosed controller correction, preserving successful tasks and budgets."""
import argparse
import json
from scene_completion.supervisor_continuation import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    try:
        result = request(args.run_dir, args.task, args.plan)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(json.dumps({'scheduled': False, 'reason': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
