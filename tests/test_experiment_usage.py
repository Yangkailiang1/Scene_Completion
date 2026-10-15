import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from scene_completion import experiment_usage as usage
from scene_completion.semantic_backend import read_json, write_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def ledger(tmp_path, name='token_budget.json'):
    path = tmp_path / name
    write_json(path, {'schema': 'semantic-token-budget-v1', 'limit': 900000, 'committed_tokens': 150,
        'reserved_tokens': 0, 'remaining_tokens': 899850, 'requests': {
            'aaaa': {'status': 'complete', 'model': 'fixture-27b', 'reservation': 130, 'charged_tokens': 100,
                'reported_total_tokens': 120, 'started_unix': 1000.5, 'finished_unix': 1010.5},
            'bbbb': {'status': 'usage_unknown', 'model': 'fixture-plus', 'reservation': 50,
                'started_unix': 1020.5, 'finished_unix': 1030.5},
            'cccc': {'status': 'refused', 'model': 'fixture-35b', 'reservation': 70}}})
    return path


def test_unknown_ledger_rows_hold_their_reservation_and_are_never_counted_as_zero(tmp_path):
    path = ledger(tmp_path)
    before = path.read_bytes()
    summary = usage.ledger_summary(path)
    # Committed quota is what was charged for settled calls plus every reservation
    # an unsettled report is still holding; the refused call consumed nothing.
    assert summary['accounting_matches'] is True
    assert (summary['committed_tokens'], summary['charged_tokens'], summary['held_unknown_tokens']) == (150, 100, 50)
    assert summary['reported_total_tokens'] == 120
    assert [row['request_id'] for row in summary['unknown_rows']] == ['bbbb']
    assert summary['unknown_rows'][0]['reservation'] == 50
    assert summary['unknown_rows'][0]['started_at'].startswith('1970-01-01T00:17:00')
    assert [(row['request_id'], row['released_reservation']) for row in summary['refused_rows']] == [('cccc', 70)]
    assert summary['released_refused_tokens'] == 70 and summary['rows_by_status'] == {
        'complete': 1, 'refused': 1, 'usage_unknown': 1}
    assert path.read_bytes() == before


def test_ledger_schema_drift_is_reported_instead_of_silently_iterated(tmp_path):
    path = tmp_path / 'token_budget.json'
    write_json(path, {'schema': 'semantic-token-budget-v1', 'requests': [{'status': 'complete'}]})
    with pytest.raises(ValueError, match='keyed by request id'):
        usage.ledger_summary(path)
    assert usage.ledger_summary(tmp_path / 'missing.json')['available'] is False


def test_controller_channel_reads_only_the_allow_listed_columns(tmp_path):
    db = tmp_path / 'cc-switch.db'
    connection = sqlite3.connect(db)
    connection.execute('CREATE TABLE proxy_request_logs (session_id TEXT, model TEXT, status_code INTEGER, '
        'latency_ms INTEGER, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, '
        'created_at INTEGER, request_params TEXT, api_key TEXT)')
    connection.executemany('INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?,?,?,?)', [
        ('651362fa-original', 'ecnu-max', 200, 1500, 900, 300, 400, 1792054800, 'SENTINEL-REQUEST-PARAMS', 'SENTINEL-KEY'),
        ('651362fa-shadow', 'ecnu-max', 200, 500, 10, 10, 0, 1792054900, 'SENTINEL-REQUEST-PARAMS', 'SENTINEL-KEY'),
        ('54e53dd0-current', 'ecnu-plus', 401, None, 0, 0, 0, 1792055000, 'SENTINEL-REQUEST-PARAMS', 'SENTINEL-KEY'),
        ('b78a2027-old-plus-mall', 'ecnu-plus', 200, 9999, 777, 777, 777, 1792055100, 'SENTINEL-REQUEST-PARAMS', 'SENTINEL-KEY')])
    connection.commit()
    connection.close()
    before = db.read_bytes()
    payload = usage.controller_summary(db, include_sessions=('651362fa', '54e53dd0'),
        exclude_sessions=('651362fa-shadow', 'b78a2027'))
    assert payload['available'] is True and payload['table'] == 'proxy_request_logs'
    assert payload['columns_read'] == list(usage.CONTROLLER_COLUMNS)
    # Sessions outside this experiment are dropped, and an exclusion wins over
    # an inclusion that happens to share its prefix.
    assert [session['session'] for session in payload['sessions']] == ['54e53dd0-current', '651362fa-original']
    first = payload['sessions'][1]
    assert (first['requests'], first['input_tokens'], first['cache_read_tokens']) == (1, 900, 400)
    assert first['latency_seconds_reported'] == 1.5 and first['requests_missing_latency'] == 0
    assert first['window'][0].startswith('2026-')
    assert (payload['totals']['requests'], payload['totals']['requests_missing_latency']) == (2, 1)
    assert payload['totals']['latency_seconds_reported'] == 1.5
    # Provider configuration and request parameters are never selected, so no
    # sentinel from those columns can reach the payload.
    assert 'SENTINEL' not in json.dumps(payload, ensure_ascii=False)
    assert db.read_bytes() == before
    assert usage.controller_summary(tmp_path / 'absent.db')['available'] is False


