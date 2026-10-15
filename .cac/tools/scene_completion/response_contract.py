"""Pure format views; original provider results and semantic checks stay intact."""
from copy import deepcopy


ENVELOPE_METADATA = {'stage', 'collection', 'round', 'batch_id', 'input_hash', 'model',
    'execution_model_evidence', 'baseline_execution'}


def contract_view(packet, result):
    """Accept only an unambiguous echo envelope, never alternate semantics."""
    if not isinstance(result, dict):
        raise ValueError('response root must be a JSON object')
    expected = set(packet.get('output_contract', {}))
    if 'output_contract' not in result or 'output_contract' in expected:
        return deepcopy(result)
    nested = result['output_contract']
    if not isinstance(nested, dict):
        raise ValueError('echoed output_contract must contain a populated JSON object')
    conflicts = expected & set(result)
    extras = set(result) - ENVELOPE_METADATA - {'output_contract'}
    missing = expected - set(nested)
    nested_metadata = set(nested) & ENVELOPE_METADATA - expected
    if conflicts or extras or missing or nested_metadata:
        raise ValueError(f'ambiguous response envelope: root_contract_fields={sorted(conflicts)}, '
            f'unexpected_outer_fields={sorted(extras)}, missing_inner_fields={sorted(missing)}, '
            f'inner_transport_fields={sorted(nested_metadata)}')
    if result.get('stage', packet.get('stage')) != packet.get('stage'):
        raise ValueError('echoed response stage differs from its packet')
    collection = packet.get('input', {}).get('collection')
    if 'collection' in result and result['collection'] != collection:
        raise ValueError('echoed response collection differs from its independent input channel')
    # Transport proof belongs to the actual outer response. Nothing is inferred
    # or filled in the semantic payload. The ordinary validator runs next.
    return {**{k: deepcopy(v) for k, v in result.items() if k in ENVELOPE_METADATA}, **deepcopy(nested)}


def source_id_differences(expected, actual):
    """Describe collection shape defects before quoting individual source units."""
    expected = list(expected)
    actual = [value if isinstance(value, str) else '<invalid:' + type(value).__name__ + '>' for value in actual]
    return {'expected_count': len(expected), 'actual_count': len(actual),
        'missing_ids': sorted(set(expected) - set(actual)),
        'unknown_ids': sorted(set(actual) - set(expected)),
        'duplicate_ids': sorted({value for value in actual if actual.count(value) > 1})}
