"""Explain invalid source audits using only their original normal packet.

Diagnostics supply literal source and actual schema, never a semantic decision,
replacement model, checker conditions or an acceptance assertion.
"""
import re
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from .semantic_backend import read_json, write_json
from .sources import fingerprint


def source_audit_hint(packet, error, previous_output=None):
    data = packet['input']
    match = re.search(r'record=([^;]+)', error)
    eid = match.group(1) if match else None
    exchange = next((e for e in data['normal_model']['exchanges'] if e['local_id'] == eid), None)
    if exchange is None and eid and eid.isdigit():
        scenes = data['normal_model'].get('normal_scenarios', [])
        exchange = scenes[int(eid)] if int(eid) < len(scenes) else None
    hint = 'Return the full original output contract. Do not change normal models or semantic decisions merely to pass validation. '
    if exchange:
        offending = []
        for kind in ('exchange_reviews', 'field_reviews', 'responsibility_reviews', 'contract_reviews'):
            for row in (previous_output or {}).get(kind, []):
                quote = row.get('evidence_quote')
                if row.get('local_exchange_id') == eid and isinstance(quote, str) and repr(quote) in error:
                    offending.append({'array': kind, 'exchange_id': eid, 'field': row.get('field'),
                        'service_type': row.get('service_type'), 'received_quote': quote})
        if offending:
            hint += 'Records using the rejected evidence: ' + repr(offending[:2]) + '. '
        if any(row['array'] == 'field_reviews' for row in offending):
            hint += 'Actual recorded transfer association (not a source approval): ' + repr({
                'return_description': exchange.get('return_description'),
                'request_fields': exchange.get('request_fields', []), 'response_fields': exchange.get('response_fields', []),
                'request_contracts': exchange.get('request_contracts', []), 'response_contracts': exchange.get('response_contracts', [])}) + '. '
            hint += 'For a success-guarantee response datum, quote an exact contiguous original transfer clause and verify its association with the recorded return or a reviewed positive bound contract. Different whole-sentence punctuation does not justify replacing original evidence with a paraphrase. If the transfer itself or its association is unsupported, preserve a concrete negative finding; do not fabricate a call, returned field or contract. '
        hint += 'Exchange and responsibility reviews need their own positive call/processing evidence. Return guarantees can support a returned datum in field_reviews, but cannot establish an initiating call or business responsibility. '
        refs = exchange['source_refs']
        candidates = [{'line_id': v['line_id'], 'literal_start': v['text'][:110],
            'literal_source': v['text'] if len(v['text']) <= 1600 else None,
            'literal_end': v['text'][-400:] if len(v['text']) > 1600 else ''}
            for v in data['normal_source_lines'] if v['requirement_layer'] == exchange['requirement_layer']
            and v.get('source_origin') in {'normal', 'trigger', 'ordinary_optional'}
            and any(r['document'] == v['source_refs'][0]['document']
                and r['line_start'] <= v['source_refs'][0]['line_start'] <= r['line_end'] for r in refs)]
        hint += 'Original own-layer positive clauses bound to this exchange (not asserted semantic support): ' + repr(candidates) + '. '
        hint += 'Coordinated operations can share one predicate. Copy an actual contiguous fragment or its full original line; do not repeat a verb before a later object if the source does not repeat it. This is a literal-source diagnostic, not support for the claimed operation. '
    elif 'source data' in error or 'source datum' in error:
        hint += 'One datum per original transferred value; evidence_quote is a literal fragment of that exact line, direction=request/response. mappings.field must exist in the actual field array. If absent, mappings=[] reports an omission, never invent a field or hide the original datum. '
        lines = {v['line_id']: v for v in data['normal_source_lines']}
        if 'independently inspect every original flow line' in error:
            received = [v.get('line_id') for v in (previous_output or {}).get('source_data_reviews', [])]
            missing = [key for key in lines if key not in received]
            hint += 'Source-data inventory mismatch: ' + repr({
                'expected_count': len(lines), 'received_count': len(received),
                'missing_line_ids': missing,
                'duplicate_line_ids': list(dict.fromkeys(key for key in received if received.count(key) > 1)),
                'unknown_line_ids': list(dict.fromkeys(key for key in received if key not in lines))}) + '. '
            hint += 'Missing original lines (no transferred-datum decision supplied): ' + repr([
                {'line_id': key, 'literal_source': lines[key]['text']} for key in missing]) + '. '
            hint += 'Inventory every assigned line once; a line with no transferred data still needs datums=[] and its original-source reason. This inventory correction supplies no semantic decision. '
        invalid = []
        for row in (previous_output or {}).get('source_data_reviews', []):
            line = lines.get(row.get('line_id'))
            if not line:
                continue
            seen = set()
            for datum in row.get('datums', []):
                quote = datum.get('evidence_quote')
                identity = repr((datum.get('direction'), datum.get('datum')))
                if (identity in seen or datum.get('direction') not in {'request', 'response'}
                        or not isinstance(quote, str) or not quote.strip() or quote not in line['text']
                        or '\n' in quote or '\r' in quote):
                    invalid.append({'line_id': row['line_id'], 'received_quote': quote,
                        'duplicate_identity': identity in seen,
                        'literal_source_start': line['text'][:150],
                        'literal_source_end': line['text'][-200:] if len(line['text']) > 150 else ''})
                seen.add(identity)
        if invalid:
            hint += 'Invalid literal/direction/duplicate records: ' + repr(invalid[:2]) + '. '
        if any(v['duplicate_identity'] for v in invalid):
            hint += 'A repeated direction/datum on one source line is one inventory record with mappings to all genuine transfers. Do not emit it repeatedly for separate exchanges; do not invent a renamed datum to evade uniqueness. '
    elif 'resource operation' in error:
        from .interaction_origins import explicit_exception_line
        nodes = {n['component_id']: n for n in data['normal_model'].get('components', [])}
        lines = {v['line_id']: v for v in data['normal_source_lines']}
        invalid = []
        for row in (previous_output or {}).get('resource_operation_reviews', []):
            seen = set()
            for op in row.get('operations', []):
                line = lines.get(op.get('line_id'))
                caller_id = op.get('caller_component_id')
                caller = nodes.get(caller_id)
                caller_name = op.get('caller_source_name')
                quote = op.get('evidence_quote')
                ids = op.get('local_exchange_ids')
                key = (op.get('line_id'), caller_id, caller_name, op.get('operation'))
                problems = []
                if key in seen:
                    problems.append('duplicate operation identity')
                if not line or line['requirement_layer'] != 'SR':
                    problems.append('missing/non-SR source line')
                elif line.get('source_origin') == 'abnormal' or explicit_exception_line(line['text']):
                    problems.append('abnormal source cannot create a positive call')
                if not isinstance(caller_id, str) or (caller_id and (not caller or caller['layer'] != 'SR')):
                    problems.append('unknown/non-SR caller ID')
                if data.get('resource_caller_source_required') or caller_id == '':
                    if (not isinstance(caller_name, str) or not caller_name.strip()
                            or not line or caller_name not in line['text']):
                        problems.append('caller_source_name is not a literal original caller')
                if caller_id == '' and ids:
                    problems.append('missing caller cannot claim modeled exchanges')
                if not isinstance(op.get('operation'), str) or not op['operation'].strip():
                    problems.append('missing operation')
                if not isinstance(quote, str) or not quote.strip() or not line or quote not in line['text']:
                    problems.append('quote is not an exact fragment of this source line')
                if not isinstance(ids, list) or len(ids) != len(set(ids)):
                    problems.append('missing/duplicate exchange ID list')
                if problems:
                    invalid.append({'resource': row.get('resource_component_id'), 'line_id': op.get('line_id'),
                        'claimed_caller': caller_id, 'caller_source_name': caller_name, 'received_quote': quote,
                        'schema_problems': problems, 'literal_source': line['text'] if line else None})
                seen.add(key)
        hint += 'Invalid resource inventory records: ' + repr(invalid[:2]) + '. '
        hint += 'Use actual SR component IDs for modeled callers, not service display names. A named original caller missing from the model keeps its literal caller_source_name, empty caller_component_id and local_exchange_ids=[]; never substitute another endpoint. Inventory each original operation once; distinct real instantiations belong in its local_exchange_ids. A missing call uses []. Coordinated operations share the original predicate: do not paraphrase or insert a repeated verb into an evidence quote. These facts do not certify the claimed caller or operation semantically. '
    elif 'normal graph decision needs explicit flags' in error or 'normal graph flags and defect reasons contradict' in error:
        invalid = []
        for kind, flag in [('line_reviews', 'covered'), ('exchange_reviews', 'supported'),
                ('scenario_reviews', 'supported'), ('field_reviews', 'supported'),
                ('responsibility_reviews', 'correctly_modeled'), ('contract_reviews', 'supported')]:
            for number, row in enumerate((previous_output or {}).get(kind, [])):
                value, issues = row.get(flag), row.get('issues')
                if type(value) is not bool or not isinstance(issues, list) or bool(issues) == value:
                    invalid.append({'array': kind, 'index': number, 'line_id': row.get('line_id'),
                        'exchange_id': row.get('local_exchange_id'), 'flag': flag, 'received_value': value,
                        'received_issues': issues})
        hint += 'Invalid decision records: ' + repr(invalid[:3]) + '. '
        hint += 'Every decision requires a boolean and issues list. True requires no defects; false requires a concrete defect. Re-read source to resolve a contradiction; never discard a real defect to make a flag pass. '
    elif 'resource coverage' in error:
        nodes = {n['component_id']: n for n in data['normal_model'].get('components', [])}
        exchanges = {e['local_id']: e for e in data['normal_model']['exchanges']}
        invalid = []
        for row in (previous_output or {}).get('resource_operation_reviews', []):
            rid = row.get('resource_component_id')
            for op in row.get('operations', []):
                for mapped in op.get('local_exchange_ids', []):
                    e = exchanges.get(mapped, {})
                    target = nodes.get(e.get('to_component_id'), {})
                    if e.get('from_component_id') != op.get('caller_component_id') or (target.get('component_id') != rid and target.get('physical_resource_id') != rid):
                        invalid.append({'line_id': op.get('line_id'), 'claimed_caller': op.get('caller_component_id'),
                            'resource': rid, 'mapped_id': mapped, 'actual_caller': e.get('from_component_id'),
                            'actual_callee': e.get('to_component_id')})
        hint += 'Incompatible claimed resource mappings: ' + repr(invalid[:2]) + '. Read the original clause to decide the actual caller; do not change a claim merely to agree with endpoints. A missing original call has local_exchange_ids=[]. '
    elif 'must inspect every assigned positive flow line exactly once' in error:
        expected = [v['line_id'] for v in data['normal_source_lines']]
        received = [v.get('line_id') for v in (previous_output or {}).get('line_reviews', [])]
        missing = [key for key in expected if key not in received]
        duplicates = list(dict.fromkeys(key for key in received if received.count(key) > 1))
        unknown = list(dict.fromkeys(key for key in received if key not in expected))
        lines = {v['line_id']: v for v in data['normal_source_lines']}
        hint += 'Line inventory mismatch: ' + repr({'expected_count': len(expected), 'received_count': len(received),
            'missing_line_ids': missing, 'duplicate_line_ids': duplicates, 'unknown_line_ids': unknown}) + '. '
        hint += 'Missing original lines (no classification decision supplied): ' + repr([
            {'line_id': key, 'literal_source': lines[key]['text']} for key in missing[:8]]) + '. '
        hint += 'Review every supplied line once, including context and excluded abnormal background. Coverage means accounted for, not converted into a request. Preserve real defects with negative flags; inventory repair cannot authorize an exchange or mark a semantic finding passed. '
    hint += 'Headings, pre/postconditions and another layer cannot prove an initiating request. Use only supplied source; preserve a genuine defect with a negative decision. '
    return error[:350] + '\n' + hint