@pytest.mark.parametrize('reasoning_usage', [
    {'completion_tokens_details': {'reasoning_tokens': 150}}, {'reasoning_tokens': 150}])
def test_telemetry_keeps_cache_and_reasoning_as_sub_items_and_unknown_as_unknown(tmp_path, reasoning_usage):
    events = [
        {'kind': 'request', 'request_kind': 'agent', 'status': 'ok', 'model': 'fixture-27b', 'duration_seconds': 12.5,
            'transport_attempts': 1, 'usage': {'prompt_tokens': 1000, 'completion_tokens': 200, 'total_tokens': 1200,
                'prompt_tokens_details': {'cached_tokens': 800}, **reasoning_usage}},
        {'kind': 'request', 'request_kind': 'agent', 'status': 'failed', 'model': 'fixture-plus',
            'duration_seconds': 30.0, 'transport_attempts': None, 'usage': None},
        {'kind': 'validation', 'request_kind': 'agent', 'usage': {'prompt_tokens': 9999, 'total_tokens': 9999}}]
    (tmp_path / 'performance_events.jsonl').write_text(
        '\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf8')
    payload = usage.telemetry_summary(tmp_path)
    assert [channel['request_kind'] for channel in payload['channels']] == ['agent']
    channel = payload['channels'][0]
    assert (channel['requests'], channel['statuses'], channel['models']) == (2, {'failed': 1, 'ok': 1}, {'fixture-27b': 1, 'fixture-plus': 1})
    # Cache-read and reasoning are provider sub-items of the input and output
    # columns; adding them on top would double-count the same tokens.
    assert (channel['input_tokens'], channel['output_tokens'], channel['total_tokens']) == (1000, 200, 1200)
    assert (channel['cache_read_tokens'], channel['reasoning_tokens']) == (800, 150)
    assert channel['unknown_usage_requests'] == 1 and channel['unknown_transport_attempts'] == 1
    assert channel['request_seconds_reported'] == 42.5
    assert payload['sub_items']['cache_read_tokens'].startswith('subset of input_tokens')
    assert usage.telemetry_summary(tmp_path / 'absent')['available'] is False


def test_telemetry_groups_by_stage_phase_model_and_reports_repair_cost(tmp_path):
    events = [
        {'kind': 'request', 'request_kind': 'agent', 'stage': 'E-extract', 'phase': 'repair',
            'status': 'complete', 'model': 'model-b', 'duration_seconds': 12.5,
            'usage': {'prompt_tokens': 100, 'completion_tokens': 40, 'total_tokens': 140}},
        {'kind': 'request', 'request_kind': 'agent', 'stage': 'E-extract', 'phase': 'repair',
            'status': 'failed', 'model': 'model-b', 'duration_seconds': 4.0, 'usage': None},
        {'kind': 'request', 'request_kind': 'agent', 'stage': 'E-extract', 'phase': 'execute',
            'status': 'complete', 'model': 'model-a', 'duration_seconds': 7.0,
            'usage': {'prompt_tokens': 50, 'total_tokens': 50}},
        {'kind': 'request', 'request_kind': 'agent', 'stage': 'Z-check', 'phase': 'execute',
            'status': 'complete', 'model': 'model-a', 'usage': {'prompt_tokens': 1,
                'completion_tokens': 2, 'total_tokens': 3}},
        {'kind': 'validation', 'stage': 'E-extract', 'phase': 'repair', 'model': 'ignored',
            'usage': {'prompt_tokens': 9000, 'total_tokens': 9000}},
    ]
    (tmp_path / 'performance_events.jsonl').write_text(
        '\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf8')

    payload = usage.telemetry_summary(tmp_path)
    rows = payload['stage_models']
    assert [(row['stage'], row['phase'], row['model']) for row in rows] == [
        ('E-extract', 'execute', 'model-a'), ('E-extract', 'repair', 'model-b'),
        ('Z-check', 'execute', 'model-a')]
    repair = rows[1]
    assert (repair['requests'], repair['input_tokens'], repair['output_tokens'], repair['total_tokens']) == (2, 100, 40, 140)
    assert (repair['unknown_usage_requests'], repair['request_seconds_reported']) == (1, 16.5)
    assert rows[0]['partial_usage_requests'] == 1
    assert rows[0]['missing_usage_fields'] == {'completion_tokens': 1}
    assert rows[2]['unknown_duration_requests'] == 1
    assert payload['repair_costs'] == [{'model': 'model-b', 'requests': 2,
        'input_tokens': 100, 'output_tokens': 40, 'total_tokens': 140,
        'unknown_usage_requests': 1, 'partial_usage_requests': 0,
        'request_seconds_reported': 16.5, 'unknown_duration_requests': 0}]
    # The channel view and stage view describe the same four request events.
    assert payload['channels'][0]['requests'] == sum(row['requests'] for row in rows) == 4
    assert 'Stage | Phase | Model' in usage.render({'ledgers': [], 'telemetry': payload,
        'controller': {'available': False}, 'time': {'available': False}})
    assert 'phase=repair' in payload['note']


