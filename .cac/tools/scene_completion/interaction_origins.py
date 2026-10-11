"""Check normal SSD origins using document structure, never exception matching.

This detects extraction errors, not applicability of generated exceptions.
Unrecognized document templates produce an explicit model-evidence gap.
"""
import re
from pathlib import Path
from uuid import uuid4

from .sources import fingerprint


def line_origins(text):
    role, roles = 'context', {}
    normal = re.compile(r'^(主成功路径|基本流程|主流程|Main success path|Basic flow|Normal flow)\s*[:：]?$', re.I)
    branches = re.compile(r'^(扩展路径|扩展流程|备选流程|替代流程|Alternative flows?|Extensions?)\s*[:：]?$', re.I)
    for number, line in enumerate(text.splitlines(), 1):
        title = re.sub(r'^\s*(?:#{1,6}\s*|\d+[.、)]\s*)?', '', line).strip()
        if normal.fullmatch(title):
            role = 'normal'
        elif branches.fullmatch(title):
            role = 'branch'
        elif re.fullmatch(r'(前置条件|Preconditions?)\s*[:：]?', title, re.I):
            role = 'precondition'
        elif line.lstrip().startswith('#'):
            role = 'context'
        if role == 'branch':
            # Only explicitly ordinary optional branches may form normal SSD
            # exchanges; failures and their fallback returns remain context.
            optional = bool(re.search(r'(?:可选场景|普通可选|optional\s+(?:scenario|flow))', line, re.I))
            roles[number] = 'ordinary_optional' if optional else 'branch'
        else:
            roles[number] = role
    return roles


def explicit_exception_line(text):
    """Normal-model guard; independent checker origin rules remain unchanged."""
    return bool(re.search(r'(?:异常场景|异常流程|exception\s+(?:scenario|flow))', text, re.I))


def normal_model_line_origins(text):
    """Include initiating events, without changing independent C branch rules."""
    roles = line_origins(text)
    trigger = False
    heading_scopes = []
    abnormal_branch = False
    abnormal_branch_depth = 0
    for number, line in enumerate(text.splitlines(), 1):
        title = re.sub(r'^\s*(?:#{1,6}\s*|\d+[.、)]\s*)?', '', line).strip()
        heading = re.match(r'^\s*(#{1,6})\s+(.+)', line)
        if heading:
            depth = len(heading[1])
            new_numbered_branch = bool(re.match(r'^(?:\d+[.．][A-Za-z]|[Aa]\d+)\s*[:：.]?', heading[2]))
            if depth <= abnormal_branch_depth or new_numbered_branch:
                abnormal_branch = False
            while heading_scopes and heading_scopes[-1][0] >= depth:
                heading_scopes.pop()
            inherited = heading_scopes[-1][1] if heading_scopes else None
            kind = 'abnormal' if inherited == 'abnormal' or abnormal_branch or explicit_exception_line(heading[2]) else (
                'optional_branch' if new_numbered_branch or re.search(r'可选场景|普通可选|optional\s+(?:scenario|flow)', heading[2], re.I) else inherited)
            heading_scopes.append((depth, kind))
        if re.fullmatch(r'(主成功路径|基本流程|主流程|Main success path|Basic flow|Normal flow|扩展路径|扩展流程|备选流程|替代流程|Alternative flows?|Extensions?)\s*[:：]?', title, re.I):
            abnormal_branch = False
            roles[number] = 'context'  # A flow title cannot prove an actual call.
        elif not heading:
            scope = heading_scopes[-1][1] if heading_scopes else None
            if scope == 'optional_branch' and roles[number] == 'context':
                roles[number] = 'branch'  # Body needs actual optional source review.
            if re.match(r'^\s*(?:[-*]\s*)?(?:\d+[.．][A-Za-z]|[Aa]\d+)\s*[:：.]?', line) or re.search(r'可选场景|普通可选|optional\s+(?:scenario|flow)', line, re.I):
                abnormal_branch = False
            if explicit_exception_line(line):
                abnormal_branch = True
                abnormal_branch_depth = heading_scopes[-1][0] if heading_scopes else 1
            if scope == 'abnormal' or abnormal_branch:
                roles[number] = 'abnormal'
        if heading:
            roles[number] = 'context'
        if re.fullmatch(r'(触发事件|触发条件|Trigger(?:ing)?(?: events?| conditions?)?)\s*[:：]?', title, re.I):
            trigger = True
            roles[number] = 'context'
        elif trigger and (line.lstrip().startswith('#') or re.match(r'^\s*\d+[.、)]\s*[^\n]+[:：]\s*$', line)):
            trigger = False
        elif trigger and line.strip() and roles[number] != 'abnormal':
            roles[number] = 'trigger'
    return roles


