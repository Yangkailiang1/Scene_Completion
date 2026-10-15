"""Literal evidence selection and bounded diagnosis-format repair helpers."""
from .sources import fingerprint


def rejection_ids(failure, target):
    """Connect a rejected normalized unit to its own original source record."""
    ids = {str(row[key]) for row in failure.get('findings', []) if isinstance(row, dict)
        for key in ('unit_id', 'scenario_id', 'id', 'source_scenario_id') if row.get(key)}
    for row in target.get('values', []):
        if isinstance(row, dict) and any(str(row.get(k)) in ids for k in ('unit_id', 'scenario_id', 'id')):
            if row.get('source_scenario_id'):
                ids.add(str(row['source_scenario_id']))
    return ids


def failure_view(failure):
    """The immutable failure archive retains the output; prompts need findings."""
    artifacts = {'output', 'candidate_replacements', 'candidate_source_repair',
        'source_obligation_findings', 'recovered_from_journal', 'normalization_folder'}
    return {key: value for key, value in failure.items() if key not in artifacts}


def focus_input(payload, ids=()):
    """Keep rejected records and their clauses; retain surrounding model context."""
    from copy import deepcopy
    result = deepcopy(payload)
    selected = set(ids)
    for key in ('scenarios', 'units', 'original_scenarios'):
        rows = result.get(key)
        if not selected or not isinstance(rows, list):
            continue
        related = [row for row in rows if isinstance(row, dict) and any(
            str(row.get(field)) in selected for field in ('scenario_id', 'unit_id', 'source_scenario_id'))]
        if related:
            result[key] = related
    evidence = result.get('original_evidence')
    if selected and isinstance(evidence, list):
        related = [row for row in evidence if str(row.get('scenario_id')) in selected]
        if related:
            result['original_evidence'] = related
    return result


def share_allowed_inputs(inputs):
    """Send identical stage context once, without dropping any allowed evidence."""
    from copy import deepcopy
    inputs = deepcopy(inputs)
    if len(inputs) < 2:
        return inputs
    shared = {key: value for key, value in inputs[0].items()
        if all(key in other and other[key] == value for other in inputs[1:])}
    if shared:
        for value in inputs:
            for key in shared:
                value.pop(key)
        inputs.append({'shared_stage_context': shared})
    return inputs


def repair_input(payload):
    """Retain every taxonomy definition, omit repeated registry bookkeeping."""
    from copy import deepcopy
    result = deepcopy(payload)
    definitions = result.get('concern_definitions')
    if isinstance(definitions, dict):
        result['concern_definitions'] = {key: {field: value for field, value in row.items()
            if field not in ('key', 'registry_version', 'draft', 'evidence_types')}
            if isinstance(row, dict) else row for key, row in definitions.items()}
        result['concern_registry_hash'] = fingerprint(definitions)
    return result


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,list):
        for item in value:yield from strings(item)
    elif isinstance(value,dict):
        for key,item in value.items():
            if key not in ('skill','extraction_skills','execution_versions','instructions'):
                yield from strings(item)


def quote_catalog(allowed, limit=40):
    result=[];seen=set()
    for text in strings(allowed):
        for line in text.splitlines():
            quote=line.strip()[:200]
            if len(quote)<4 or quote in seen:continue
            seen.add(quote);result.append({'id':'DQ-'+fingerprint(quote)[:12],'quote':quote})
            if len(result)>=limit:return result
    return result


def validate(packet,result):
    if result.get('action') not in ('repair','recheck','confirm') or not result.get('reason'):
        raise ValueError('diagnosis requires a permitted action and concrete reason')
    allowed=list(strings(packet['input']['allowed_inputs']))
    # A diagnosis must be able to name the wrong value it is correcting, and a
    # rejected output value by construction cannot occur in the allowed inputs.
    # The channel's own supplied failed output is original material too, so it
    # is quotable; the original-source rule below still stands.
    supplied=allowed+list(strings(packet['input'].get('failed_outputs_from_same_channel',[])))
    quotes=result.get('evidence_quotes',[])
    if not isinstance(quotes,list):raise ValueError('diagnosis evidence_quotes must be a list')
    quotes=list(quotes)
    catalog={r['id']:r['quote'] for r in packet['input'].get('evidence_catalog',[])}
    refs=result.get('evidence_refs',[])
    if not isinstance(refs,list) or any(not isinstance(ref,str) or ref not in catalog for ref in refs):
        raise ValueError('diagnosis evidence_refs must select supplied literal quote IDs')
    quotes.extend(catalog[ref] for ref in refs)
    # Match original string leaves, not Python repr(dict), which escapes
    # newlines and quotation marks and rejected otherwise literal evidence.
    if any(not isinstance(q,str) or not q or not any(q in text for text in supplied) for q in quotes):
        raise ValueError('diagnosis must quote supplied evidence')
    # At least one quote must still come from the case's original allowed
    # inputs, so a diagnosis never rests only on the output it is judging.
    targets = result.get('targets', [])
    errors = list(strings(packet['input'].get('failure', {})))
    structure_only = (result['action'] == 'repair' and not quotes and targets == ['items']
        and any('items must be a list' in error for error in errors))
    if not structure_only and not any(any(q in text for text in allowed) for q in quotes):
        raise ValueError('diagnosis requires original-source evidence from allowed inputs')
    if result['action']=='recheck' and not quotes:
        raise ValueError('checker misjudgment requires independent original-source evidence')
    if not isinstance(result.get('targets'),list):raise ValueError('diagnosis must explicitly identify repair targets')
    return [{'action':result['action'],'reason':result['reason'],'targets':result['targets'],
        'evidence_quotes':list(dict.fromkeys(quotes))}]