def run_source_audit_diagnostics(args):
    from .interaction_model_audit import model_audit_packets, model_audit_validator
    root = Path(args.output_dir)
    folder = root/'batches/interaction-model-audit'
    if getattr(args, 'prepare_retry', False):
        from .interaction_worker_state import assert_stage_idle
        assert_stage_idle(folder, 'preparing source audit retry diagnostics')
    index = read_json(root/'sources_index.json')
    with TemporaryDirectory(prefix='scene-source-diagnostic-') as temporary:
        from .interaction_scope import selected_use_case_ids
        expected = model_audit_packets(root/'batches/interaction-model', index, temporary, use_case_ids=selected_use_case_ids(root))
    if read_json(folder/'manifest.json') != expected:
        raise ValueError('source audit diagnostic manifest differs from the current normal model and audit rule')
    validator = model_audit_validator(index)
    records = []
    for batch in read_json(folder/'manifest.json')['batches']:
        bid = batch['batch_id']
        packet = read_json(folder/'packets'/(bid+'.json'))
        if (folder/'results'/(bid+'.json')).exists():
            continue
        attempts = sorted((folder/'attempts').glob(bid+'-*.json'), key=lambda p: p.stat().st_mtime)
        structured = [(p, read_json(p)) for p in attempts]
        structured = [(p, a) for p, a in structured if isinstance(a.get('result'), dict)]
        if not structured:
            records.append({'batch_id': bid, 'status': 'no_structured_attempt'})
            continue
        path, attempt = structured[-1]
        raw = attempt['result']
        if raw.get('input_hash') != packet['input_hash'] or raw.get('batch_id') != bid:
            raise ValueError('source audit diagnostic is stale or belongs to another packet')
        try:
            validator(packet, deepcopy(raw))
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
        else:
            raise ValueError('valid source audit cannot be labeled invalid')
        hint = source_audit_hint(packet, error, raw)
        row = {'batch_id': bid, 'status': 'invalid_output', 'input_hash': packet['input_hash'],
            'original_attempt': str(path), 'original_result_hash': fingerprint(raw),
            'validation_error': error, 'retry_hint': hint, 'semantic_decision_supplied': False}
        if getattr(args, 'prepare_retry', False):
            target = folder/'attempts'/(bid+'-source-diagnostic-'+uuid4().hex+'.json')
            write_json(target, {'result': raw, 'validation_error': hint, 'attempt': 0,
                'diagnostic_source_attempt': str(path), 'diagnostic_tool_hash': fingerprint(Path(__file__).read_text(encoding='utf-8'))})
            row['retry_feedback_file'] = str(target)
        records.append(row)
    report = {'source_only': True, 'semantic_decision_supplied': False, 'findings': records}
    write_json(root/'normal_source_audit_diagnostics.json', report)
    return report, 2 if records else 0


