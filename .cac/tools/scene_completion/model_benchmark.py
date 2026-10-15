"""Isolated role screening using real packets and the unchanged role validators."""
import copy
from pathlib import Path
from types import SimpleNamespace
import time

from .semantic_backend import read_json, write_json, prepare_packets, run_agent_packets, collect_packets
from .sources import fingerprint
from .performance import Profiler, span
from .response_contract import contract_view


def _assignment_fingerprint(packet):
    """Bind a benchmark task to its complete assigned role packet."""
    return fingerprint({key: packet.get(key) for key in ('stage', 'input', 'instructions', 'output_contract')})


def _client_identity(client):
    from .model_configuration import request_effort
    config = client.config
    return fingerprint({'model': client.model('agent'),
        'endpoint_hash': fingerprint(getattr(client, 'base_url', 'native')),
        'thinking': bool(config.get('thinking')), 'reasoning_effort': request_effort(config),
        'thinking_budget': config.get('thinking_budget')})


def _supplement_instruction(attempt):
    if attempt == 0:
        return None
    return (f'Independent screening repeat {attempt}. Re-read only this task’s assigned input and original role evidence; '
        'analyze it from scratch without relying on any previous attempt. Follow the same output contract.')


def _task_is_current(task, packet):
    data_fingerprint = fingerprint(packet['input'])
    assigned = _assignment_fingerprint(packet)
    # Migrate reports written before full-packet assignments were recorded.
    if task.get('assignment_fingerprint') is None and task.get('input_fingerprint') == data_fingerprint:
        task['assignment_fingerprint'] = assigned
    return task.get('assignment_fingerprint') == assigned


def _reported_success(output, task, validator, model):
    """Trust a passed report only when its saved execution still validates."""
    for attempt in reversed(task.get('attempts', [])):
        relative = attempt.get('folder')
        if not isinstance(relative, str):
            continue
        folder = Path(relative)
        if not folder.is_absolute():
            folder = output / folder
        if not (folder / 'manifest.json').exists():
            continue
        try:
            _, status = collect_packets(folder, lambda p, r: validator(p, contract_view(p, r)))
            manifest = read_json(folder / 'manifest.json')
            wrong_model = False
            for row in manifest.get('batches', []):
                result_path = folder / 'results' / (row['batch_id'] + '.json')
                if not result_path.exists():
                    continue
                result = read_json(result_path)
                if result.get('model') != model:
                    wrong_model = True
                    break
            if status.get('complete') and not wrong_model:
                return True, None
            errors = status.get('errors', {})
            for batch_id, message in errors.items():
                result_path = folder / 'results' / (batch_id + '.json')
                raw = read_json(result_path) if result_path.exists() else None
                return False, {'validation_error': message, 'raw_output': raw}
            if wrong_model:
                return False, {'validation_error': 'saved execution model does not match this candidate', 'raw_output': None}
        except (ValueError, KeyError, OSError, TypeError):
            continue
    return False, None


def cases(source):
    from . import interaction_batches as b
    from .interaction_audit import checker_audit_validator
    from .concern_gap_dag import diagnosis_validator
    from .concern_gap_batches import generation_validator
    source = Path(source)
    index = read_json(source / 'sources_index.json')
    tests = read_json(source / 'test_sources_index.json')
    state = read_json(source / 'case_tasks.json')['tasks']
    case = read_json(source / 'run_manifest.json')['scope']['use_case_ids'][0]
    specs = []
    for stage, check in [('normal', b.model_validator(index)), ('E-extract', b.checker_validator(index)),
            ('E-audit', checker_audit_validator(index)), ('T-extract', b.test_validator(tests))]:
        output = read_json(source / state[case + ':' + stage]['output_file'])
        original = source / 'cases' / fingerprint(case)[:16] / 'batches' / stage
        folder = original if (original / 'manifest.json').exists() else Path(output['folder'])
        for number, row in enumerate(read_json(folder / 'manifest.json')['batches']):
            specs.append((stage + '-' + str(number), read_json(folder / 'packets' / (row['batch_id'] + '.json')), check))
    root = source / 'cases' / fingerprint(case)[:16] / 'batches'
    folder = root / 'G-generate'
    rows = read_json(folder / 'manifest.json')['batches']
    failed = next((r for r in rows if not (folder / 'results' / (r['batch_id'] + '.json')).exists()), rows[0])
    specs.append(('G-generate', read_json(folder / 'packets' / (failed['batch_id'] + '.json')), generation_validator(index)))
    folder = root / 'G-generate-diagnosis-1'
    if (folder / 'manifest.json').exists():
        row = read_json(folder / 'manifest.json')['batches'][0]
        specs.append(('diagnosis', read_json(folder / 'packets' / (row['batch_id'] + '.json')), diagnosis_validator))
    return specs


