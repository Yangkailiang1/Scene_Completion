"""Experiment-scoped usage accounting across ledgers, run telemetry and the controller proxy log.

Everything here is read-only: a ledger row is never re-settled, a budget is
never widened, and a request whose provider report never arrived stays
``unknown`` instead of being counted as zero.  The three channels are kept
apart because they measure different things (reserved-and-settled model quota,
per-request telemetry, and the controller's own proxy log) and because wall
clock, API time and parallel overlap are separate scales.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .semantic_backend import read_json, write_json

SCHEMA = 'scene-experiment-usage-v1'
UNSETTLED_STATUSES = ('usage_unknown',)
# The controller channel is read read-only from the cc-switch proxy log, and
# only through this column list: model, status, latency, token counts and time.
# Provider configuration and request parameters are never selected.
CONTROLLER_COLUMNS = ('session_id', 'model', 'status_code', 'latency_ms', 'input_tokens',
    'output_tokens', 'cache_read_tokens', 'created_at')
CONTROLLER_QUERY = 'SELECT ' + ', '.join(CONTROLLER_COLUMNS) + ' FROM proxy_request_logs ORDER BY created_at'


def _number(value):
    return value if type(value) in (int, float) else 0


def _iso(seconds):
    return None if seconds is None else datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def ledger_summary(path):
    """Summarize one semantic token ledger exactly as the ledger accounts for it."""
    path = Path(path)
    if not path.exists():
        return {'file': str(path), 'available': False, 'note': 'ledger file not found'}
    payload = read_json(path)
    rows = payload.get('requests') or {}
    if not isinstance(rows, dict):
        raise ValueError(f'{path.name}: semantic-token-budget requests must be keyed by request id')
    statuses = Counter(row.get('status') for row in rows.values())
    charged = sum(_number(row.get('charged_tokens')) for row in rows.values() if row.get('status') == 'complete')
    reported = sum(_number(row.get('reported_total_tokens')) for row in rows.values() if row.get('status') == 'complete')
    unknown = [{'request_id': request_id, 'model': row.get('model'), 'status': row.get('status'),
        'reservation': _number(row.get('reservation')), 'started_at': _iso(row.get('started_unix')),
        'finished_at': _iso(row.get('finished_unix'))}
        for request_id, row in rows.items() if row.get('status') in UNSETTLED_STATUSES]
    refused = [{'request_id': request_id, 'model': row.get('model'),
        'released_reservation': _number(row.get('reservation'))}
        for request_id, row in rows.items() if row.get('status') == 'refused']
    held = sum(row['reservation'] for row in unknown)
    committed = payload.get('committed_tokens')
    return {'file': str(path), 'available': True, 'schema': payload.get('schema'),
        'limit': payload.get('limit'), 'committed_tokens': committed,
        'reserved_tokens': payload.get('reserved_tokens'), 'remaining_tokens': payload.get('remaining_tokens'),
        'requests': len(rows), 'rows_by_status': dict(sorted(statuses.items())),
        'models': dict(sorted(Counter(row.get('model') for row in rows.values()).items(), key=lambda p: str(p[0]))),
        'charged_tokens': charged, 'reported_total_tokens': reported,
        # A row whose provider report never arrived still holds its whole
        # reservation; that is why committed_tokens is charged + held and why
        # this tool refuses to guess what the request actually cost.
        'held_unknown_tokens': held, 'accounting_matches': committed == charged + held,
        'unknown_rows': unknown, 'refused_rows': refused,
        'released_refused_tokens': sum(row['released_reservation'] for row in refused),
        'note': 'Committed quota is charged-complete plus every reservation still held by an unknown report. '
            'Unknown rows are listed and never counted as zero; this tool cannot settle them.'}


def telemetry_summary(run_dir):
    """Aggregate per-request telemetry, keeping cache and reasoning as sub-items."""
    path = Path(run_dir) / 'performance_events.jsonl'
    if not path.exists():
        return {'file': str(path), 'available': False, 'note': 'run telemetry not found'}
    channels = {}
    stage_models = {}
    for line in path.read_text(encoding='utf8').splitlines():
        if not line:
            continue
        event = json.loads(line)
        if event.get('kind') != 'request':
            continue
        kind = event.get('request_kind', 'unknown')
        stage = event.get('stage') or 'unknown'
        phase = event.get('phase') or 'unknown'
        model = event.get('model') or 'unknown'
        channel = channels.setdefault(kind, {'requests': 0, 'statuses': Counter(), 'models': Counter(),
            'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0, 'cache_read_tokens': 0,
            'reasoning_tokens': 0, 'unknown_usage_requests': 0, 'unknown_transport_attempts': 0,
            'failed_requests': 0, 'api_seconds': 0.})
        detail = stage_models.setdefault((str(stage), str(phase), str(model)), {
            'stage': str(stage), 'phase': str(phase), 'model': str(model), 'requests': 0,
            'statuses': Counter(), 'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0,
            'unknown_usage_requests': 0, 'partial_usage_requests': 0,
            'missing_usage_fields': Counter(), 'failed_requests': 0, 'api_seconds': 0.,
            'unknown_duration_requests': 0})
        channel['requests'] += 1
        channel['statuses'][event.get('status')] += 1
        channel['models'][event.get('model')] += 1
        channel['api_seconds'] += _number(event.get('duration_seconds'))
        channel['failed_requests'] += event.get('status') == 'failed'
        detail['requests'] += 1
        detail['statuses'][event.get('status')] += 1
        detail['api_seconds'] += _number(event.get('duration_seconds'))
        if type(event.get('duration_seconds')) not in (int, float):
            detail['unknown_duration_requests'] += 1
        detail['failed_requests'] += event.get('status') == 'failed'
        if not isinstance(event.get('transport_attempts'), int):
            channel['unknown_transport_attempts'] += 1
        usage = event.get('usage')
        if not isinstance(usage, dict) or not usage:
            # No provider report: the tokens are unknown, not zero.
            channel['unknown_usage_requests'] += 1
            detail['unknown_usage_requests'] += 1
            continue
        missing = [field for field in ('prompt_tokens', 'completion_tokens', 'total_tokens')
            if type(usage.get(field)) not in (int, float)]
        if missing:
            detail['partial_usage_requests'] += 1
            detail['missing_usage_fields'].update(missing)
        channel['input_tokens'] += _number(usage.get('prompt_tokens'))
        channel['output_tokens'] += _number(usage.get('completion_tokens'))
        channel['total_tokens'] += _number(usage.get('total_tokens'))
        channel['cache_read_tokens'] += _number((usage.get('prompt_tokens_details') or {}).get('cached_tokens'))
        details = usage.get('completion_tokens_details') or {}
        channel['reasoning_tokens'] += _number(details.get('reasoning_tokens', usage.get('reasoning_tokens')))
        detail['input_tokens'] += _number(usage.get('prompt_tokens'))
        detail['output_tokens'] += _number(usage.get('completion_tokens'))
        detail['total_tokens'] += _number(usage.get('total_tokens'))
    for kind, channel in channels.items():
        channel['request_kind'] = kind
        channel['statuses'] = dict(sorted((str(k), v) for k, v in channel['statuses'].items()))
        channel['models'] = dict(sorted((str(k), v) for k, v in channel['models'].items()))
        channel['request_seconds_reported'] = round(channel.pop('api_seconds'), 3)
    detailed = []
    for key in sorted(stage_models):
        detail = stage_models[key]
        detail['statuses'] = dict(sorted((str(k), v) for k, v in detail['statuses'].items()))
        detail['missing_usage_fields'] = dict(sorted(detail['missing_usage_fields'].items()))
        detail['request_seconds_reported'] = round(detail.pop('api_seconds'), 3)
        detailed.append(detail)
    repair_models = {}
    for detail in detailed:
        if detail['phase'] != 'repair':
            continue
        repair = repair_models.setdefault(detail['model'], {'model': detail['model'], 'requests': 0,
            'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0,
            'unknown_usage_requests': 0, 'partial_usage_requests': 0,
            'request_seconds_reported': 0., 'unknown_duration_requests': 0})
        for field in ('requests', 'input_tokens', 'output_tokens', 'total_tokens',
                'unknown_usage_requests', 'partial_usage_requests', 'unknown_duration_requests'):
            repair[field] += detail[field]
        repair['request_seconds_reported'] += detail['request_seconds_reported']
    for repair in repair_models.values():
        repair['request_seconds_reported'] = round(repair['request_seconds_reported'], 3)
    return {'file': str(path), 'available': True,
        'channels': [channels[kind] for kind in sorted(channels)],
        'stage_models': detailed, 'repair_costs': [repair_models[model] for model in sorted(repair_models)],
        'sub_items': {'cache_read_tokens': 'subset of input_tokens as the provider reports it',
            'reasoning_tokens': 'subset of output_tokens as the provider reports it'},
        'note': 'Provider-reported usage only. Cache-read and reasoning tokens are sub-items of the input and '
            'output columns and must not be added on top of them. Stage rows and request-kind channels are two '
            'views of the same requests and must not be added together. Request seconds are summed API durations, '
            'not pipeline wall-clock time; repair costs sum only phase=repair rows and are a subset of stage rows.'}


def controller_summary(db_path, include_sessions=(), exclude_sessions=()):
    """Aggregate the controller's own proxy log within the experiment's sessions."""
    db_path = Path(db_path)
    if not db_path.exists():
        return {'available': False, 'file': str(db_path), 'note': 'controller proxy log not found'}
    connection = sqlite3.connect('file:%s?mode=ro' % quote(str(db_path.resolve())), uri=True)
    try:
        rows = connection.execute(CONTROLLER_QUERY).fetchall()
    finally:
        connection.close()
    sessions = {}
    for session, model, status, latency, input_tokens, output_tokens, cache_read, created_at in rows:
        session = str(session)
        if include_sessions and not any(session.startswith(prefix) for prefix in include_sessions):
            continue
        if any(session.startswith(prefix) for prefix in exclude_sessions):
            continue
        entry = sessions.setdefault(session, {'session': session, 'requests': 0, 'models': Counter(),
            'statuses': Counter(), 'input_tokens': 0, 'output_tokens': 0, 'cache_read_tokens': 0,
            'latency_seconds': 0., 'requests_missing_latency': 0, 'unknown_token_requests': 0, 'first_at': None, 'last_at': None})
        entry['requests'] += 1
        entry['models'][model] += 1
        entry['statuses'][str(status)] += 1
        entry['input_tokens'] += _number(input_tokens)
        entry['output_tokens'] += _number(output_tokens)
        entry['cache_read_tokens'] += _number(cache_read)
        if input_tokens is None or output_tokens is None or input_tokens == 0 and output_tokens == 0:
            entry['unknown_token_requests'] += 1
        if latency is None:
            entry['requests_missing_latency'] += 1
        else:
            entry['latency_seconds'] += _number(latency) / 1000.
        if created_at is not None:
            entry['first_at'] = created_at if entry['first_at'] is None else min(entry['first_at'], created_at)
            entry['last_at'] = created_at if entry['last_at'] is None else max(entry['last_at'], created_at)
    ordered = []
    for session in sorted(sessions):
        entry = sessions[session]
        entry['models'] = dict(sorted((str(k), v) for k, v in entry['models'].items()))
        entry['statuses'] = dict(sorted(entry['statuses'].items()))
        entry['latency_seconds_reported'] = round(entry.pop('latency_seconds'), 3)
        entry['window'] = [_iso(entry.pop('first_at')), _iso(entry.pop('last_at'))]
        ordered.append(entry)
    totals = {key: sum(entry[key] for entry in ordered)
        for key in ('requests', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'requests_missing_latency', 'unknown_token_requests')}
    totals['latency_seconds_reported'] = round(sum(entry['latency_seconds_reported'] for entry in ordered), 3)
    return {'available': True, 'file': str(db_path), 'table': 'proxy_request_logs',
        'columns_read': list(CONTROLLER_COLUMNS), 'included_sessions': list(include_sessions),
        'excluded_sessions': list(exclude_sessions), 'sessions': ordered, 'totals': totals,
        'note': 'Controller usage read read-only from the controller proxy log, restricted to the listed columns; '
            'provider configuration and request parameters were not read. Cache-read tokens are a sub-item of the '
            'input column. This latency is the proxy\'s own measurement and is not the pipeline request time.'}


def time_summary(run_dir):
    """Carry over wall clock, busy and overlap seconds without collapsing them."""
    path = Path(run_dir) / 'performance.json'
    if not path.exists():
        return {'available': False, 'file': str(path), 'note': 'performance.json not found; rerun with --profile'}
    payload = read_json(path)
    spans = [{'session': session.get('session'), 'wall_seconds': session.get('wall_seconds'),
        'task_seconds': session.get('task_seconds'), 'task_busy_seconds': session.get('task_busy_seconds'),
        'task_overlap_seconds': session.get('task_overlap_seconds'), 'request_seconds': session.get('request_seconds'),
        'unknown_usage_requests': session.get('unknown_usage_requests', 0),
        'unfinished_request_count': session.get('unfinished_request_count', 0)}
        for session in payload.get('sessions', [])]
    return {'available': True, 'file': str(path), 'sessions': spans,
        'note': 'Wall clock, API request time and parallel overlap are separate scales and are never added '
            'together. Requests still open at the last record have unknown time and usage.'}


def local_dir(path, allow_any=False):
    """Keep experiment statistics local unless the caller explicitly opts out."""
    target = Path(path).resolve()
    if allow_any or 'tmp' in target.parts or Path(tempfile.gettempdir()).resolve() in target.parents:
        return target
    raise ValueError('experiment usage statistics are local-only; write under a tmp directory '
        'or pass --allow-any-output-dir')


def collect(*, run_dir=None, ledgers=(), controller_db=None, include_sessions=(), exclude_sessions=()):
    payload = {'schema': SCHEMA,
        'scope': {'run_dir': str(Path(run_dir).resolve()) if run_dir else None,
            'note': 'Scoped workflow run; failed, repaired, pre-checked, controller, fallback, embedding '
                'and review calls are all included. Values reported as unknown stay unknown.'},
        'ledgers': [ledger_summary(path) for path in ledgers],
        'telemetry': telemetry_summary(run_dir) if run_dir else {'available': False},
        'controller': (controller_summary(controller_db, include_sessions, exclude_sessions)
            if controller_db else {'available': False, 'note': 'no controller proxy log configured'}),
        'time': time_summary(run_dir) if run_dir else {'available': False}}
    return payload


def render(payload):
    lines = ['# 实验用量统计', '',
        '本文件只读账本、运行遥测和主控代理日志，不重结算、不提额、不把未返回的用量记作零。', '']
    for ledger in payload['ledgers']:
        lines += [f"## 账本 {Path(ledger['file']).name}", '']
        if not ledger.get('available'):
            lines += [ledger.get('note', '账本不可读'), '']; continue
        lines += [f"上限 {ledger['limit']}；已提交 {ledger['committed_tokens']}；保留 {ledger['reserved_tokens']}；"
            f"剩余 {ledger['remaining_tokens']}；请求 {ledger['requests']}；状态分布 {json.dumps(ledger['rows_by_status'], ensure_ascii=False)}",
            f"已结算用量合计 {ledger['reported_total_tokens']}（按行计费 {ledger['charged_tokens']}）；"
            f"未结算报告占用的额度 {ledger['held_unknown_tokens']}；账本口径一致：{ledger['accounting_matches']}",
            f"被拒绝而未占用额度的请求 {len(ledger['refused_rows'])}（释放 {ledger['released_refused_tokens']}）", '']
        for row in ledger['unknown_rows']:
            lines.append(f"- 用量未知 {row['request_id']}（{row['model']}，占用 {row['reservation']}，"
                f"开始 {row['started_at']}，结束 {row['finished_at']}）：不能按 0 计入")
        if ledger['unknown_rows']:
            lines.append('')
    telemetry = payload['telemetry']
    lines += ['## 运行遥测（provider 返回）', '']
    if not telemetry.get('available'):
        lines += [telemetry.get('note', '遥测不可读'), '']
    else:
        lines += ['| 通道 | 请求 | 状态 | 模型 | 输入 tokens | 输出 tokens | 合计 | 缓存读取（子项） | 推理（子项） | 未返回用量 | 已记录请求秒 |',
            '|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for channel in telemetry['channels']:
            lines.append(f"| {channel['request_kind']} | {channel['requests']} | "
                f"{json.dumps(channel['statuses'], ensure_ascii=False)} | {json.dumps(channel['models'], ensure_ascii=False)} | "
                f"{channel['input_tokens']} | {channel['output_tokens']} | {channel['total_tokens']} | "
                f"{channel['cache_read_tokens']} | {channel['reasoning_tokens']} | {channel['unknown_usage_requests']} | "
                f"{channel['request_seconds_reported']} |")
        lines += ['', telemetry['note'], '']
        lines += ['### 阶段 / phase / model（同一请求的分组明细）', '',
            '| Stage | Phase | Model | 请求 | 状态 | 输入 tokens | 输出 tokens | 总 tokens | 用量未知请求 | 部分用量请求 | API 请求秒 | 时间未知请求 |',
            '|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|']
        for detail in telemetry.get('stage_models', []):
            lines.append(f"| {detail['stage']} | {detail['phase']} | {detail['model']} | {detail['requests']} | "
                f"{json.dumps(detail['statuses'], ensure_ascii=False)} | {detail['input_tokens']} | "
                f"{detail['output_tokens']} | {detail['total_tokens']} | {detail['unknown_usage_requests']} | "
                f"{detail['partial_usage_requests']} | {detail['request_seconds_reported']} | "
                f"{detail['unknown_duration_requests']} |")
        lines += ['', '修复请求成本（phase=repair，已包含在上表中）：', '']
        if telemetry.get('repair_costs'):
            lines += ['| Model | 请求 | 输入 tokens | 输出 tokens | 总 tokens | 未知用量 | 部分用量 | API 请求秒 | 时间未知请求 |',
                '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
            for repair in telemetry['repair_costs']:
                lines.append(f"| {repair['model']} | {repair['requests']} | {repair['input_tokens']} | "
                    f"{repair['output_tokens']} | {repair['total_tokens']} | {repair['unknown_usage_requests']} | "
                    f"{repair['partial_usage_requests']} | {repair['request_seconds_reported']} | "
                    f"{repair['unknown_duration_requests']} |")
        else:
            lines.append('没有 phase=repair 的请求。')
        lines += ['', '请求秒是 API duration 的合计，不代表墙钟耗时；具体运行墙钟见下方时间口径。', '']
    controller = payload['controller']
    lines += ['## 主控渠道（只读代理日志）', '']
    if not controller.get('available'):
        lines += [controller.get('note', '主控用量不可读'), '']
    else:
        lines += [f"读取列：{', '.join(controller['columns_read'])}；纳入会话 {controller['included_sessions']}；"
            f"排除会话 {controller['excluded_sessions']}", '',
            '| 会话 | 请求 | 模型 | 状态 | 输入 tokens | 输出 tokens | 缓存读取（子项） | 已记录延迟秒 | 缺延迟 | 时间窗 |',
            '|---|---:|---|---|---:|---:|---:|---:|---:|---|']
        for session in controller['sessions']:
            lines.append(f"| {session['session']} | {session['requests']} | {json.dumps(session['models'], ensure_ascii=False)} | "
                f"{json.dumps(session['statuses'], ensure_ascii=False)} | {session['input_tokens']} | {session['output_tokens']} | "
                f"{session['cache_read_tokens']} | {session['latency_seconds_reported']} | {session['requests_missing_latency']} | "
                f"{session['window'][0]} → {session['window'][1]} |")
        totals = controller['totals']
        lines += ['', f"合计：请求 {totals['requests']}；输入 {totals['input_tokens']}；输出 {totals['output_tokens']}；"
            f"缓存读取 {totals['cache_read_tokens']}；缺少延迟 {totals['requests_missing_latency']}", '', controller['note'], '']
    time = payload['time']
    lines += ['## 时间口径', '']
    if not time.get('available'):
        lines += [time.get('note', '时间记录不可读'), '']
    else:
        lines += ['| 运行 | 墙钟秒 | 任务秒 | 并行去重后任务秒 | 并行重叠秒 | 请求秒 | 未返回用量 | 未结束请求 |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
        for span in time['sessions']:
            wall = '未结束' if span['wall_seconds'] is None else f"{span['wall_seconds']:.2f}"
            lines.append(f"| {span['session']} | {wall} | {span['task_seconds']:.2f} | {span['task_busy_seconds']:.2f} | "
                f"{span['task_overlap_seconds']:.2f} | {span['request_seconds']:.2f} | {span['unknown_usage_requests']} | "
                f"{span['unfinished_request_count']} |")
        lines += ['', time['note'], '']
    return '\n'.join(lines)


def run(args):
    output_dir = local_dir(args.output_dir, getattr(args, 'allow_any_output_dir', False))
    payload = collect(run_dir=getattr(args, 'run_dir', None), ledgers=getattr(args, 'ledger', None) or [],
        controller_db=getattr(args, 'controller_db', None),
        include_sessions=getattr(args, 'controller_session', None) or [],
        exclude_sessions=getattr(args, 'exclude_controller_session', None) or [])
    write_json(output_dir / 'experiment_usage.json', payload)
    (output_dir / 'experiment_usage.md').write_text(render(payload), encoding='utf8')
    unknown = [row for ledger in payload['ledgers'] if ledger.get('available') for row in ledger['unknown_rows']]
    result = {'schema': SCHEMA, 'output_dir': str(output_dir),
        'files': [str(output_dir / 'experiment_usage.json'), str(output_dir / 'experiment_usage.md')],
        'ledgers': [{'file': ledger['file'], 'available': ledger['available'],
            'committed_tokens': ledger.get('committed_tokens'), 'remaining_tokens': ledger.get('remaining_tokens'),
            'rows_by_status': ledger.get('rows_by_status'), 'unknown_rows': len(ledger.get('unknown_rows', []))}
            for ledger in payload['ledgers']],
        'unknown_usage_rows': unknown,
        'telemetry_channels': [channel['request_kind'] for channel in payload['telemetry'].get('channels', [])],
        'telemetry_stage_models': [{'stage': row['stage'], 'phase': row['phase'], 'model': row['model'],
            'requests': row['requests'], 'input_tokens': row['input_tokens'],
            'output_tokens': row['output_tokens'], 'total_tokens': row['total_tokens'],
            'unknown_usage_requests': row['unknown_usage_requests'],
            'request_seconds_reported': row['request_seconds_reported']}
            for row in payload['telemetry'].get('stage_models', [])],
        'telemetry_repair_costs': payload['telemetry'].get('repair_costs', []),
        'controller_sessions': [session['session'] for session in payload['controller'].get('sessions', [])]}
    return result, 0
