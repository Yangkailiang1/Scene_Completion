"""Produce and verify regression, cached resume and effect-review evidence.

These are reproducibility records, not cryptographic attestations of a reviewer.
No command accepts a caller-supplied "tests passed" boolean as proof.
"""
from pathlib import Path
import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from contextlib import contextmanager, ExitStack
from unittest.mock import patch

from .semantic_backend import read_json, write_json, run_agent_packets
from .sources import fingerprint
from .interaction_execution_identity import validate_result_execution


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repository():
    return Path(__file__).resolve().parents[3]


def validation_identity():
    from .interaction_cli import versions
    from .interaction_versions import replay_versions
    repo = repository()
    paths = sorted((repo / 'tests').rglob('*.py'))
    paths += [repo / n for n in ('pyproject.toml', 'pytest.ini', 'conftest.py', 'requirements.txt') if (repo / n).is_file()]
    return fingerprint({'tools': replay_versions(versions()), 'tests': {
        p.relative_to(repo).as_posix(): file_hash(p) for p in paths}})


def batch_snapshot(root):
    root = Path(root)
    paths = []
    for folder in sorted((root / 'batches').glob('interaction-*')):
        manifest = read_json(folder / 'manifest.json')
        paths.append(folder / 'manifest.json')
        for batch in manifest['batches']:
            paths.extend(folder / k / (batch['batch_id'] + '.json') for k in ('packets', 'results'))
    return {p.relative_to(root).as_posix(): file_hash(p) for p in paths}


def resume_cached(root):
    """Execute the real resume worker; a cache miss raises instead of using LLM."""
    from . import interaction_batches as b
    from .interaction_audit import checker_audit_validator
    from .interaction_model_audit import model_audit_validator
    from .interaction_participants import participant_validator
    from .interaction_equivalence import equivalence_validator
    root = Path(root)
    index = read_json(root / 'sources_index.json')
    tests = read_json(root / 'test_sources_index.json')
    validators = {'interaction-model': b.model_validator(index), 'interaction-model-audit': model_audit_validator(index), 'interaction-checker': b.checker_validator(index),
        'interaction-checker-audit': checker_audit_validator(index), 'interaction-generation': b.generation_validator(index),
        'interaction-matching': b.pair_validator, 'interaction-verification': b.pair_validator,
        'interaction-recommendation': b.recommendation_validator(index), 'interaction-test-conditions': b.test_validator(tests),
        'interaction-adoption': b.pair_validator, 'interaction-participants': participant_validator(index),
        'interaction-equivalence': equivalence_validator}
    records = []
    for stage, validator in validators.items():
        folder = root / 'batches' / stage
        for batch in read_json(folder / 'manifest.json')['batches']:
            result_path = folder / 'results' / (batch['batch_id'] + '.json')
            result = read_json(result_path)
            identity = validate_result_execution(result, result_path=result_path)
            evidence = result['execution_model_evidence']
            class CacheOnlyClient:
                config = {'max_concurrency': 1, 'thinking': evidence.get('thinking', False),
                    'reasoning_effort': evidence.get('reasoning_effort'),
                    'allowed_cached_models': [identity['model']]}
                def model(self, kind):
                    return identity['model']
                def agent(self, packet):
                    raise RuntimeError('same-version resume required a new model call: ' + packet['batch_id'])
            state = run_agent_packets(folder, CacheOnlyClient(), validator, batch_ids=[batch['batch_id']])
            if not state['complete'] or state['batches'] != [{'batch_id': batch['batch_id'], 'status': 'cached'}]:
                raise ValueError('same-version cached resume failed: ' + batch['batch_id'])
            records.append({'stage': stage, **state['batches'][0], 'model': identity['model'],
                'proof_kind': identity['proof_kind'], 'execution_evidence_hash': identity['execution_evidence_hash']})
    return records


@contextmanager
def deny_resume_network():
    """Fail any standard Python socket access during the resume verification."""
    calls = {'attempts': 0}
    def deny(*args, **kwargs):
        calls['attempts'] += 1
        raise RuntimeError('network access is forbidden during cached resume')
    with ExitStack() as stack:
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            stack.enter_context(patch(name, deny))
        yield calls


