"""Output shape constraints, independent of source semantics and acceptance."""
import re
from copy import deepcopy


def audit_literal_quotes(packet):
    """Selectable literal fragments of supplied ORIGINAL lines, not model text."""
    data = packet.get('input') or {}
    lines = [row['text'] for key in ('normal_source_lines', 'contract_source_lines')
        for row in data.get(key, []) if isinstance(row.get('text'), str)]
    for section in data.get('sections', []) + data.get('architecture_sections', []):
        for numbered in section.get('numbered_text', '').splitlines():
            match = re.match(r'^\d+: (.*)$', numbered)
            if match:
                lines.append(match.group(1))
    quotes = set()
    for line in lines:
        text = line.strip()
        if not text:
            continue
        # Every choice remains one contiguous fragment of an original line.
        # Shared predicates are never repeated or paraphrased for later objects.
        pieces = [text, *re.split(r'[，,；;。]', text)]
        for piece in pieces:
            for literal in (piece.strip(), piece.strip().rstrip('.。；;')):
                if literal:
                    quotes.add(literal)
    return sorted(quotes)


def audit_output_schema(contract, literal_quotes=None, source_lines=None):
    """Compile the existing source-audit contract without setting decisions."""
    def schema(value, field=''):
        if isinstance(value, dict):
            return {'type': 'object', 'properties': {k: schema(v, k) for k, v in value.items()},
                'required': list(value), 'additionalProperties': False}
        if isinstance(value, list):
            if value:
                if len(value) != 1:
                    raise ValueError('audit output contract arrays need one shape exemplar')
                item = schema(value[0])
            elif field in {'source_refs', 'role_refs', 'interaction_refs', 'participant_refs'}:
                item = schema({'document': '', 'line_start': 1, 'line_end': 1})
            elif field in {'issues', 'local_exchange_ids', 'mapped_sr_local_ids', 'missing_condition_details', 'heading_path'}:
                item = {'type': 'string'}
            else:
                raise ValueError('unknown empty audit contract array: ' + field)
            return {'type': 'array', 'items': item}
        if type(value) is bool:
            return {'type': 'boolean'}
        if type(value) is int:
            return {'type': 'integer'}
        if type(value) is float:
            return {'type': 'number'}
        if isinstance(value, str):
            if field == 'evidence_quote' and literal_quotes:
                return {'$ref': '#/$defs/OriginalQuote'}
            if field in {'role_quote', 'interaction_quote', 'declared_participant_quote'} and literal_quotes:
                # Optional evidence can be absent; the semantic validator still
                # requires it for the statuses that claim actual involvement.
                return {'$ref': '#/$defs/ParticipantQuote'}
            result = {'type': 'string'}
            if field in {'classification', 'direction', 'requirement_layer', 'contract_kind', 'source_kind', 'status', 'relation', 'checker_field'} and '|' in value:
                result['enum'] = value.split('|')
            return result
        raise ValueError('unknown audit output contract value: ' + field)
    if not isinstance(contract, dict) or not ({'line_reviews', 'component_reviews', 'pairs', 'items', 'decisions'} & set(contract)):
        raise ValueError('structured source audit requires its original output contract')
    result = schema(contract)
    if literal_quotes:
        result['$defs'] = {'OriginalQuote': {'type': 'string', 'enum': sorted(set(literal_quotes))}}
        if 'component_reviews' in contract:
            result['$defs']['ParticipantQuote'] = {'type': 'string', 'enum': sorted(set(literal_quotes) | {''})}
    # A literal from another supplied line is still a false citation. Bind
    # transfer-inventory quotes to the selected original line without choosing
    # datums, mappings, source semantics or a positive coverage decision.
    if source_lines and 'source_data_reviews' in result['properties']:
        definitions = result.setdefault('$defs', {})
        item = result['properties']['source_data_reviews']['items']
        datum = item['properties']['datums']['items']
        definitions['SourceDatumMappings'] = datum['properties']['mappings']
        choices = []
        for number, row in enumerate(source_lines):
            name = 'SourceLineQuote' + str(number)
            definitions[name] = {'type': 'string', 'enum': audit_literal_quotes({
                'input': {'normal_source_lines': [{'text': row['text']}]}})}
            choices.append({'type': 'object', 'additionalProperties': False,
                'required': ['line_id', 'reason', 'datums'], 'properties': {
                    'line_id': {'type': 'string', 'enum': [row['line_id']]},
                    'reason': {'type': 'string'},
                    'datums': {'type': 'array', 'items': {
                        'type': 'object', 'additionalProperties': False,
                        'required': ['datum', 'direction', 'evidence_quote', 'mappings'],
                        'properties': {'datum': {'type': 'string'},
                            'direction': {'type': 'string', 'enum': ['request', 'response']},
                            'evidence_quote': {'$ref': '#/$defs/' + name},
                            'mappings': {'$ref': '#/$defs/SourceDatumMappings'}}}}}})
        result['properties']['source_data_reviews']['items'] = {'anyOf': choices}
        if 'source_kind' in datum['properties']:
            for choice in choices:
                child = choice['properties']['datums']['items']
                child['required'].append('source_kind')
                child['properties']['source_kind'] = deepcopy(datum['properties']['source_kind'])
        result['properties']['source_data_reviews'].update(minItems=len(source_lines), maxItems=len(source_lines))
        # Resource inventory also selects an original line. A quote from a
        # different supplied line remains invalid even when globally literal.
        # Do not constrain callers, operations or mappings to model guesses.
        resources = result['properties'].get('resource_operation_reviews')
        if resources:
            operations = resources['items']['properties']['operations']
            original_item = operations['items']
            alternatives = []
            for number, row in enumerate(source_lines):
                item = deepcopy(original_item)
                item['properties']['line_id'] = {'type': 'string', 'enum': [row['line_id']]}
                item['properties']['evidence_quote'] = {'$ref': '#/$defs/SourceLineQuote' + str(number)}
                alternatives.append(item)
            operations['items'] = {'anyOf': alternatives}
    return result


