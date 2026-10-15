import argparse
import json
from scene_completion.model_trial import inspect_trial
from scene_completion.semantic_backend import write_json

parser = argparse.ArgumentParser(description='Check actual model attribution and whole-trial delivery')
parser.add_argument('--run-dir', required=True)
parser.add_argument('--candidate-model', required=True)
parser.add_argument('--verify', action='store_true')
parser.add_argument('--output-file')
args = parser.parse_args()
result = inspect_trial(args.run_dir, args.candidate_model, verify_delivery=args.verify)
if args.output_file:
    write_json(args.output_file, result)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['independently_qualified'] else 2)
