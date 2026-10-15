import argparse
import json
from scene_completion.finalize import run

parser = argparse.ArgumentParser(description='Validate, independently review, export and verify a completed v2 run')
parser.add_argument('--run-dir', required=True)
parser.add_argument('--review-config', required=True)
args = parser.parse_args()
result = run(args.run_dir, args.review_config)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result.get('ready_to_deliver') else 2)
