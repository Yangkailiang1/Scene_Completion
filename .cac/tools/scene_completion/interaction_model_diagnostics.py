"""Explain rejected normal graph roles without C/G/test inputs or graph edits."""
from pathlib import Path
from uuid import uuid4
from copy import deepcopy

from .interaction_protocol import SERVICE_TYPES, OPERATION_KINDS
from .semantic_backend import read_json, write_json
from .sources import fingerprint


def structural_diagnostics(raw, packet=None, index=None):
    nodes = {n.get('component_id'): n for n in raw.get('components', [])}
    edges = raw.get('exchanges', [])
    result = []
    if packet is not None:
        assigned = {s['chapter_id'] for s in packet['input']['sections']}
        covered = raw.get('covered_section_ids', [])
        if len(covered) != len(assigned) or set(covered) != assigned:
            result.append({'code': 'covered_sections_include_context_or_omit_assigned',
                'required_section_ids': sorted(assigned), 'missing_section_ids': sorted(assigned-set(covered)),
                'extra_section_ids': sorted(set(covered)-assigned),
                'reason': 'covered_section_ids equals assigned sections exactly once; context_sections only resolve original metadata, not extra assignment or use-case units.'})
    for node in nodes.values():
        invalid = sorted(set(node.get('service_types', [])) - set(SERVICE_TYPES))
        if invalid:
            result.append({'code': 'unknown_service_type', 'component_id': node['component_id'],
                'invalid': invalid, 'allowed': list(SERVICE_TYPES)})
    for position, edge in enumerate(edges):
        source, target = [nodes.get(edge.get(k), {}) for k in ('from_component_id', 'to_component_id')]
        ids = {'local_exchange_id': edge.get('local_id'),
            'from_component_id': edge.get('from_component_id'), 'to_component_id': edge.get('to_component_id'),
            'source_refs': edge.get('source_refs', [])}
        invalid_operations = sorted(set(edge.get('operation_kinds', [])) - set(OPERATION_KINDS))
        if invalid_operations:
            result.append({**ids, 'code': 'unknown_operation_kind', 'invalid': invalid_operations,
                'allowed': sorted(OPERATION_KINDS),
                'reason': 'Use a supported category for the documented operation, without changing its actual source semantics or inventing behavior.'})
        if edge.get('requirement_layer') == 'RR':
            roles = edge.get('business_service_roles', [])
            for role in roles:
                category = role.get('service_type')
                mapped = role.get('mapped_sr_local_ids', [])
                if category not in SERVICE_TYPES or not role.get('evidence_quote') or not role.get('source_refs'):
                    result.append({**ids, 'code': 'rr_role_category_or_evidence_missing',
                        'service_type': category, 'allowed': list(SERVICE_TYPES),
                        'missing_fields': [k for k in ('evidence_quote', 'source_refs') if not role.get(k)],
                        'reason': 'Use one allowed category and a concrete positive own-RR quote with citations; an empty or guessed placeholder is not a business role.'})
                if not mapped or any(not any(e.get('local_id') == mid and e.get('requirement_layer') == 'SR'
                        and e.get('parent_rr_local_id') == edge.get('local_id') for e in edges) for mid in mapped):
                    result.append({**ids, 'code': 'rr_role_mapping_missing_or_foreign', 'service_type': category,
                        'mapped_sr_local_ids': mapped,
                        'reason': 'Map only real SR child calls under this exact RR interaction, according to positive business responsibility. Another RR request cannot supply role mappings; missing analyzed expansion is a model gap, not a placeholder role.'})
                if sum(r.get('service_type') == category for r in roles) > 1:
                    result.append({**ids, 'code': 'duplicate_rr_role_category', 'service_type': category,
                        'reason': 'One category per RR request. Combine source-backed child mappings and quotations in one role rather than emitting duplicate roles per clause.'})
                if index is not None:
                    from .interaction_origins import normal_model_line_origins
                    documents = {d['document']: d for d in index['documents']}
                    positive = []
                    for ref in role.get('source_refs', []):
                        doc = documents.get(ref.get('document'))
                        if not doc or doc['requirement_layer'] != 'RR':
                            continue
                        if type(ref.get('line_start')) is not int or type(ref.get('line_end')) is not int:
                            continue
                        origins = normal_model_line_origins(doc['text'])
                        positive.extend(doc['text'].splitlines()[n-1] for n in range(ref['line_start'], ref['line_end']+1)
                            if 1 <= n <= doc['line_count'] and origins[n] in {'normal', 'trigger', 'ordinary_optional'})
                    if not role.get('evidence_quote') or not any(role['evidence_quote'] in line for line in positive):
                        result.append({**ids, 'code': 'rr_role_without_own_positive_clause', 'service_type': category,
                            'received_quote': role.get('evidence_quote'), 'role_source_refs': role.get('source_refs', []),
                            'reason': 'Quote one actual RR positive normal/trigger/ordinary-optional business clause. Flow titles, exception branches, SR contracts and synthesized wording cannot establish an RR role. Find the real RR responsibility or report absence; do not copy another layer.'})
            human = source.get('kind') == 'human_actor' and target.get('boundary_role') == 'ui'
            incoming = source.get('kind') in {'external_service', 'external_llm'} and target.get('boundary_role') == 'receiver'
            outgoing = source.get('boundary_role') == 'receiver' and target.get('kind') in {'external_service', 'external_llm'}
            if not (human or incoming or outgoing):
                result.append({**ids, 'code': 'rr_actor_boundary_direction_invalid',
                    'reason': 'RR requests are human-to-UI or external-to/from-receiving-boundary. A display or reverse return belongs in response/normal scenario; internal service processing is a logical business role, not another RR request. Re-read actual initiating source.'})
            continue
        if edge.get('requirement_layer') != 'SR':
            continue
        if target.get('boundary_role'):
            result.append({**ids, 'code': 'sr_target_is_logical_boundary',
                'reason': 'SR entry API is a service role, not an additional UI/receiver boundary. Preserve the actual RR boundary and source-backed entry request; do not add deployment components.'})
        if source.get('boundary_role'):
            if edge.get('parent_sr_local_id'):
                result.append({**ids, 'code': 'logical_boundary_call_has_sr_parent',
                    'reason': 'An initiating UI/receiver call expands RR directly, not another SR call.'})
            parent = next((e for e in edges if e.get('local_id') == edge.get('parent_rr_local_id') and e.get('requirement_layer') == 'RR'), None)
            if parent:
                boundary_ids = [parent.get(k) for k in ('from_component_id', 'to_component_id') if nodes.get(parent.get(k), {}).get('boundary_role')]
                if edge.get('from_component_id') not in boundary_ids:
                    result.append({**ids, 'code': 'sr_boundary_differs_from_rr_parent', 'actual_rr_boundary_ids': boundary_ids,
                        'reason': 'Direct SR initiation comes from its actual RR boundary; shared names do not merge UI and external receiver roles. Keep actual actor direction and original request nesting.'})
            continue
        if source.get('kind') not in {'internal_service', 'abstract_service'}:
            continue
        earlier = [e for e in edges[:position] if e.get('requirement_layer') == 'SR'
            and e.get('to_component_id') == edge.get('from_component_id')
            and e.get('parent_rr_local_id') == edge.get('parent_rr_local_id')]
        parent = edge.get('parent_sr_local_id')
        if not earlier:
            result.append({**ids, 'code': 'sr_caller_without_enclosing_request',
                'reason': 'This executing SR role has no earlier incoming SR request in the same RR expansion. Re-read original normal steps for the boundary-to-entry call or correct a misclassified logical boundary; do not guess an edge or use exception/test conditions.'})
        elif parent not in {e['local_id'] for e in earlier}:
            result.append({**ids, 'code': 'sr_parent_missing_or_wrong_caller',
                'declared_parent': parent, 'eligible_structural_parent_ids': [e['local_id'] for e in earlier],
                'reason': 'A nested call must be enclosed by an earlier SR request to its actual caller within the same RR expansion. Eligibility does not establish semantic parentage; verify original order.'})
    return result


