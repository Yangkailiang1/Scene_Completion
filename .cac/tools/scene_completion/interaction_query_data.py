"""Source-bound logical query results; never manufacture protocol fields."""
from .sources import validate_refs

QUERY_DATA_POLICY = 'logical-query-results-v1'


def validate_derived_response_shape(exchange):
    rows = exchange.get('derived_response_data', [])
    if not isinstance(rows, list):
        raise ValueError('derived_response_data must be a list')
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'field', 'derivation_reason', 'evidence_quote', 'source_refs', 'protocol_structure_unknown'}
                or row.get('protocol_structure_unknown') is not True
                or any(not isinstance(row.get(k), str) or not row[k].strip()
                    for k in ('field', 'derivation_reason', 'evidence_quote'))
                or not row['source_refs']):
            raise ValueError('logical query result needs derivation, original evidence and unknown protocol marker')
        if row['field'] in seen or row['field'] not in exchange.get('response_fields', []):
            raise ValueError('logical query result must name one unique actual response field')
        if 'read' not in exchange.get('operation_kinds', []):
            raise ValueError('logical query response requires a source-backed read interaction')
        seen.add(row['field'])


def validate_derived_response_sources(exchange, index):
    from .interaction_origins import normal_model_line_origins, explicit_exception_line
    validate_derived_response_shape(exchange)
    documents = {d['document']: d for d in index['documents']}
    bounds = exchange['source_refs'] + [ref for kind in ('contracts', 'request_contracts', 'response_contracts')
        for contract in exchange.get(kind, []) for ref in contract['source_refs']]
    for row in exchange.get('derived_response_data', []):
        refs = validate_refs(row['source_refs'], index, bounds)
        if not any(doc['requirement_layer'] == exchange['requirement_layer']
                and row['evidence_quote'] in doc['text'].splitlines()[n-1]
                and normal_model_line_origins(doc['text'])[n] in {'normal', 'trigger', 'ordinary_optional', 'branch'}
                and not explicit_exception_line(doc['text'].splitlines()[n-1])
                for ref in refs for doc in [documents[ref['document']]]
                for n in range(ref['line_start'], ref['line_end']+1)):
            raise ValueError('logical query result needs its own-layer original positive query evidence')


def audit_query_data(data, inventory, index):
    """Validate provenance links after independent semantic query decisions."""
    if data.get('query_data_policy') != QUERY_DATA_POLICY:
        return []
    exchanges = {e['local_id']: e for e in data['normal_model']['exchanges']}
    sources = {v['line_id']: v for v in data['normal_source_lines']}
    findings = []
    linked = set()
    for row in inventory:
        for datum in row['datums']:
            kind = datum.get('source_kind')
            if kind not in {'explicit', 'query_semantics'}:
                raise ValueError('source datum must distinguish original explicit data from query inference')
            if kind == 'query_semantics' and datum['direction'] != 'response':
                raise ValueError('query inference is only a logical response, never invented request data')
            for mapping in datum['mappings']:
                exchange = exchanges[mapping['local_exchange_id']]
                record = next((p for p in exchange.get('derived_response_data', []) if p['field'] == mapping['field']), None)
                if kind == 'query_semantics':
                    if record is None:
                        findings.append({'code':'derived_query_data_not_marked', 'line_id':row['line_id'],
                            'local_exchange_id':exchange['local_id'], 'field':mapping['field'],
                            'source_refs':sources[row['line_id']]['source_refs'],
                            'reason':'The independently identified logical result lacks explicit derivation/unknown-schema provenance.'})
                        continue
                    validate_derived_response_sources(exchange, index)
                    validate_refs(sources[row['line_id']]['source_refs'], index, record['source_refs'])
                    if record['evidence_quote'] not in sources[row['line_id']]['text']:
                        raise ValueError('logical result derivation must cite the independently reviewed original query line')
                    linked.add((exchange['local_id'], record['field']))
    for exchange in exchanges.values():
        for record in exchange.get('derived_response_data', []):
            if (exchange['local_id'], record['field']) not in linked:
                findings.append({'code':'logical_query_derivation_not_verified', 'local_exchange_id':exchange['local_id'],
                    'field':record['field'], 'source_refs':record['source_refs'],
                    'reason':'The source-only inventory has not independently confirmed this marked logical query result.'})
    return findings