def run_source_audit_retry(args):
    import json
    from .interaction_source_review import source_audit_review_feedback
    from .interaction_model_audit import model_audit_packets, model_audit_validator
    from .role_cli import _client
    from .semantic_backend import run_agent_packets
    root = Path(args.output_dir)
    if (root/'generated_scenarios.json').exists():
        raise ValueError('G already exists; source judgment changes require a new documented round')
    folder = root/'batches/interaction-model-audit'
    from .interaction_worker_state import assert_stage_idle
    assert_stage_idle(folder, 'retrying selected source judgments')
    assert_stage_idle(root/'batches/interaction-model', 'retrying source judgments against the normal model')
    index, model = read_json(root/'sources_index.json'), read_json(root/'scene_model.json')
    with TemporaryDirectory(prefix='scene-source-review-retry-') as temporary:
        from .interaction_scope import selected_use_case_ids
        expected = model_audit_packets(root/'batches/interaction-model', index, temporary, use_case_ids=selected_use_case_ids(root))
    if read_json(folder/'manifest.json') != expected:
        raise ValueError('source-audit retry requires current normal-model/audit packets')
    feedback = source_audit_review_feedback(args.source_review_file, model, index, folder, args.source_finding_id)
    client = _client(args, root)
    from .interaction_execution_identity import validate_client_execution_model
    validate_client_execution_model(client)
    before = fingerprint(model)
    for bid, findings in feedback.items():
        raw = read_json(folder/'results'/(bid+'.json'))
        write_json(folder/'attempts'/(bid+'-source-review-'+uuid4().hex+'.json'), {
            'result': raw, 'validation_error': 'Re-audit these selected source-only judgment errors; normal model unchanged. '
                + json.dumps(findings, ensure_ascii=False), 'attempt': 0, 'source_only_review_feedback': findings})
        (folder/'results'/(bid+'.json')).unlink()
    state = run_agent_packets(folder, client, model_audit_validator(index), batch_ids=sorted(feedback))
    from .interaction_execution_identity import validate_result_execution
    for bid in feedback:
        result_path = folder / 'results' / (bid + '.json')
        if result_path.is_file():
            validate_result_execution(read_json(result_path), result_path=result_path)
    if fingerprint(read_json(root/'scene_model.json')) != before:
        raise ValueError('normal model changed during source-audit judgment retry')
    return {'normal_model_unchanged': True, 'retried_source_audit_ids': sorted(feedback),
        'worker_result': state, 'note': 'Recollect the complete original source audit; this retry alone is not acceptance.'}, 2