def run_model_diagnostics(args):
    from .interaction_batches import model_validator
    root = Path(args.output_dir)
    folder = root / 'batches/interaction-model'
    if args.prepare_retry:
        from .interaction_worker_state import assert_stage_idle
        assert_stage_idle(folder, 'preparing normal model retry diagnostics')
    index = read_json(root / 'sources_index.json')
    validator = model_validator(index)
    findings = []
    for batch in read_json(folder / 'manifest.json')['batches']:
        bid = batch['batch_id']
        if (folder / 'results' / (bid + '.json')).exists():
            continue
        def attempt_order(path):
            data = read_json(path)
            # A diagnostic copy is not a new model execution. With equal file
            # timestamps prefer the actual attempt, including a stale binding
            # which must be reported rather than silently ignored.
            return (path.stat().st_mtime_ns, not bool(data.get('diagnostic_source_attempt')), path.name)
        attempts = sorted((folder / 'attempts').glob(bid + '-*.json'), key=attempt_order)
        structured = [(p, read_json(p)) for p in attempts]
        structured = [(p, r) for p, r in structured if isinstance(r.get('result'), dict)]
        if not structured:
            findings.append({'batch_id': bid, 'status': 'no_structured_attempt'})
            continue
        original_path, original = structured[-1]
        raw = original['result']
        packet = read_json(folder / 'packets' / (bid + '.json'))
        if raw.get('batch_id') != bid or raw.get('input_hash') != packet['input_hash']:
            raise ValueError('normal diagnostic attempt is not bound to current packet')
        try:
            validator(packet, deepcopy(raw))
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
        else:
            raise ValueError('normal diagnostic cannot label valid extraction as rejected')
        diagnostics = structural_diagnostics(raw, packet, index)
        diagnostics.extend(component_identity_diagnostics(raw, packet, index, error))
        item = {'batch_id': bid, 'status': 'rejected', 'input_hash': packet['input_hash'],
            'original_attempt': str(original_path), 'original_result_hash': fingerprint(raw),
            'validation_error': error, 'diagnostics': diagnostics}
        if args.prepare_retry and diagnostics:
            feedback = folder / 'attempts' / (bid + '-structural-diagnostic-' + uuid4().hex + '.json')
            write_json(feedback, {'result': raw, 'validation_error': error, 'attempt': 0,
                'model_origin_feedback': diagnostics, 'diagnostic_source_attempt': str(original_path),
                'diagnostic_tool_hash': fingerprint(Path(__file__).read_text(encoding='utf-8'))})
            item['retry_feedback_file'] = str(feedback)
        findings.append(item)
    report = {'source_hash': fingerprint(index), 'complete_model': not findings,
        'generator_exception_edits': False, 'findings': findings}
    write_json(root / 'normal_model_diagnostics.json', report)
    return report, 0


