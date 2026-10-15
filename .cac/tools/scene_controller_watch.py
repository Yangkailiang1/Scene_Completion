import argparse
import json
from scene_completion.controller_watch import inspect

parser = argparse.ArgumentParser(description='Record actual workflow progress and detect controller stagnation')
parser.add_argument('--run-dir', required=True)
parser.add_argument('--state-file', required=True)
args = parser.parse_args()
result = inspect(args.run_dir, args.state_file)
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(3 if result['stagnated'] else 0)
