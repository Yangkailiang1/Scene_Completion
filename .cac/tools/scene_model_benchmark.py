import argparse
import json
from scene_completion.model_benchmark import run

parser = argparse.ArgumentParser(description='Screen fixed independent role packets without model fallback')
parser.add_argument('--source-run', required=True)
parser.add_argument('--config', required=True)
parser.add_argument('--output-dir', required=True)
parser.add_argument('--supplements', type=int, choices=(0, 1, 2), default=2)
parser.add_argument('--task', action='append', help='Select a named hard case; repeat to select several')
args = parser.parse_args()
result = run(args.source_run, args.config, args.output_dir, supplements=args.supplements, tasks=args.task)
print(json.dumps({'status': result['status'], 'model': result['model'],
    'tasks': {k: {'passed': v.get('passed'), 'independent_pass': v.get('independent_pass'),
        'attempts': len(v['attempts']), 'blocked_category': v.get('blocked_category')} for k, v in result['tasks'].items()}}, ensure_ascii=False))