def component_identity_diagnostics(raw, packet, index, error):
    """Expose literal source positions for a rejected name, never choose a call."""
    prefix = 'component name must quote its own original source, not an architecture hint or invented alias: '
    if not error.startswith(prefix):
        return []
    name = error[len(prefix):]
    documents = {d['document']: d for d in index['documents']}
    from .interaction_origins import normal_model_line_origins, explicit_exception_line
    rows = []
    for node in raw.get('components', []):
        if node.get('name') != name:
            continue
        bound = []
        for ref in node.get('source_refs', []):
            doc = documents.get(ref.get('document'))
            if not doc or type(ref.get('line_start')) is not int or type(ref.get('line_end')) is not int:
                continue
            bound.extend({'document': doc['document'], 'line': n, 'text': doc['text'].splitlines()[n-1]}
                for n in range(max(1, ref['line_start']), min(doc['line_count'], ref['line_end'])+1))
        candidates = {}
        for section in packet['input']['sections'] + packet['input'].get('context_sections', []):
            doc = documents[section['document']]
            if node.get('layer') in {'RR', 'SR'} and doc['requirement_layer'] != node['layer']:
                continue
            origins = normal_model_line_origins(doc['text'])
            for n in range(section['line_start'], section['line_end']+1):
                line = doc['text'].splitlines()[n-1]
                if name in line and origins[n] != 'abnormal' and not explicit_exception_line(line):
                    candidates[(doc['document'], n)] = {'document': doc['document'], 'line': n,
                        'text': line, 'source_origin': origins[n]}
        rows.append({'code': 'component_identity_reference_mismatch', 'component_id': node['component_id'],
            'received_name': name, 'received_source_refs': node.get('source_refs', []),
            'bound_original_lines': bound, 'literal_original_matches': list(candidates.values())[:8],
            'reason': 'The name is absent from its claimed source. These literal occurrences are source context, not a selected replacement or authorization for a component, database operation or call. Re-extract the identity and its own evidence from the original normal flow; do not guess an alias or copy exceptional branches.'})
    return rows
