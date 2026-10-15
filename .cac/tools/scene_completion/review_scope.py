"""Definition closure for checks of already-mounted generated units."""
from copy import deepcopy


def concern_closure(payload, registry):
    """Keep every mounted/source label; never alter units, evidence or locations."""
    result = deepcopy(payload)
    if result.get('collection') != 'G':
        return result
    definitions = result.get('concern_definitions', {})
    if not isinstance(definitions, dict) or any(
            key not in registry or value != registry[key] for key, value in definitions.items()):
        raise ValueError('review definitions differ from the bound concern registry')
    keys = set()
    for row in [*result.get('units', []), *result.get('original_scenarios', [])]:
        if not isinstance(row, dict):
            continue
        if row.get('concern_key'):
            keys.add(row['concern_key'])
        for field in ('concern_keys', 'original_concern_keys'):
            keys.update(row.get(field, []))
    if not keys or not keys <= set(definitions):
        raise ValueError('review is missing an actual mounted/source concern definition')
    result['concern_definitions'] = {key: value for key, value in definitions.items() if key in keys}
    return result