def test_time_scales_stay_separate_and_an_unfinished_run_is_not_given_a_wall_clock(tmp_path):
    write_json(tmp_path / 'performance.json', {'schema': 'scene-performance-v1', 'sessions': [
        {'session': 'closed', 'wall_seconds': 120.0, 'task_seconds': 100.0, 'task_busy_seconds': 80.0,
            'task_overlap_seconds': 20.0, 'request_seconds': 60.0},
        {'session': 'open', 'wall_seconds': None, 'task_seconds': 5.0, 'task_busy_seconds': 5.0,
            'task_overlap_seconds': 0.0, 'request_seconds': 5.0}]})
    payload = usage.time_summary(tmp_path)
    assert [span['wall_seconds'] for span in payload['sessions']] == [120.0, None]
    assert payload['sessions'][1]['unfinished_request_count'] == 0
    assert 'separate scales' in payload['note']
    assert usage.time_summary(tmp_path / 'absent')['available'] is False


def test_experiment_statistics_are_written_under_tmp_only(tmp_path):
    assert usage.local_dir(tmp_path / 'stats') == (tmp_path / 'stats').resolve()
    outside = Path(usage.tempfile.gettempdir()).parent / 'scene-experiment-usage'
    with pytest.raises(ValueError, match='local-only'):
        usage.local_dir(outside)
    assert usage.local_dir(outside, allow_any=True) == outside.resolve()


def test_experiment_usage_command_writes_local_reports_without_touching_its_inputs(tmp_path):
    spec = importlib.util.spec_from_file_location('reference_cli', REPOSITORY_ROOT / '.cac/tools/scene_completion.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    path = ledger(tmp_path)
    run_dir = tmp_path / 'run'
    write_json(run_dir / 'performance.json', {'schema': 'scene-performance-v1', 'sessions': [
        {'session': 'run', 'wall_seconds': 33.0, 'task_seconds': 30.0, 'task_busy_seconds': 25.0,
            'task_overlap_seconds': 5.0, 'request_seconds': 20.0}]})
    (run_dir / 'performance_events.jsonl').write_text(json.dumps({'kind': 'request', 'request_kind': 'embedding',
        'status': 'ok', 'model': 'fixture-embed', 'duration_seconds': 1.5, 'usage': {'prompt_tokens': 7,
            'total_tokens': 7}}) + '\n', encoding='utf8')
    before = path.read_bytes()
    assert cli._main_impl(['experiment-usage', '--output-dir', str(tmp_path / 'stats'), '--run-dir', str(run_dir),
        '--ledger', str(path), '--controller-session', '651362fa']) == 0
    payload = read_json(tmp_path / 'stats/experiment_usage.json')
    assert payload['schema'] == usage.SCHEMA and payload['telemetry']['channels'][0]['request_kind'] == 'embedding'
    # The written report carries the unknown row itself; the command's return
    # value summarizes it as a count so a caller can see it without parsing.
    assert [row['request_id'] for row in payload['ledgers'][0]['unknown_rows']] == ['bbbb']
    assert payload['ledgers'][0]['accounting_matches'] is True
    assert payload['controller']['available'] is False
    text = (tmp_path / 'stats/experiment_usage.md').read_text(encoding='utf8')
    assert '实验用量统计' in text and '不能按 0 计入' in text and '缓存读取（子项）' in text
    assert 'bbbb' in text and path.read_bytes() == before