def audit_model_origins(model, index, semantic_reviews=None):
    documents = {d['document']: d for d in index['documents']}
    origins = {name: normal_model_line_origins(d['text']) for name, d in documents.items()}
    checks = []
    reviewed = {r['use_case_id']: r for r in semantic_reviews or []}
    for uc in model['use_cases']:
        for exchange in uc['exchanges']:
            refs = exchange['source_refs']
            own = [r for r in refs if documents[r['document']]['requirement_layer'] == exchange['requirement_layer']]
            evidence = [{'document': r['document'], 'line': n, 'role': origins[r['document']][n],
                'text': documents[r['document']]['text'].splitlines()[n - 1]}
                for r in own for n in range(r['line_start'], r['line_end'] + 1)]
            allowed = {'normal', 'trigger'} if exchange['path_type'] == 'main_success' else {'normal', 'trigger', 'ordinary_optional'}
            supported = any(v['role'] in allowed and not explicit_exception_line(v['text']) for v in evidence)
            needs_semantic = not supported and exchange['path_type'] == 'alternative' and any(v['role'] == 'branch' and not explicit_exception_line(v['text']) for v in evidence)
            proof = reviewed.get(uc['use_case_id'], {})
            if needs_semantic and proof.get('passed'):
                supported = any(r['local_exchange_id'] == exchange['local_id'] and r['supported'] for r in proof['exchange_reviews'])
            checks.append({'use_case_id': uc['use_case_id'], 'local_exchange_id': exchange['local_id'],
                'requirement_layer': exchange['requirement_layer'], 'operation': exchange['operation'],
                'passed': supported, 'needs_semantic_branch_review': needs_semantic, 'evidence': evidence,
                'reason': '' if supported else 'No original normal/ordinary-optional flow evidence from this layer; participants, contracts, other-layer steps or failure fallback alone do not establish an initiating SSD exchange'})
        for position, scene in enumerate(uc.get('normal_scenarios', [])):
            evidence = [{'document': r['document'], 'line': n, 'role': origins[r['document']][n],
                'text': documents[r['document']]['text'].splitlines()[n - 1]}
                for r in scene['source_refs'] if documents[r['document']]['requirement_layer'] == scene['requirement_layer']
                for n in range(r['line_start'], r['line_end'] + 1)]
            allowed = {'normal', 'trigger'} if scene['scenario_type'] == 'main_success' else {'normal', 'trigger', 'ordinary_optional'}
            supported = any(v['role'] in allowed and not explicit_exception_line(v['text']) for v in evidence)
            needs_semantic = not supported and scene['scenario_type'] == 'alternative' and any(v['role'] == 'branch' and not explicit_exception_line(v['text']) for v in evidence)
            proof = reviewed.get(uc['use_case_id'], {})
            if needs_semantic and proof.get('passed'):
                supported = any(r['scenario_index'] == position and r['supported'] for r in proof['scenario_reviews'])
            checks.append({'use_case_id': uc['use_case_id'], 'local_exchange_id': f'NORMAL-{position}',
                'normal_scenario_index': position, 'requirement_layer': scene['requirement_layer'], 'operation': scene['name'],
                'passed': supported, 'needs_semantic_branch_review': needs_semantic, 'evidence': evidence,
                'reason': '' if supported else 'Normal/ordinary-optional scenario cites only context, preconditions or abnormal branches; correctly handled exceptions are still exceptions'})
    return {'model_hash': fingerprint(model), 'source_hash': fingerprint(index),
        'rule_hash': fingerprint(Path(__file__).read_text(encoding='utf-8')),
        'semantic_audit_hash': fingerprint(semantic_reviews) if semantic_reviews is not None else None,
        'passed': all(c['passed'] for c in checks), 'checks': checks}


