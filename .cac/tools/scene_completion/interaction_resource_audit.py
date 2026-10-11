"""Verify independently inventoried positive database calls against SSD endpoints.

Semantic source extraction decides whether a clause describes a resource call.
The tool checks its exact source, real caller, physical callee/facade and anchors.
Architecture-only resources do not imply calls or exception candidates.
"""
from .interaction_origins import explicit_exception_line


def resource_universe(model):
    if not isinstance(model, dict) or not isinstance(model.get('components'), list):
        raise ValueError('resource audit requires the normal-model components schema; nodes are not interchangeable')
    return [n['component_id'] for n in model['components']
        if n['kind'] in {'internal_database', 'external_database'} and n['layer'] == 'SR']


def validate_resource_reviews(data, result, lines, exchanges, findings):
    required = data.get('source_resource_coverage_required', False)
    rows = result.get('resource_operation_reviews', [])
    if not required:
        return []
    resources = resource_universe(data['normal_model'])
    if data.get('resource_universe', resources) != resources:
        raise ValueError('resource audit universe differs from the actual normal model')
    if (not isinstance(rows, list) or len(rows) != len(resources)
            or {r.get('resource_component_id') for r in rows} != set(resources)):
        raise ValueError('resource audit must inspect every declared SR physical resource exactly once')
    nodes = {n['component_id']: n for n in data['normal_model'].get('components', [])}
    for row in rows:
        if not isinstance(row.get('reason'), str) or not row['reason'].strip() or not isinstance(row.get('operations'), list):
            raise ValueError('resource audit needs original-flow reasoning and an explicit operation list')
        seen = set()
        rid = row['resource_component_id']
        for op in row['operations']:
            line = lines.get(op.get('line_id'))
            caller_id = op.get('caller_component_id')
            caller = nodes.get(caller_id)
            caller_name = op.get('caller_source_name')
            quote = op.get('evidence_quote')
            ids = op.get('local_exchange_ids')
            key = (op.get('line_id'), caller_id, caller_name, op.get('operation'))
            if (key in seen or not line or line['requirement_layer'] != 'SR'
                    or line.get('source_origin') == 'abnormal' or explicit_exception_line(line['text'])
                    or not isinstance(caller_id, str)
                    or (caller_id and (not caller or caller['layer'] != 'SR'))
                    or not isinstance(op.get('operation'), str) or not op['operation'].strip()
                    or not isinstance(quote, str) or not quote.strip() or quote not in line['text']
                    or not isinstance(ids, list) or len(ids) != len(set(ids))):
                raise ValueError('resource operation needs a unique positive SR clause, an existing SR caller or an explicit missing caller, and exact quote')
            if data.get('resource_caller_source_required') or not caller_id:
                if (not isinstance(caller_name, str) or not caller_name.strip()
                        or caller_name not in line['text']):
                    raise ValueError('resource operation caller_source_name must be a literal original positive SR caller')
            seen.add(key)
            if not caller_id:
                if ids:
                    raise ValueError('a missing source caller cannot claim an existing resource exchange')
                findings.append({'code': 'resource_caller_not_modeled', 'line_id': op['line_id'],
                    'resource_component_id': rid, 'caller_source_name': caller_name,
                    'operation': op['operation'], 'source_refs': line['source_refs'], 'evidence_quote': quote,
                    'reason': 'The named original SR resource caller is absent from the normal model; no endpoint may impersonate it. Source-backed participant completion and its authorized calls are required.'})
                continue
            if not ids:
                findings.append({'code': 'source_resource_call_omitted', 'line_id': op['line_id'],
                    'resource_component_id': rid, 'caller_component_id': op['caller_component_id'],
                    'operation': op['operation'], 'source_refs': line['source_refs'], 'evidence_quote': quote,
                    'reason': 'The original positive SR database operation has no actual resource-service SSD exchange; implementation references cannot cover it.'})
            for eid in ids:
                e = exchanges.get(eid)
                target = nodes.get(e.get('to_component_id')) if e else None
                if (not e or e['requirement_layer'] != 'SR'
                        or e.get('from_component_id') != op['caller_component_id'] or not target
                        or (target['component_id'] != rid and target.get('physical_resource_id') != rid)):
                    raise ValueError('resource coverage must reach the physical resource or its explicit facade from the original caller')
                ref = line['source_refs'][0]
                if not any(r['document'] == ref['document'] and r['line_start'] <= ref['line_start'] <= r['line_end']
                        for r in e['source_refs']):
                    findings.append({'code': 'source_resource_call_without_anchor', 'line_id': op['line_id'],
                        'resource_component_id': rid, 'local_exchange_id': eid, 'source_refs': line['source_refs'],
                        'reason': 'The resource operation is mapped to an exchange without its own original call anchor.'})
    return rows
