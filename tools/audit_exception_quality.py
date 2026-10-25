"""Export a reproducible, read-only G/GT/decision audit without model calls."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.cac/tools'))
from scene_completion.quality_audit import audit_run
from scene_completion.usage_index import indexed_usage, usage_csv


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--case', action='append', help='Case ID, repeatable; defaults to zero-validity cases')
    args = parser.parse_args(argv)
    source, target = Path(args.run_dir).resolve(), Path(args.output_dir).resolve()
    if target == source or source.is_relative_to(target):
        parser.error('audit output must not contain or replace the source run')
    target.mkdir(parents=True, exist_ok=True)
    result = audit_run(source, target, args.case)
    usage = indexed_usage(source, view='export')
    (target / 'usage.json').write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding='utf8')
    (target / 'task-usage.csv').write_text(usage_csv(usage), encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