def run_model_repair(args):
    """Re-extract unsupported normal graphs; never read G/C/test conditions."""
    from . import interaction_batches as b
    from .interaction_cli import merge_model
    from .role_cli import _client
    from .semantic_backend import read_json, write_json, collect_packets, run_agent_packets
    root = Path(args.output_dir)
    from .interaction_worker_state import assert_stage_idle
    assert_stage_idle(root/'batches/interaction-model', 'repairing normal model sources')
    assert_stage_idle(root/'batches/interaction-model-audit', 'repairing the model being source audited')
    if (root / 'generated_scenarios.json').exists():
        raise ValueError('G already exists; repair normal model in a new documented round')
    index = read_json(root / 'sources_index.json')
    base = read_json(root / 'generator_base_identity.json')
    folder = root / 'batches/interaction-model'
    validator = b.model_validator(index)
    values, status = collect_packets(folder, validator)
    if not status['complete']:
        raise ValueError('normal-origin repair requires complete structurally valid extraction')
    from .interaction_scope import selected_use_case_ids, select_cases, assessment_base
    selected_scope = selected_use_case_ids(root)
    model = merge_model(select_cases(values, selected_scope), assessment_base(base, selected_scope), index)
    audit = audit_model_origins(model, index)
    semantic_failures = {}
    native_failures = {}
    review_path = getattr(args, 'source_review_file', None)
    selected_findings = getattr(args, 'source_finding_id', None)
    if bool(review_path) != bool(selected_findings):
        raise ValueError('source-only repair requires both a review file and explicit finding selection')
    if review_path:
        from .interaction_source_review import source_review_feedback
        native_failures = source_review_feedback(review_path, model, index, folder, selected_findings)
    review_folder = root / 'batches/interaction-model-audit'
    if (review_folder / 'manifest.json').exists():
        from .interaction_model_audit import model_audit_packets, model_audit_validator
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(prefix='scene-normal-repair-') as temporary:
            expected = model_audit_packets(folder, index, temporary, use_case_ids=selected_scope)
        current_audit = read_json(review_folder / 'manifest.json') == expected
        if not current_audit and not native_failures:
            raise ValueError('normal graph repair audit is stale; reprepare and complete it first')
        reviewed, state = collect_packets(review_folder, model_audit_validator(index)) if current_audit else ([], {'complete': False})
        if not state['complete'] and not native_failures:
            raise ValueError('normal graph repair requires complete semantic source coverage audit')
        # A valid selected source defect can trigger re-extraction while a full
        # audit is pending. No partial audit is treated as complete or passed.
        for row in reviewed if state['complete'] else []:
            if not row['passed']:
                original_packet = read_json(folder / 'packets' / (row['model_batch_id'] + '.json'))
                uc = original_packet['input']['use_case_id']
                # Explicit reviewed findings authorize those defects only. An
                # audit can mix correct and incorrect judgments in one case;
                # do not silently turn every unreviewed judgment in that case
                # into a repair instruction. All remain acceptance blockers
                # until the complete independent source audit passes again.
                if not native_failures:
                    semantic_failures[uc] = row
        reviewed = reviewed if state['complete'] else []
        audit = audit_model_origins(model, index, reviewed)
    from .interaction_graph_checks import check_graph_anchors
    graph_checks = check_graph_anchors(model, index, reviewed if (review_folder / 'manifest.json').exists() else None)
    for row in graph_checks['checks']:
        if native_failures and row['use_case_id'] not in native_failures:
            continue
        semantic_failures.setdefault(row['use_case_id'], {}).setdefault('normal_graph_tool_checks', []).append(row)
    # Extracted uncertainties are model input, not checker diagnoses. Preserve
    # their citations and let source-only extraction resolve or retain them.
    for gap in model.get('model_gaps', []):
        if native_failures and gap['use_case_id'] not in native_failures:
            continue
        semantic_failures.setdefault(gap['use_case_id'], {}).setdefault('unresolved_model_gaps', []).append(gap)
    client = _client(args, root)
    from .interaction_execution_identity import validate_client_execution_model
    validate_client_execution_model(client)
    write_json(root / 'model_origin_checks.json', audit)
    failures = {}
    for uc, row in semantic_failures.items():
        failures.setdefault(uc, []).append({'semantic_source_audit': row})
    for uc, rows in native_failures.items():
        failures.setdefault(uc, []).extend({'native_source_review': row} for row in rows)
    for check in audit['checks']:
        if native_failures and check['use_case_id'] not in native_failures:
            continue
        if not check['passed'] and not check.get('needs_semantic_branch_review'):
            failures.setdefault(check['use_case_id'], []).append(check)
    selected = []
    for batch in read_json(folder / 'manifest.json')['batches']:
        packet = read_json(folder / 'packets' / (batch['batch_id'] + '.json'))
        uc = packet['input']['use_case_id']
        if uc not in failures:
            continue
        raw = read_json(folder / 'results' / (batch['batch_id'] + '.json'))
        write_json(folder / 'attempts' / (batch['batch_id'] + '-normal-origin-' + uuid4().hex + '.json'),
            {'result': raw, 'validation_error': 'Source-only normal graph origin checks failed',
             'attempt': 0, 'model_origin_feedback': failures[uc]})
        (folder / 'results' / (batch['batch_id'] + '.json')).unlink()
        selected.append(batch['batch_id'])
    def validate_repaired(packet, raw):
        rows = validator(packet, raw)
        subset = {**base, 'use_cases': [u for u in base['use_cases'] if u['use_case_id'] == packet['input']['use_case_id']]}
        checked = audit_model_origins(merge_model(rows, subset, index), index)
        if any(not c['passed'] and not c.get('needs_semantic_branch_review') for c in checked['checks']):
            import json
            raise ValueError('Normal origin unresolved: ' + json.dumps([c for c in checked['checks'] if not c['passed']], ensure_ascii=False))
        return rows
    worker = run_agent_packets(folder, client, validate_repaired, batch_ids=selected) if selected else {'complete': True, 'batches': []}
    if selected:
        from .interaction_execution_identity import validate_result_execution
        for bid in selected:
            result_path = folder / 'results' / (bid + '.json')
            if result_path.is_file():
                validate_result_execution(read_json(result_path), result_path=result_path)
    return {'complete': False, 'repaired_batch_ids': selected, 'worker_result': worker,
        'repair_scope': 'selected_source_findings' if native_failures else 'all_current_source_failures',
        'note': 'Recompile the source-only model and recheck origins/architecture; no generated exceptions were rewritten.'}, 2