def pair_output_schema(packet):
    """Pin actual IDs and literal evidence, never the semantic decision."""
    result = audit_output_schema(packet['output_contract'])
    original = result['properties']['pairs']['items']
    alternatives = []
    def choices(values):
        return {'type':'string', 'enum':sorted(set(values) | {''})}
    for checker in packet['input']['checker']:
        for generated in packet['input']['generated']:
            item = deepcopy(original)
            props = item['properties']
            props['checker_scenario_id'] = choices([checker['scenario_id']])
            props['checker_scenario_id']['enum'].remove('')
            props['generated_scenario_id'] = choices([generated['scenario_id']])
            props['generated_scenario_id']['enum'].remove('')
            fields = ('exception_object','operation','failure_mechanism','trigger_condition')
            for side, scene in (('generated',generated),('checker',checker)):
                props[side+'_evidence'] = choices([scene[f] for f in fields])
                for field in fields:
                    props['identification_evidence']['properties'][field]['properties'][side] = choices([scene[field]])
                props['causal_facet_evidence']['properties'][side] = choices([scene['failure_mechanism'],scene['trigger_condition']])
            conditions = checker.get('necessary_conditions',[])
            evidence = props['condition_evidence']['items']['properties']
            evidence['checker_condition'] = choices(conditions)
            evidence['generated_quote'] = choices([generated['failure_mechanism'],generated['trigger_condition'],*generated.get('necessary_conditions',[])])
            props['condition_evidence']['maxItems'] = len(conditions)
            missing = [checker['trigger_condition'],*conditions]
            props['missing_condition_details']['items'] = choices(missing)
            gaps = props['missing_condition_evidence']['items']['properties']
            gaps['detail'] = choices(missing)
            gaps['checker_quote'] = choices(missing)
            alternatives.append(item)
    result['properties']['pairs'].update(items={'anyOf':alternatives},
        minItems=len(alternatives),maxItems=len(alternatives))
    return result


