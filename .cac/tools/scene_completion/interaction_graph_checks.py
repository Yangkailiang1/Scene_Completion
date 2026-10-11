"""Deterministic source-anchor guards, independent of project identifiers.

No exception collection or generated candidates are inputs. These checks do not
classify arbitrary prose: operation decisions come from validated source audit.
"""
import re

from .interaction_batches import cited_text, bound_contract_refs
from .sources import fingerprint


def check_graph_anchors(model, index, source_reviews):
    documents = {d['document']: d for d in index['documents']}
    checks = []
    for uc in model['use_cases']:
        review = next((r for r in source_reviews or [] if r['use_case_id'] == uc['use_case_id']), None)
        for exchange in uc['exchanges']:
            caller = exchange.get('from_node', exchange.get('from_component_id'))
            callee = exchange.get('to_node', exchange.get('to_component_id'))
            if exchange['requirement_layer'] == 'SR' and caller and caller == callee:
                checks.append({'use_case_id': uc['use_case_id'], 'local_exchange_id': exchange['local_id'],
                    'passed': False, 'code': 'local_service_step_as_interaction',
                    'source_refs': exchange['source_refs'],
                    'reason': 'An operation inside one SR endpoint is not an interaction between SR participants. Retain the documented local step or bound legal contract in its enclosing request; a distinct callee needs original evidence, never an invented component.'})
            if exchange['requirement_layer'] != 'RR':
                continue
            refs = [r for r in exchange['source_refs'] + bound_contract_refs(exchange)
                if documents[r['document']]['requirement_layer'] == 'RR']
            text = cited_text(refs, index)
            supported = {(r['direction'], r['field']) for r in (review or {}).get('field_reviews', [])
                if r['supported'] and r['local_exchange_id'] == exchange['local_id']}
            unbound = [field for side in ('request', 'response') for field in exchange.get(side + '_fields', [])
                if field not in text and (side, field) not in supported]
            if unbound:
                checks.append({'use_case_id': uc['use_case_id'], 'local_exchange_id': exchange['local_id'],
                    'passed': False, 'code': 'rr_fields_without_original_names', 'fields': sorted(set(unbound)),
                    'source_refs': refs, 'reason': 'RR data needs original text or a complete semantic field audit bound to its own positive evidence; unproven SR schemas cannot be imported. Preserve unknown data in pending_details.'})
        if not review:
            continue
        calls = {}
        for row in review['line_reviews']:
            if row['classification'] != 'request_call' or not row['covered']:
                continue
            name, number = row['line_id'].rsplit(':L', 1)
            line = documents[name]['text'].splitlines()[int(number) - 1]
            # Only independently numbered steps establish distinct invocations;
            # continuation lines and prose formatting do not trigger this rule.
            if not re.match(r'^\s*(?:[①-⑳]|\d+[.、)]\s)', line):
                continue
            for eid in row['local_exchange_ids']:
                calls.setdefault(eid, []).append(row['line_id'])
        for eid, lines in calls.items():
            if len(set(lines)) > 1:
                checks.append({'use_case_id': uc['use_case_id'], 'local_exchange_id': eid,
                    'passed': False, 'code': 'collapsed_separate_request_steps', 'source_line_ids': sorted(set(lines)),
                    'reason': 'Distinct numbered initiating request steps share one SSD exchange. Preserve their order and separate calls; storing all steps in a broad source span does not preserve interactions.'})
    return {'model_hash': fingerprint(model), 'source_hash': fingerprint(index),
        'source_review_hash': fingerprint(source_reviews) if source_reviews is not None else None,
        'passed': not checks, 'checks': checks}
