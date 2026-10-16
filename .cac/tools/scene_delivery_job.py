"""Start or inspect durable finalization; never regenerates successful business tasks."""
import argparse
import json

from scene_completion.delivery_job import start, status, worker

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=('start', 'status', 'worker'))
parser.add_argument('--run-dir', required=True)
parser.add_argument('--review-config')
args = parser.parse_args()
if args.action != 'status' and not args.review_config:
    parser.error('--review-config is required')
result = (status(args.run_dir) if args.action == 'status' else
    start(args.run_dir, args.review_config) if args.action == 'start' else
    worker(args.run_dir, args.review_config))
print(json.dumps(result, ensure_ascii=False, indent=2))
