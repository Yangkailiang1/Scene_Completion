"""Compact controller status and optional offline acceptance verification."""
import argparse
import json
import os
from pathlib import Path
from scene_completion.controller_status import wait_for_change


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--process-file')
    parser.add_argument('--budget-ledger', action='append', default=[])
    parser.add_argument('--wait-seconds', type=int, default=0)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--snapshot-file')
    parser.add_argument('--rebuilt-dir')
    admission = parser.add_mutually_exclusive_group()
    admission.add_argument('--pause-admission', action='store_true')
    admission.add_argument('--resume-admission', action='store_true')
    args = parser.parse_args()
    try:
        if args.pause_admission or args.resume_admission:
            root = Path(args.run_dir)
            if not (root / 'case_tasks.json').is_file():
                raise ValueError('admission control requires an existing case-DAG run')
            marker = root / 'pause_requested.json'
            if args.pause_admission:
                temporary = marker.with_suffix('.tmp')
                temporary.write_text(json.dumps({'reason': 'controller requested diagnosis before new external calls'}), encoding='utf8')
                os.replace(temporary, marker)
            else:
                marker.unlink(missing_ok=True)
        result = wait_for_change(args.run_dir, process_file=args.process_file,
            budget_ledgers=args.budget_ledger, wait_seconds=args.wait_seconds, verify=args.verify,
            snapshot_file=args.snapshot_file, rebuilt_dir=args.rebuilt_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'ready_to_deliver': False, 'next_action': 'inspect_state_read_failure', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('ready_to_deliver') else 2


if __name__ == '__main__':
    raise SystemExit(main())