def recommendation_output_schema(packet):
    """Bind each candidate to its own evidence and target chapter choices."""
    from .interaction_batches import bound_contract_refs
    result=audit_output_schema(packet['output_contract'])
    exemplar=result['properties']['items']['items']
    exchanges={e['exchange_id']:e for e in packet['input']['exchanges']}
    definitions=result.setdefault('$defs',{})
    citation_names={}
    def reference_choice(ref):
        from .sources import fingerprint
        citation={key:value for key,value in ref.items()
            if key in {'document','chapter_id','heading_path','line_start','line_end'}}
        identity=fingerprint(citation)
        if identity in citation_names:
            return {'$ref':'#/$defs/'+citation_names[identity]}
        name='Citation'+str(len(citation_names))
        citation_names[identity]=name
        properties={key:({'type':'array','items':{'type':'string','enum':ref[key] or ['']},
            'minItems':len(ref[key]),'maxItems':len(ref[key])} if isinstance(value,list)
            else {'type':'integer' if type(value) is int else 'string','enum':[value]})
            for key,value in ref.items() if key in {'document','chapter_id','heading_path','line_start','line_end'}}
        definitions[name]={'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
        return {'$ref':'#/$defs/'+name}
    alternatives=[]
    for candidate in packet['input']['candidates']:
        item=deepcopy(exemplar)
        props=item['properties']
        props['scenario_id']={'type':'string','enum':[candidate['scenario_id']]}
        exchange=exchanges[candidate['exchange_id']]
        refs=exchange['source_refs']+bound_contract_refs(exchange)
        props['source_refs']={'type':'array','minItems':1,'items':{'anyOf':[reference_choice(r) for r in refs]}}
        targets=packet['input']['target_sections'][candidate['scenario_id']]
        props['suggested_sections']={'type':'array','minItems':1,'items':{'anyOf':[reference_choice(r) for r in targets]}}
        for score in ('support_score','missing_score'):
            props[score]={'type':'number','minimum':0,'maximum':1}
        alternatives.append(item)
    result['properties']['items'].update(items={'anyOf':alternatives},minItems=len(alternatives),maxItems=len(alternatives))
    return result


def equivalence_output_schema(packet):
    """Keep every source-mapped pair and source strings, not a chosen verdict."""
    result=audit_output_schema(packet['output_contract'])
    exemplar=result['properties']['decisions']['items']
    definitions=result.setdefault('$defs',{})
    quote_names={}
    def quote(text):
        if text not in quote_names:
            name='IdentityQuote'+str(len(quote_names))
            quote_names[text]=name
            definitions[name]={'type':'string','enum':[text]}
        return {'$ref':'#/$defs/'+quote_names[text]}
    alternatives=[]
    for pair in packet['input']['pairs']:
        item=deepcopy(exemplar)
        props=item['properties']
        for side in ('left','right'):
            scene=pair[side]
            props[side+'_id']=quote(scene['scenario_id'])
            for field in ('exception_object','operation','failure_mechanism','trigger_condition'):
                props['evidence']['properties'][field]['properties'][side]=quote(scene[field])
            props['condition_equivalence']['items']['properties'][side+'_condition']={
                'type':'string','enum':scene.get('necessary_conditions',[])+['']}
        alternatives.append(item)
    result['properties']['decisions'].update(items={'anyOf':alternatives},
        minItems=len(alternatives),maxItems=len(alternatives))
    return result


def validate_output_shape(value, schema, location='$', definitions=None):
    """Check the small generated schema vocabulary; do not judge semantics."""
    definitions = schema.get('$defs', {}) if definitions is None else definitions
    if 'anyOf' in schema:
        for alternative in schema['anyOf']:
            try:
                validate_output_shape(value, alternative, location, definitions)
                return
            except ValueError:
                pass
        raise ValueError('native output alternatives differ at ' + location)
    if '$ref' in schema:
        reference = schema['$ref']
        if not reference.startswith('#/$defs/') or reference[8:] not in definitions:
            raise ValueError('native output schema has an unsupported reference at ' + location)
        return validate_output_shape(value, definitions[reference[8:]], location, definitions)
    kind = schema.get('type')
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
        'string': isinstance(value, str), 'boolean': type(value) is bool, 'integer': type(value) is int,
        'number': type(value) in (int,float)}
    if kind not in valid or not valid[kind]:
        raise ValueError('native output shape differs at ' + location)
    if kind == 'object':
        properties = schema.get('properties', {})
        if set(value) != set(properties) or set(schema.get('required', [])) != set(properties):
            raise ValueError('native output missing/extra fields at ' + location)
        for field, child in properties.items():
            validate_output_shape(value[field], child, location + '.' + field, definitions)
    elif kind == 'array':
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            raise ValueError('native output array size differs at ' + location)
        for number, item in enumerate(value):
            validate_output_shape(item, schema['items'], location + '[' + str(number) + ']', definitions)
    else:
        if 'enum' in schema and value not in schema['enum']:
            raise ValueError('native output enum differs at ' + location)
        if kind=='number' and (value < schema.get('minimum',float('-inf')) or value > schema.get('maximum',float('inf'))):
            raise ValueError('native output numeric range differs at ' + location)