def run(source, config, output, *, supplements=2, tasks=None):
    """No model fallback: independent and repaired passes remain distinct."""
    from .role_cli import _client
    from .model_access import preflight
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    profiler = Profiler(output)
    args = SimpleNamespace(config=str(config), env_file='.env', agent_runtime=None,
        agent_model=None, embedding_model=None, max_concurrency=1)
    client = _client(args, output)
    client.profiler = profiler
    client.config.update(semantic_max_attempts=1, max_concurrency=1)
    model = client.model('agent')
    execution_identity = _client_identity(client)
    report_file = output / 'screening.json'
    report = read_json(report_file) if report_file.exists() else {'model': model, 'tasks': {}}
    if report.get('model') != model:
        profiler.finish('screening')
        raise ValueError('screening output belongs to a different model; use a separate candidate output directory')
    prior_identity = report.get('execution_identity')
    if prior_identity is not None and prior_identity != execution_identity:
        profiler.finish('screening')
        raise ValueError('screening output belongs to a different endpoint or request configuration')
    report['execution_identity'] = execution_identity
    specs = cases(source)
    try:
        selected = sorted(set(tasks)) if tasks else [name for name, _, _ in specs]
        if set(selected) - {name for name, _, _ in specs}:
            raise ValueError('unknown screening task selection')
        if report.get('task_scope') is not None and report['task_scope'] != selected:
            raise ValueError('screening task scope changed; use a separate trial directory')
        report['task_scope'] = selected
        specs = [spec for spec in specs if spec[0] in selected]
        reusable = True
        for name, packet, validator in specs:
            task = report['tasks'].get(name, {})
            if not task.get('passed') or not _task_is_current(task, packet):
                reusable = False
                break
            valid, failure = _reported_success(output, task, validator, model)
            if not valid:
                reusable = False
                task['passed'] = False
                task['reported_pass_invalidated'] = True
                if failure and task.get('attempts'):
                    task['attempts'][-1].setdefault('validation_failures', []).append(failure)
                    task['last_validation_error_fingerprint'] = fingerprint(failure['validation_error'])
                write_json(report_file, report)
                break
        if reusable:
            report.update(model=model, status='screening_passed')
            write_json(report_file, report)
            return report
        terminal = True
        has_no_progress = False
        for name, packet, validator in specs:
            task = report['tasks'].get(name, {})
            if not _task_is_current(task, packet):
                terminal = False
                break
            if task.get('passed'):
                valid, failure = _reported_success(output, task, validator, model)
                if valid:
                    continue
                task['passed'] = False
                task['reported_pass_invalidated'] = True
                if failure and task.get('attempts'):
                    task['attempts'][-1].setdefault('validation_failures', []).append(failure)
                    task['last_validation_error_fingerprint'] = fingerprint(failure['validation_error'])
                write_json(report_file, report)
                terminal = False
                break
            if task.get('no_progress'):
                has_no_progress = True
                continue
            terminal = False
            break
        if terminal:
            report.update(model=model, status='semantic_failures' if has_no_progress else 'screening_passed')
            write_json(report_file, report)
            return report
        try:
            report['availability'] = preflight(client)
        except Exception as exc:
            report.update(model=model, status='inaccessible_or_transport_blocked',
                diagnostic=getattr(exc, 'response_diagnostic', {'error_type': type(exc).__name__}))
            write_json(report_file, report)
            return report
        for name, packet, validator in specs:
            task = report['tasks'].setdefault(name, {'attempts': []})
            task.pop('blocked_category', None)
            data = copy.deepcopy(packet['input'])
            assignment_fingerprint = _assignment_fingerprint(packet)
            if (task.get('input_fingerprint') and task['input_fingerprint'] != fingerprint(data)) or (
                    task.get('assignment_fingerprint') and task['assignment_fingerprint'] != assignment_fingerprint):
                raise ValueError('screening assignment changed; retain the previous trial instead of relabeling or overwriting it')
            task['context_kind'] = 'inherited_repair_context' if 'bounded_repair' in data else 'original_role_evidence'
            task['role_context_kind'] = task['context_kind']
            task['input_fingerprint'] = fingerprint(data)
            task['assignment_fingerprint'] = assignment_fingerprint
            # Same supplied role evidence, instructions and contract for every
            # candidate. No outputs from another role are added by screening.
            for attempt in range(len(task['attempts']), supplements + 1):
                if task.get('no_progress'):
                    break
                if task.get('passed'):
                    break
                # Each correction uses a fresh packet and receives only this
                # role's own failed output and validator finding.
                folder = output / 'batches' / name / ('attempt-' + str(attempt).zfill(3))
                run_data = copy.deepcopy(data)
                instructions = list(packet['instructions'])
                repair = None
                if attempt > 0:
                    prior_failures = [failure for old in task['attempts']
                        for failure in old.get('validation_failures', [])]
                    if not prior_failures:
                        task['repair_unavailable'] = 'no same-role validation error and rejected output were captured'
                        break
                    prior = prior_failures[-1]
                    repair = {'attempt': attempt, 'validation_error': prior['validation_error'],
                        'raw_output': prior['raw_output']}
                    run_data['bounded_repair'] = repair
                    task['context_kind'] = 'self_repair_context'
                    instructions.append('Correct this role packet’s rejected output using bounded_repair.validation_error and bounded_repair.raw_output. Preserve any valid items, correct only the identified failure, and keep all evidence within this assigned role. This packet is batch-level, so return the complete corrected output contract.')
                prepare_packets(folder, packet['stage'], [run_data], instructions, packet['output_contract'])
                validation_failures = []

                def checked_validator(p, result):
                    view = contract_view(p, result)
                    try:
                        return validator(p, view)
                    except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                        validation_failures.append({'validation_error': str(exc),
                            'raw_output': copy.deepcopy(view)})
                        raise

                with span(profiler, 'task', case='screening', stage=name, phase='execute' if attempt == 0 else 'supplement'):
                    started = time.monotonic()
                    result = run_agent_packets(folder, client, checked_validator)
                    attempt_record = {'attempt': attempt, 'kind': 'initial' if attempt == 0 else 'bounded_self_repair',
                        'folder': folder.relative_to(output).as_posix(),
                        'seconds': time.monotonic()-started, 'result': result}
                    if validation_failures:
                        attempt_record['validation_failures'] = validation_failures
                        error_fingerprint = fingerprint(validation_failures[-1]['validation_error'])
                        previous_error = task.get('last_validation_error_fingerprint')
                        task['no_progress'] = bool(previous_error and previous_error == error_fingerprint)
                        task['last_validation_error_fingerprint'] = error_fingerprint
                    task['attempts'].append(attempt_record)
                    task['passed'] = result['complete']
                    task['initial_trial_pass'] = bool(result['complete'] and attempt == 0)
                    task['independent_pass'] = bool(result['complete'] and attempt == 0 and task['role_context_kind'] == 'original_role_evidence')
                    task['self_repaired_pass'] = bool(result['complete'] and attempt > 0)
                    task['assisted_context_pass'] = bool(result['complete'] and task['role_context_kind'] == 'inherited_repair_context')
                    task['supplemental_pass'] = bool(result['complete'] and attempt > 0)
                    write_json(report_file, report)
                    if not result['complete']:
                        category = next((r.get('failure_category') for r in result.get('batches', []) if r.get('failure_category')), None)
                        if category:
                            task['blocked_category'] = category
                            break
                        if not validation_failures:
                            task['repair_unavailable'] = 'no validator-rejected output was captured for a directed correction'
                            break
                        if task.get('no_progress'):
                            break
            if task.get('blocked_category'):
                report['status'] = 'transport_or_budget_blocked'
                break
        else:
            report['status'] = 'screening_passed' if all(report['tasks'].get(name, {}).get('passed') for name, _, _ in specs) else 'semantic_failures'
        write_json(report_file, report)
        return report
    finally:
        profiler.finish('screening')
