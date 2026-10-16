"""Isolated role screening using real packets and the unchanged role validators."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import time

from .semantic_backend import read_json, write_json, prepare_packets, run_agent_packets, collect_packets
from .sources import fingerprint
from .performance import Profiler, span
from .response_contract import contract_view


MAX_INCREMENTAL_TOKENS = 150_000


def _assignment_fingerprint(packet):
    """Bind a benchmark task to its complete assigned role packet."""
    from .semantic_backend import compose_packet
    return fingerprint(compose_packet(packet['stage'],packet['input'],packet['instructions'],packet['output_contract'],
        context_policy=packet.get('context_policy', {})))


def _client_identity(client):
    from .model_configuration import request_effort
    config = client.config
    return fingerprint({'model': client.model('agent'),
        'endpoint_hash': fingerprint(getattr(client, 'base_url', 'native')),
        'thinking': bool(config.get('thinking')), 'reasoning_effort': request_effort(config),
        'thinking_budget': config.get('thinking_budget'),
        'accepted_provider_models': config.get('accepted_provider_models')})


def _supplement_instruction(attempt):
    if attempt == 0:
        return None
    return (f'Independent screening repeat {attempt}. Re-read only this task’s assigned input and original role evidence; '
        'analyze it from scratch without relying on any previous attempt. Follow the same output contract.')


def _legacy_assignment_matches(output, task, packet):
    """Only migrate a legacy assignment after reading its complete saved packet."""
    expected = _assignment_fingerprint(packet)
    for attempt in task.get('attempts', []):
        relative = attempt.get('folder')
        if not isinstance(relative, str):
            continue
        folder = Path(relative)
        if not folder.is_absolute():
            folder = output / folder
        manifest_path = folder / 'manifest.json'
        if not manifest_path.is_file():
            continue
        try:
            manifest = read_json(manifest_path)
            for row in manifest.get('batches', []):
                saved = read_json(folder / 'packets' / (row['batch_id'] + '.json'))
                packet_hash = fingerprint({key: value for key, value in saved.items()
                    if key not in {'batch_id', 'input_hash'}})
                if (saved.get('batch_id') == row.get('batch_id')
                        and saved.get('input_hash') == row.get('input_hash') == packet_hash
                        and fingerprint({key: saved.get(key) for key in ('stage','input','instructions','output_contract')}) == expected
                        and task.get('input_fingerprint') == fingerprint(saved.get('input'))):
                    return True
        except (ValueError, KeyError, OSError, TypeError):
            continue
    return False


def _task_is_current(task, packet, output=None):
    data_fingerprint = fingerprint(packet['input'])
    assigned = _assignment_fingerprint(packet)
    # Legacy reports migrate only when their saved original packet proves the
    # stage, input, instructions and contract were the same assignment.
    if (task.get('assignment_fingerprint') is None
            and task.get('input_fingerprint') == data_fingerprint
            and output is not None and _legacy_assignment_matches(output, task, packet)):
        task['assignment_fingerprint'] = assigned
    return task.get('assignment_fingerprint') == assigned


def _result_matches_client(result, client, result_path):
    from .interaction_execution_identity import validate_result_execution
    from .model_configuration import request_effort
    model = client.model('agent')
    evidence = result.get('execution_model_evidence')
    expected_endpoint = fingerprint(getattr(client, 'base_url', 'native'))
    expected_budget = client.config.get('thinking_budget') if client.config.get('thinking') else None
    if (result.get('model') != model or not isinstance(evidence, dict)
            or evidence.get('requested_model') != model
            or evidence.get('api_endpoint_hash') != expected_endpoint
            or evidence.get('thinking') != bool(client.config.get('thinking'))
            or evidence.get('reasoning_effort') != request_effort(client.config)
            or evidence.get('thinking_budget') != expected_budget):
        raise ValueError('saved execution endpoint, model, or thinking identity differs from this candidate')
    returned = evidence.get('provider_model')
    accepted = client.config.get('accepted_provider_models', [model])
    if not isinstance(accepted, list) or not all(isinstance(value, str) and value for value in accepted):
        raise ValueError('accepted_provider_models must be an explicit nonempty model-name list')
    if returned and returned not in accepted:
        raise ValueError('saved provider model differs from the configured candidate or explicit aliases')
    validate_result_execution(result, result_path=result_path)


def _reported_success(output, task, validator, client):
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
            identity_error = None
            for row in manifest.get('batches', []):
                result_path = folder / 'results' / (row['batch_id'] + '.json')
                if not result_path.exists():
                    continue
                result = read_json(result_path)
                try:
                    _result_matches_client(result, client, result_path)
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    identity_error = str(exc)
                    break
            if status.get('complete') and identity_error is None:
                return True, None
            errors = status.get('errors', {})
            for batch_id, message in errors.items():
                result_path = folder / 'results' / (batch_id + '.json')
                raw = read_json(result_path) if result_path.exists() else None
                return False, {'validation_error': message, 'raw_output': raw}
            if identity_error:
                return False, {'validation_error': identity_error, 'raw_output': result}
        except (ValueError, KeyError, OSError, TypeError):
            continue
    return False, None


class _ScreeningBudgetBlocked(RuntimeError):
    def __init__(self, reason, *, remaining=0, required=0):
        super().__init__('screening incremental token allowance is exhausted or unresolved')
        self.response_diagnostic = {'failure_category': 'budget_exhausted',
            'budget_kind': 'tokens', 'budget_reason': reason,
            'remaining_tokens': remaining, 'required_reservation': required}


def _ledger_usage(path, ledger_limit):
    if not path.exists():
        data = {'schema': 'semantic-token-budget-v1', 'limit': ledger_limit, 'requests': {}}
    else:
        data = read_json(path)
    if (not isinstance(data, dict) or data.get('schema') != 'semantic-token-budget-v1'
            or data.get('limit') != ledger_limit or not isinstance(data.get('requests'), dict)):
        raise _ScreeningBudgetBlocked('token_ledger_invalid_or_changed')
    used, unknown = 0, 0
    for row in data['requests'].values():
        if not isinstance(row, dict):
            raise _ScreeningBudgetBlocked('token_ledger_row_invalid')
        status = row.get('status')
        reservation = row.get('reservation', 0)
        charged = row.get('charged_tokens', row.get('reported_total_tokens', 0))
        if type(reservation) is not int or reservation < 0 or type(charged) is not int or charged < 0:
            raise _ScreeningBudgetBlocked('token_ledger_usage_invalid')
        if status == 'refused':
            continue
        if status in ('reserved', 'usage_unknown'):
            used += max(charged, reservation)
            unknown += 1
        elif status == 'complete':
            used += charged
        else:
            # Unrecognized states cannot be assumed free.
            used += max(charged, reservation)
            unknown += 1
    return used, unknown


def _ledger_rows(path, limit):
    _ledger_usage(path, limit)
    return read_json(path)['requests'] if path.exists() else {}


def _verify_ledger_history(previous, current):
    """Reservations may settle downward; known/unknown charges cannot vanish."""
    for request_id, old in previous.items():
        new = current.get(request_id)
        if not isinstance(new, dict):
            raise _ScreeningBudgetBlocked('token_ledger_request_removed')
        if any(new.get(key) != old.get(key) for key in ('model', 'reservation', 'started_unix')):
            raise _ScreeningBudgetBlocked('token_ledger_request_identity_changed')
        if old.get('status') == 'reserved':
            if new.get('status') not in ('reserved', 'complete', 'usage_unknown', 'refused'):
                raise _ScreeningBudgetBlocked('token_ledger_settlement_invalid')
            status = new.get('status')
            charged = new.get('charged_tokens')
            if status == 'reserved' and new != old:
                raise _ScreeningBudgetBlocked('token_ledger_pending_request_changed')
            if status != 'reserved':
                valid_charge = (status == 'complete' and type(charged) is int and charged > 0
                    and charged == new.get('reported_total_tokens')
                    or status == 'usage_unknown' and charged == new.get('reservation')
                    or status == 'refused' and charged == 0)
                finished = new.get('finished_unix')
                if not valid_charge or type(finished) not in (int, float) or finished < old.get('started_unix', 0):
                    raise _ScreeningBudgetBlocked('token_ledger_settlement_invalid')
        elif new != old:
            raise _ScreeningBudgetBlocked('token_ledger_settled_request_changed')


def _reservation_for_body(body, budget):
    reservation = sum(len(json.dumps(message, ensure_ascii=False).encode('utf8')) + 256
        for message in body.get('messages', []))
    reservation += int(body['max_tokens'])
    if body.get('enable_thinking') or body.get('thinking'):
        reservation += max(budget.reasoning_reserve, int(body.get('thinking_budget', 0)))
    return reservation


class _IncrementalBudgetGuard:
    def __init__(self, client, report, report_file, limit):
        budget = getattr(client, 'token_budget', None)
        if budget is None or not callable(getattr(budget, 'reserve', None)):
            raise _ScreeningBudgetBlocked('candidate_config_requires_existing_token_ledger')
        self.budget = budget
        self.path = Path(budget.path).resolve()
        self.report = report
        self.report_file = report_file
        self.limit = limit
        self.ledger_limit = budget.limit
        self.path_identity = fingerprint(str(self.path))
        used, unknown = _ledger_usage(self.path, self.ledger_limit)
        current_rows = _ledger_rows(self.path, self.ledger_limit)
        state = report.get('incremental_token_budget')
        if state is None:
            state = {'ledger_identity': self.path_identity, 'ledger_limit': self.ledger_limit,
                'incremental_limit': limit, 'baseline_used_tokens': used,
                'last_seen_used_tokens': used, 'unknown_rows_at_baseline': unknown,
                'baseline_request_ids': sorted(current_rows),
                'observed_requests': copy.deepcopy(current_rows)}
            report['incremental_token_budget'] = state
        elif (state.get('ledger_identity') != self.path_identity
                or state.get('ledger_limit') != self.ledger_limit
                or state.get('incremental_limit') != limit):
            raise _ScreeningBudgetBlocked('screening_budget_identity_changed')
        baseline = state.get('baseline_used_tokens')
        if type(baseline) is not int or baseline < 0:
            raise _ScreeningBudgetBlocked('token_ledger_baseline_invalid')
        if 'observed_requests' not in state:
            # Legacy aggregate-only reports cannot authenticate arbitrary
            # settlement changes. A caller must supply a verified migration.
            raise _ScreeningBudgetBlocked('legacy_budget_history_requires_verified_migration')
        _verify_ledger_history(state['observed_requests'], current_rows)
        self._baseline = baseline
        self._record(used, unknown)
        self.original_reserve = budget.reserve

        def guarded_reserve(body):
            current, unknown_now = _ledger_usage(self.path, self.ledger_limit)
            self._check_history()
            estimate = _reservation_for_body(body, budget)
            delta = self._incremental_usage()
            if estimate > self.ledger_limit - current:
                raise _ScreeningBudgetBlocked('insufficient_remaining_ledger_allowance',
                    remaining=max(0, self.ledger_limit - current), required=estimate)
            if delta + estimate > self.limit:
                raise _ScreeningBudgetBlocked('screening_incremental_limit',
                    remaining=max(0, self.limit - delta), required=estimate)
            result = self.original_reserve(body)
            after, unknown_after = _ledger_usage(self.path, self.ledger_limit)
            self._record(after, unknown_after)
            return result

        budget.reserve = guarded_reserve

    def _check_history(self):
        state = self.report['incremental_token_budget']
        current = _ledger_rows(self.path, self.ledger_limit)
        _verify_ledger_history(state['observed_requests'], current)
        return current

    def _incremental_usage(self):
        state = self.report['incremental_token_budget']
        rows = self._check_history()
        baseline_ids = set(state['baseline_request_ids'])
        # Baseline pending reservations stay outside the new allowance; all
        # requests admitted during screening count at actual or held usage.
        return sum(max(row.get('charged_tokens', 0), row.get('reservation', 0))
            if row['status'] in ('reserved', 'usage_unknown') else row.get('charged_tokens', 0)
            for key, row in rows.items() if key not in baseline_ids)

    def _record(self, used, unknown):
        state = self.report['incremental_token_budget']
        rows = self._check_history()
        incremental = self._incremental_usage()
        state.update(last_seen_used_tokens=used, unknown_rows=unknown,
            observed_requests=copy.deepcopy(rows),
            incremental_used_tokens=incremental,
            remaining_incremental_tokens=max(0, self.limit - incremental))
        write_json(self.report_file, self.report)

    def refresh(self):
        used, unknown = _ledger_usage(self.path, self.ledger_limit)
        self._record(used, unknown)


def _install_incremental_budget_guard(client, report, report_file, limit):
    return _IncrementalBudgetGuard(client, report, report_file, limit)


def _largest_closures(rows, key, limit=2):
    """Pick complete source rows by closure size, with stable identifier ties."""
    groups = {}
    for row in rows:
        value = row.get(key)
        if value is not None:
            groups.setdefault(value, []).append(row)
    ranked = sorted(groups, key=lambda value: (
        -len(json.dumps(groups[value], ensure_ascii=False, sort_keys=True)), str(value)))
    selected = set(ranked[:limit])
    return [row for row in rows if row.get(key) in selected], selected


def _mark_fixed_upstream(packet, *, closure):
    packet = copy.deepcopy(packet)
    packet['input']['benchmark_scope'] = {'kind': 'stage_fixed_upstream', 'closure': closure}
    return packet


def _bounded_normalize(packet):
    """Retain two complete scenario/source/evidence closures for G normalization."""
    packet = copy.deepcopy(packet)
    data = packet['input']
    rows = data.get('scenarios', [])
    closure_key = 'mount_id' if any(row.get('mount_id') is not None for row in rows) else 'scenario_id'
    scenarios, _ = _largest_closures(rows, closure_key)
    if not scenarios:
        return _mark_fixed_upstream(packet, closure='up_to_two_source_scenarios')
    ids = {row.get('scenario_id') for row in scenarios}
    data['scenarios'] = scenarios
    uses = {row.get('use_case_id') for row in scenarios}
    exchange_ids = {row.get('exchange_id') for row in scenarios}
    data['original_evidence'] = [row for row in data.get('original_evidence', [])
        if row.get('scenario_id') in ids]
    data['locations'] = [row for row in data.get('locations', [])
        if row.get('use_case_id') in uses]
    data['exchange_details'] = [row for row in data.get('exchange_details', [])
        if row.get('use_case_id') in uses or row.get('exchange_id') in exchange_ids]
    node_ids = {node for row in data['exchange_details'] for node in (row.get('from_node'), row.get('to_node'))}
    data['nodes'] = [row for row in data.get('nodes', [])
        if row.get('node_id') in node_ids or row.get('use_case_id') in uses]
    data['benchmark_source_scenario_ids'] = sorted(ids)
    return _mark_fixed_upstream(packet, closure='up_to_two_source_scenarios')


def _bounded_reverse(packet):
    """Keep at most two source scenarios, including every derived unit/evidence row."""
    packet = copy.deepcopy(packet)
    data = packet['input']
    rows = data.get('original_scenarios', [])
    closure_key = 'mount_id' if any(row.get('mount_id') is not None for row in rows) else 'scenario_id'
    source_rows, _ = _largest_closures(rows, closure_key)
    if not source_rows:
        return _mark_fixed_upstream(packet, closure='up_to_two_source_scenarios')
    ids = {row.get('scenario_id') for row in source_rows}
    data['original_scenarios'] = source_rows
    data['units'] = [row for row in data.get('units', []) if row.get('source_scenario_id') in ids]
    data['original_evidence'] = [row for row in data.get('original_evidence', [])
        if row.get('scenario_id') in ids]
    uses = {row.get('use_case_id') for row in source_rows}
    location_ids = {row.get('location_id') for row in data['units']}
    data['locations'] = [row for row in data.get('locations', [])
        if row.get('location_id') in location_ids or row.get('use_case_id') in uses]
    data['benchmark_source_scenario_ids'] = sorted(ids)
    return _mark_fixed_upstream(packet, closure='up_to_two_source_scenarios')


def _bounded_generation(packet):
    """Keep two mounts and their complete exchange, feature, and source closure."""
    packet = copy.deepcopy(packet)
    data = packet['input']
    mounts, mount_ids = _largest_closures(data.get('mounts', []), 'mount_id')
    if not mounts:
        return _mark_fixed_upstream(packet, closure='up_to_two_mount_source_closures')
    data['mounts'] = mounts
    exchange_ids = {row.get('exchange_id') for row in mounts}
    data['exchanges'] = [row for row in data.get('exchanges', [])
        if row.get('exchange_id') in exchange_ids]
    data['checked_features'] = [row for row in data.get('checked_features', [])
        if row.get('exchange_id') in exchange_ids]
    endpoint_ids = {node for row in data['exchanges'] for node in (row.get('from_node'), row.get('to_node'))}
    data['nodes'] = [row for row in data.get('nodes', []) if row.get('node_id') in endpoint_ids]
    data['benchmark_mount_ids'] = sorted(mount_ids)
    return _mark_fixed_upstream(packet, closure='up_to_two_mount_source_closures')


def _bounded_comparison(packet):
    """Keep one checker and two generated candidates with their full pair matrix."""
    packet = copy.deepcopy(packet)
    data = packet['input']
    checker_rows = data.get('checker', [])[:1]
    if not checker_rows:
        return _mark_fixed_upstream(packet, closure='one_checker_up_to_two_generated')
    generated, _ = _largest_closures(data.get('generated', []), 'scenario_id')
    # The candidate records are already one-row source closures. Keep only the
    # two largest complete records and preserve their original identification.
    generated_ids = {row.get('scenario_id') for row in generated[:2]}
    data['checker'] = checker_rows
    data['generated'] = [row for row in data.get('generated', []) if row.get('scenario_id') in generated_ids]
    checker_ids = [row['scenario_id'] for row in data['checker']]
    generated_ids = [row['scenario_id'] for row in data['generated']]
    data['canonical_metadata'] = {key: value for key, value in data.get('canonical_metadata', {}).items()
        if key in set(checker_ids + generated_ids)}
    data['expected_pairs'] = [{'checker_scenario_id': checker_id, 'generated_scenario_id': generated_id}
        for checker_id in checker_ids for generated_id in generated_ids]
    data['benchmark_expected_pairs_complete'] = True
    return _mark_fixed_upstream(packet, closure='one_checker_up_to_two_generated')


def cases(source):
    from . import interaction_batches as b
    from .interaction_audit import checker_audit_validator
    from .concern_gap_dag import diagnosis_validator, verify_execution_output
    from .interaction_participants import participant_validator
    from . import concern_gap_batches as gb
    from .concern_gap_batches import generation_validator
    from .concern_gap_normalize_diagnostics import validator as normalize_validator
    from .concern_gap_repair import reverse_validator
    from .concern_gap_comparison import validator as comparison_validator
    source = Path(source)
    index = read_json(source / 'sources_index.json')
    tests = read_json(source / 'test_sources_index.json')
    state = read_json(source / 'case_tasks.json')['tasks']
    case = read_json(source / 'run_manifest.json')['scope']['use_case_ids'][0]
    specs = []
    audit_check = checker_audit_validator(index)
    for stage, check in [('normal', b.model_validator(index)), ('E-extract', b.checker_validator(index)),
            ('T-extract', b.test_validator(tests))]:
        output = read_json(source / state[case + ':' + stage]['output_file'])
        original = source / 'cases' / fingerprint(case)[:16] / 'batches' / stage
        folder = original if (original / 'manifest.json').exists() else Path(output['folder'])
        for number, row in enumerate(read_json(folder / 'manifest.json')['batches']):
            specs.append((stage + '-' + str(number), read_json(folder / 'packets' / (row['batch_id'] + '.json')), check))
    audit_folder = root = source / 'cases' / fingerprint(case)[:16] / 'batches' / 'E-audit'
    if audit_folder.is_dir() and (audit_folder / 'manifest.json').is_file():
        audit_packets = []
        for row in read_json(audit_folder / 'manifest.json').get('batches', []):
            packet = read_json(audit_folder / 'packets' / (row['batch_id'] + '.json'))
            if packet['input'].get('requirement_layer') == 'SR':
                audit_packets.append(packet)
        if audit_packets:
            packet = max(audit_packets, key=lambda value: len(json.dumps(value['input'], ensure_ascii=False)))
            specs.append(('E-audit-0', _mark_fixed_upstream(packet, closure='most_complex_SR_audit_packet'), audit_check))
    root = source / 'cases' / fingerprint(case)[:16] / 'batches'
    folder = root / 'G-generate'
    rows = read_json(folder / 'manifest.json')['batches']
    failed = next((r for r in rows if not (folder / 'results' / (r['batch_id'] + '.json')).exists()), rows[0])
    specs.append(('G-generate', _bounded_generation(
        read_json(folder / 'packets' / (failed['batch_id'] + '.json'))), generation_validator(index)))
    folder = root / 'G-generate-diagnosis-1'
    if (folder / 'manifest.json').exists():
        row = read_json(folder / 'manifest.json')['batches'][0]
        specs.append(('diagnosis', _mark_fixed_upstream(
            read_json(folder / 'packets' / (row['batch_id'] + '.json')), closure='existing_focus_input'), diagnosis_validator))

    def graph_validator(packet, result):
        rows = b.graph_validator(index)(packet, result)
        for record in packet['input'].get('reused_components', []):
            verify_execution_output({'executions': record['executions']})
            rows.append(record['check'])
        return rows

    def stage_folder(name):
        folder = root / name
        if (folder / 'manifest.json').is_file():
            return folder
        record = state.get(case + ':' + name, {})
        output_file = record.get('output_file')
        if output_file:
            saved = read_json(source / output_file)
            candidate = Path(saved['folder'])
            return candidate if candidate.is_absolute() else source / candidate
        raise ValueError(f'representative run has no original packet for stage {name}')

    def hardest(name, validator):
        folder = stage_folder(name)
        manifest = read_json(folder / 'manifest.json')
        packets = [read_json(folder / 'packets' / (row['batch_id'] + '.json'))
            for row in manifest.get('batches', [])]
        if not packets:
            raise ValueError(f'representative stage {name} has no real packet')
        # A fixed, real upstream assignment with the largest source context is
        # the stage-level hard case; it does not imply a fresh upstream chain.
        packet = max(packets, key=lambda value: (len(json.dumps(value['input'], ensure_ascii=False)),
            value.get('batch_id', '')))
        if name == 'normalize-G':
            packet = _bounded_normalize(packet)
        elif name == 'reverse-G':
            packet = _bounded_reverse(packet)
        elif name == 'compare-EG':
            packet = _bounded_comparison(packet)
        else:
            packet = _mark_fixed_upstream(packet, closure='one_real_stage_packet')
        return (name, packet, validator)

    for name, validator in [
            ('graphs', graph_validator), ('participants', participant_validator(index)),
            ('features', gb.feature_validator(index)), ('normalize-G', normalize_validator(index)),
            ('reverse-G', reverse_validator), ('compare-EG', comparison_validator)]:
        specs.append(hardest(name, validator))
    return specs


def estimate_inputs(specs):
    """Return offline, conservative packet-size estimates for screening planning."""
    rows = []
    for name, packet, _ in specs:
        serialized = json.dumps({key: packet.get(key) for key in
            ('stage', 'input', 'instructions', 'output_contract')}, ensure_ascii=False, sort_keys=True)
        byte_count = len(serialized.encode('utf8'))
        rows.append({'task': name, 'stage': packet.get('stage'),
            'assignment_utf8_bytes': byte_count,
            # UTF-8 bytes are a deliberately conservative proxy for input tokens.
            'conservative_input_token_estimate': byte_count,
            'context_kind': packet.get('input', {}).get('benchmark_scope', {}).get('kind',
                'inherited_repair_context' if 'bounded_repair' in packet.get('input', {}) else 'original_role_evidence')})
    return rows


def _request_order_size(packet, client):
    serialized = json.dumps({key: packet.get(key) for key in
        ('stage', 'input', 'instructions', 'output_contract')}, ensure_ascii=False, sort_keys=True)
    output_reserve = client.output_limit(packet['stage']) if callable(getattr(client, 'output_limit', None)) \
        else int(client.config.get('max_tokens', 12000))
    # Ordering only; the budget guard uses actual request reservations and
    # settled or conservatively unknown ledger usage.
    return len(serialized.encode('utf8')) + output_reserve


def run(source, config, output, *, supplements=2, tasks=None,
        incremental_token_limit=MAX_INCREMENTAL_TOKENS):
    """No model fallback: independent and repaired passes remain distinct."""
    from .role_cli import _client
    from .model_access import preflight
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (type(incremental_token_limit) is not int or incremental_token_limit < 1
            or incremental_token_limit > MAX_INCREMENTAL_TOKENS):
        raise ValueError(f'incremental_token_limit must be 1..{MAX_INCREMENTAL_TOKENS}')
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
    report['scope'] = {'kind': 'stage_level_fixed_upstream',
        'claim_limit': 'A screening pass evaluates assigned role packets with upstream outputs held fixed; it is not an independently executed whole-chain pass.'}
    specs = cases(source)
    try:
        selected = sorted(set(tasks)) if tasks else [name for name, _, _ in specs]
        if set(selected) - {name for name, _, _ in specs}:
            raise ValueError('unknown screening task selection')
        prior_scope = report.get('task_scope')
        if prior_scope is not None and prior_scope != selected:
            raise ValueError('screening task scope cannot change; use a separate scope directory')
        report['task_scope'] = selected
        specs = [spec for spec in specs if spec[0] in selected]
        report['input_estimates'] = estimate_inputs(specs)
        report['conservative_input_token_estimate_total'] = sum(
            row['conservative_input_token_estimate'] for row in report['input_estimates'])
        write_json(report_file, report)
        reusable = True
        for name, packet, validator in specs:
            task = report['tasks'].get(name, {})
            if not task.get('passed') or not _task_is_current(task, packet, output):
                reusable = False
                break
            valid, failure = _reported_success(output, task, validator, client)
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
            if not _task_is_current(task, packet, output):
                terminal = False
                break
            if task.get('passed'):
                valid, failure = _reported_success(output, task, validator, client)
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
        positions = {name: offset for offset, (name, _, _) in enumerate(specs)}
        specs = sorted(specs, key=lambda spec: (-_request_order_size(spec[1], client), positions[spec[0]]))
        report['execution_order'] = [name for name, _, _ in specs]
        write_json(report_file, report)
        try:
            budget_guard = _install_incremental_budget_guard(client, report, report_file,
                incremental_token_limit)
            report['availability'] = preflight(client)
        except Exception as exc:
            diagnostic = getattr(exc, 'response_diagnostic', {'error_type': type(exc).__name__})
            report.update(model=model,
                status='budget_blocked' if diagnostic.get('failure_category') in ('budget_exhausted', 'quota_exhausted')
                    else 'inaccessible_or_transport_blocked', diagnostic=diagnostic)
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
            task['context_kind'] = 'inherited_repair_context' if 'bounded_repair' in data else 'stage_level_fixed_upstream'
            task['role_context_kind'] = task['context_kind']
            task['scope_kind'] = 'stage_level_fixed_upstream'
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
                        evidence = result.get('execution_model_evidence', {})
                        returned = evidence.get('provider_model')
                        if returned and returned not in client.config.get('accepted_provider_models', [model]):
                            error = RuntimeError('provider returned a different model; verify an explicit alias before continuing')
                            error.response_diagnostic = {'failure_category': 'provider_model_mismatch'}
                            raise error
                        return validator(p, view)
                    except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                        validation_failures.append({'validation_error': str(exc),
                            'raw_output': copy.deepcopy(view)})
                        raise

                with span(profiler, 'task', case='screening', stage=name, phase='execute' if attempt == 0 else 'repair'):
                    started = time.monotonic()
                    result = run_agent_packets(folder, client, checked_validator)
                    budget_guard.refresh()
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
                    task['independent_pass'] = bool(result['complete'] and attempt == 0
                        and task['role_context_kind'] in ('original_role_evidence', 'stage_level_fixed_upstream'))
                    task['whole_chain_independent_pass'] = False
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
                report['status'] = 'budget_blocked' if task['blocked_category'] in ('budget_exhausted', 'quota_exhausted') else 'transport_or_budget_blocked'
                break
        else:
            report['status'] = 'screening_passed' if all(report['tasks'].get(name, {}).get('passed') for name, _, _ in specs) else 'semantic_failures'
        write_json(report_file, report)
        return report
    finally:
        profiler.finish('screening')
