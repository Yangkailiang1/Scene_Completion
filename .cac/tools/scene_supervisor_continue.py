"""Register a diagnosed controller correction, preserving successful tasks and budgets."""
import argparse
import json
from scene_completion.supervisor_continuation import request, refresh_pending, cancel_pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--plan')
    parser.add_argument('--refresh-pending', action='store_true')
    parser.add_argument('--cancel-pending', metavar='REASON')
    args = parser.parse_args()
    try:
        if args.cancel_pending:
            if args.plan or args.refresh_pending:
                parser.error('cancelling cannot be combined with another operation')
            result = cancel_pending(args.run_dir, args.task, args.cancel_pending)
        elif args.refresh_pending:
            if args.plan:
                parser.error('--plan and --refresh-pending are mutually exclusive')
            result = refresh_pending(args.run_dir, args.task)
        else:
            if not args.plan:
                parser.error('--plan is required unless refreshing an unstarted correction')
            result = request(args.run_dir, args.task, args.plan)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(json.dumps({'scheduled': False, 'reason': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