def junit_counts(path):
    xml = ET.parse(path).getroot()
    suites = [xml] if xml.tag == 'testsuite' else list(xml.findall('testsuite'))
    return {key: sum(int(s.get(key, '0')) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}


def run_validation(args):
    from .interaction_replay import replay
    root = Path(args.output_dir).resolve()
    (root / 'acceptance_checks.json').unlink(missing_ok=True)
    initial = replay(root)
    identity = validation_identity()
    folder = root / 'verification'
    folder.mkdir(parents=True, exist_ok=True)
    junit = folder / 'regression.xml'
    command = [sys.executable, '-m', 'pytest', '-q', '--junitxml=' + str(junit)]
    process = subprocess.run(command, cwd=repository(), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    log = folder / 'regression.log'
    log.write_text(process.stdout + process.stderr, encoding='utf-8')
    counts = junit_counts(junit) if junit.exists() else {}
    record = {'schema': 1, 'result_hash': initial['result_hash'], 'validation_identity': identity,
        'command': command, 'cwd': str(repository()), 'exit_code': process.returncode,
        'junit_counts': counts, 'junit_hash': file_hash(junit) if junit.exists() else None, 'log_hash': file_hash(log)}
    write_json(folder / 'regression.json', record)
    if process.returncode != 0 or not counts.get('tests') or counts.get('failures') or counts.get('errors') or counts.get('skipped'):
        return {'complete': False, 'accepted': False, 'regression': record}, 2
    before = batch_snapshot(root)
    with deny_resume_network() as network:
        resumed = resume_cached(root)
    after = batch_snapshot(root)
    final = replay(root)
    if network['attempts'] or identity != validation_identity() or before != after or initial != final:
        raise ValueError('tools, inputs, results or metrics changed during regression/resume verification')
    resume = {'schema': 1, 'result_hash': initial['result_hash'], 'validation_identity': identity,
        'before': before, 'after': after, 'batches': resumed, 'before_replay': initial, 'after_replay': final,
        'network_calls': network['attempts'], 'network_guard': 'socket-deny', 'worker': 'run_agent_packets/cache-only'}
    write_json(folder / 'resume.json', resume)
    checks = {'schema': 1, 'result_hash': initial['result_hash'], 'validation_identity': identity,
        'regression_hash': file_hash(folder / 'regression.json'), 'resume_hash': file_hash(folder / 'resume.json')}
    write_json(root / 'acceptance_checks.json', checks)
    return {'complete': True, 'result_hash': initial['result_hash'], 'junit_counts': counts,
        'resumed_batches': len(resumed), 'note': 'Coverage and actual effect review remain separate acceptance gates.'}, 0


def verify_validation(root, result):
    root = Path(root)
    try:
        checks = read_json(root / 'acceptance_checks.json')
        folder = root / 'verification'
        reg = read_json(folder / 'regression.json')
        resume = read_json(folder / 'resume.json')
        identity = validation_identity()
        if checks.get('schema') != 1 or any(v.get('result_hash') != result['result_hash'] or v.get('validation_identity') != identity for v in (checks, reg, resume)):
            return False
        if checks.get('regression_hash') != file_hash(folder / 'regression.json') or checks.get('resume_hash') != file_hash(folder / 'resume.json'):
            return False
        if reg.get('junit_hash') != file_hash(folder / 'regression.xml') or reg.get('log_hash') != file_hash(folder / 'regression.log'):
            return False
        counts = junit_counts(folder / 'regression.xml')
        if reg.get('exit_code') != 0 or reg.get('junit_counts') != counts or not counts['tests'] or counts['errors'] or counts['failures'] or counts['skipped']:
            return False
        if reg.get('cwd') != str(repository()) or reg.get('command') != [sys.executable, '-m', 'pytest', '-q', '--junitxml=' + str((folder / 'regression.xml').resolve())]:
            return False
        expected = []
        expected_identities = {}
        for stage in sorted((root / 'batches').glob('interaction-*')):
            for batch in read_json(stage / 'manifest.json')['batches']:
                expected.append((stage.name, batch['batch_id']))
                result_path = stage / 'results' / (batch['batch_id'] + '.json')
                identity = validate_result_execution(read_json(result_path), result_path=result_path)
                expected_identities[(stage.name, batch['batch_id'])] = identity
        recorded = resume.get('batches', [])
        if (len(recorded) != len(expected) or sorted((r.get('stage'), r.get('batch_id')) for r in recorded) != sorted(expected)
                or any(r.get('status') != 'cached' for r in recorded)
                or any((r.get('model'), r.get('proof_kind'), r.get('execution_evidence_hash')) !=
                    (expected_identities[(r.get('stage'), r.get('batch_id'))]['model'],
                     expected_identities[(r.get('stage'), r.get('batch_id'))]['proof_kind'],
                     expected_identities[(r.get('stage'), r.get('batch_id'))]['execution_evidence_hash'])
                    for r in recorded if (r.get('stage'), r.get('batch_id')) in expected_identities)):
            return False
        return (resume.get('network_calls') == 0 and resume.get('network_guard') == 'socket-deny' and resume.get('worker') == 'run_agent_packets/cache-only'
            and resume.get('before') == resume.get('after') == batch_snapshot(root)
            and resume.get('before_replay') == resume.get('after_replay') == result)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError):
        return False


REVIEW_AREAS = {'ssd_only_generation', 'layer_isolation', 'mandatory_concerns', 'source_atomicity',
    'exception_identity', 'metric_denominators', 'recommendation_adoption', 'remaining_gaps',
    'participant_completeness', 'rr_sr_business_mapping', 'one_to_one_assignment', 'test_derivation'}


def review_materials(root, result):
    root = Path(root)
    names = ('sources_index.json', 'test_sources_index.json', 'scene_model.json', 'diagrams/ssd.json',
        'concern_baseline.json', 'concern_mounts.json', 'generated_scenarios.json', 'existing_scenarios.json',
        'scenario_matches.json', 'metrics.json', 'recommendations.json', 'adoption.json',
        'coverage_diagnosis.json', 'checker_source_audit.json', 'test_conditions.json', 'model_authorization.json',
        'model_origin_checks.json', 'model_source_audit.json', 'model_graph_checks.json',
        'participant_checks.json', 'recommendation_units.json', 'adoption_matches.json')
    return {'result_hash': result['result_hash'], 'files': {n: file_hash(root / n) for n in names},
        'batches': batch_snapshot(root), 'review_areas': sorted(REVIEW_AREAS)}


def run_prepare_review(args):
    from .interaction_replay import replay
    root = Path(args.output_dir)
    materials = review_materials(root, replay(root))
    write_json(root / 'effect_review_materials.json', materials)
    return {'complete': True, 'materials_hash': fingerprint(materials), 'review_areas': materials['review_areas']}, 0


def verify_effect_review(root, result):
    root = Path(root)
    try:
        review = read_json(root / 'effect_review.json')
        materials = review_materials(root, result)
        raw = read_json(root / 'effect_review_raw.json')
        if (read_json(root / 'effect_review_materials.json') != materials or review.get('materials_hash') != fingerprint(materials)
                or review.get('raw_review_hash') != file_hash(root / 'effect_review_raw.json')):
            return False
        if (review.get('model') != 'gpt-6-luna' or review.get('reasoning_effort') != 'max'
                or review.get('result_hash') != result['result_hash'] or not review.get('agent_id')
                or review.get('passed') is not True or review.get('unresolved_findings') != []):
            return False
        areas = raw.get('areas', [])
        if len(areas) != len(REVIEW_AREAS) or {r.get('area') for r in areas} != REVIEW_AREAS:
            return False
        allowed = set(materials['files']) | set(materials['batches'])
        return (raw.get('materials_hash') == fingerprint(materials) and raw.get('unresolved_findings') == []
            and all(r.get('passed') is True and isinstance(r.get('reason'), str) and r['reason'].strip()
                and isinstance(r.get('evidence_files'), list) and r['evidence_files']
                and set(r['evidence_files']) <= allowed for r in areas))
    except (OSError, ValueError, KeyError, TypeError):
        return False
