"""Structured output enforces shape while leaving source decisions unchanged."""
from copy import deepcopy
import json
import subprocess
from pathlib import Path

import pytest

from scene_completion.interaction_output_schema import audit_output_schema, audit_literal_quotes, validate_output_shape
from scene_completion.interaction_execution_identity import validate_result_execution, copy_execution_sidecars
from scene_completion.luna_subprocess import LunaSubprocessClient


def contract():
    return {'line_reviews': [{'line_id': 'assigned', 'classification': 'request_call|context',
        'covered': True, 'local_exchange_ids': [], 'reason': 'source reason', 'issues': [],
        'source_refs': []}]}


def output():
    return {'line_reviews': [{'line_id': 'clinic.md:L3', 'classification': 'request_call',
        'covered': False, 'local_exchange_ids': [], 'reason': 'Source call omitted.',
        'issues': ['The source call is absent.'],
        'source_refs': [{'document': 'clinic.md', 'line_start': 3, 'line_end': 3}]}]}


def test_schema_requires_every_nested_flag_and_keeps_negative_decisions():
    exemplar = contract()
    before = deepcopy(exemplar)
    schema = audit_output_schema(exemplar)
    row = schema['properties']['line_reviews']['items']
    assert 'issues' in row['required'] and row['additionalProperties'] is False
    assert row['properties']['covered'] == {'type': 'boolean'}
    assert row['properties']['classification']['enum'] == ['request_call', 'context']
    validate_output_shape(output(), schema)
    assert exemplar == before and output()['line_reviews'][0]['covered'] is False


def test_quote_choices_use_original_lines_not_generated_descriptions():
    source = 'LabService writes patient record and specimen record, then returns the report.'
    packet = {'input': {'normal_source_lines': [{'text': source}],
        'contract_source_lines': [{'text': 'An active patient is required.'}],
        'sections': [{'numbered_text': '4: System returns the application number.'}],
        'normal_model': {'return_description': 'Invented report fields.'}}}
    before = deepcopy(packet)
    choices = audit_literal_quotes(packet)
    assert source in choices and 'System returns the application number' in choices
    assert 'writes specimen record' not in choices and 'Invented report fields.' not in choices
    originals = [source, 'An active patient is required.', 'System returns the application number.']
    assert all(any(choice in line for line in originals) for choice in choices)
    assert packet == before


def test_participant_schema_uses_architecture_literals_without_inventing_involvement():
    packet = {'input': {'sections': [{'numbered_text': '8: Nurse submits a specimen.'}],
        'architecture_sections': [{'numbered_text': '2: LaboratoryService | internal service'}]}}
    exemplar = {'component_reviews': [{'component_id': 'component',
        'status': 'declared|missing_declaration|not_involved', 'role_quote': 'source', 'role_refs': [],
        'interaction_quote': 'source or empty', 'interaction_refs': [],
        'declared_participant_quote': 'source or empty', 'participant_refs': [], 'reason': 'evidence'}],
        'missing_model_calls': [], 'unresolved_candidates': []}
    # These real contracts use exemplars for both additional record arrays.
    exemplar.pop('missing_model_calls')
    exemplar.pop('unresolved_candidates')
    schema = audit_output_schema(exemplar, audit_literal_quotes(packet))
    value = {'component_reviews': [{'component_id': 'lab', 'status': 'not_involved',
        'role_quote': 'LaboratoryService | internal service',
        'role_refs': [{'document': 'clinic.md', 'line_start': 2, 'line_end': 2}],
        'interaction_quote': '', 'interaction_refs': [], 'declared_participant_quote': '',
        'participant_refs': [], 'reason': 'Architecture membership alone is insufficient.'}]}
    before = deepcopy(value)
    validate_output_shape(value, schema)
    assert value == before
    value['component_reviews'][0]['role_quote'] = 'LaboratoryService is involved in this call.'
    with pytest.raises(ValueError, match='native output enum'):
        validate_output_shape(value, schema)


def test_pair_schema_pins_ids_and_conditions_without_choosing_status(tmp_path):
    from scene_completion.interaction_output_schema import pair_output_schema
    from scene_completion.interaction_batches import pair_packets
    from tests.test_interaction_protocol import scene, pair
    from scene_completion.semantic_backend import read_json
    generated, checker = scene('G'), scene('C')
    manifest = pair_packets([generated],[checker],tmp_path)
    packet = read_json(tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    schema = pair_output_schema(packet)
    value = {'pairs':[dict(pair('C','G'),condition_evidence=[],missing_condition_evidence=[])]}
    validate_output_shape(value,schema)
    negative = deepcopy(value)
    negative['pairs'][0].update(status='unmatched',same_mechanism=False)
    validate_output_shape(negative,schema)
    value['pairs'][0]['generated_scenario_id']='mistyped-id'
    with pytest.raises(ValueError,match='native output alternatives'):
        validate_output_shape(value,schema)
    value['pairs'][0]['generated_scenario_id']='G'
    value['pairs'][0]['generated_evidence']='Invented evidence'
    with pytest.raises(ValueError,match='native output alternatives'):
        validate_output_shape(value,schema)


def test_recommendation_schema_keeps_scores_free_but_cannot_borrow_other_evidence():
    from scene_completion.interaction_output_schema import recommendation_output_schema
    first={'document':'clinic.md','chapter_id':'visit','heading_path':['Visit'],'line_start':3,'line_end':3}
    second={**first,'line_start':8,'line_end':8}
    contract={'items':[{'scenario_id':'ID','support_score':.5,'missing_score':1.,
        'support_reason':'evidence','missing_reason':'gap','source_refs':[],
        'suggested_sections':[{'document':'source','chapter_id':'chapter','heading_path':[],'line_start':1,'line_end':1}],
        'recommendation':'chapter suggestion'}]}
    packet={'output_contract':contract,'input':{'candidates':[{'scenario_id':'a','exchange_id':'x'},
        {'scenario_id':'b','exchange_id':'y'}], 'exchanges':[{'exchange_id':'x','source_refs':[first]},
        {'exchange_id':'y','source_refs':[second]}], 'target_sections':{'a':[first],'b':[second]}}}
    schema=recommendation_output_schema(packet)
    value={'items':[{'scenario_id':sid,'support_score':score,'missing_score':.6,'support_reason':'supported',
        'missing_reason':'not present','source_refs':[ref],'suggested_sections':[ref],'recommendation':'add condition'}
        for sid,ref,score in [('a',first,.2),('b',second,.9)]]}
    validate_output_shape(value,schema)
    value['items'][0]['source_refs']=[second]
    with pytest.raises(ValueError,match='native output alternatives'):
        validate_output_shape(value,schema)


def test_equivalence_schema_requires_literal_identity_but_leaves_verdict_open(tmp_path):
    from scene_completion.interaction_output_schema import equivalence_output_schema
    from scene_completion.interaction_equivalence import equivalence_packets
    from scene_completion.semantic_backend import read_json
    from tests.test_interaction_protocol import scene
    left,right=scene('rr'),scene('sr','SR')
    left['exchange_id'],right['exchange_id']='r','s'
    ssd={'exchanges':[{'exchange_id':'r'},{'exchange_id':'s','parent_exchange_id':'r'}]}
    manifest=equivalence_packets([left,right],ssd,tmp_path)
    packet=read_json(tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    schema=equivalence_output_schema(packet)
    row={'left_id':'rr','right_id':'sr','equivalent':False,'same_necessary_conditions':False,
        'same_actual_cause':False,'reason':'Concrete source comparison.','condition_equivalence':[],
        'evidence':{field:{'left':left[field],'right':right[field]}
            for field in ('exception_object','operation','failure_mechanism','trigger_condition')}}
    validate_output_shape({'decisions':[row]},schema)
    row.update(equivalent=True,same_necessary_conditions=True,same_actual_cause=True)
    validate_output_shape({'decisions':[row]},schema)
    row['evidence']['failure_mechanism']['right']='Paraphrased mechanism'
    with pytest.raises(ValueError,match='native output alternatives'):
        validate_output_shape({'decisions':[row]},schema)


@pytest.mark.parametrize('wrong_line', [False, True])
def test_transfer_quote_schema_binds_original_line_without_inventing_datums(wrong_line):
    exemplar = contract()
    exemplar['source_data_reviews'] = [{'line_id': 'original line', 'reason': 'inventory',
        'datums': [{'datum': 'original value', 'direction': 'request|response',
            'evidence_quote': 'literal source', 'mappings': [{'local_exchange_id': 'call',
                'field': 'field', 'reason': 'identity'}]}]}]
    lines = [{'line_id': 'clinic.md:L3', 'text': 'LabService writes the specimen record.'},
        {'line_id': 'clinic.md:L4', 'text': 'LabService returns the report.'}]
    schema = audit_output_schema(exemplar,
        audit_literal_quotes({'input': {'normal_source_lines': lines}}), lines)
    value = output()
    value['source_data_reviews'] = [{'line_id': 'clinic.md:L3', 'reason': 'source inventory',
        'datums': [{'datum': 'specimen record', 'direction': 'request',
            'evidence_quote': lines[int(wrong_line)]['text'], 'mappings': []}]},
        {'line_id': 'clinic.md:L4', 'reason': 'No invented return mapping.', 'datums': []}]
    before = deepcopy(value)
    if wrong_line:
        with pytest.raises(ValueError, match='native output alternatives'):
            validate_output_shape(value, schema)
    else:
        validate_output_shape(value, schema)
        assert value['line_reviews'][0]['covered'] is False
    assert value == before


@pytest.mark.parametrize('paraphrase', [False, True])
def test_quote_schema_restricts_literals_without_selecting_a_semantic_decision(paraphrase):
    exemplar = contract()
    exemplar['line_reviews'][0]['evidence_quote'] = 'literal original evidence'
    schema = audit_output_schema(exemplar, ['LabService calls SpecimenService.'])
    value = output()
    value['line_reviews'][0]['evidence_quote'] = ('LabService retrieves specimen.' if paraphrase
        else 'LabService calls SpecimenService.')
    if paraphrase:
        with pytest.raises(ValueError, match='native output enum'):
            validate_output_shape(value, schema)
    else:
        validate_output_shape(value, schema)
        assert value['line_reviews'][0]['covered'] is False


@pytest.mark.parametrize('wrong_line', [False, True])
def test_resource_quote_stays_on_selected_line_without_selecting_a_caller(wrong_line):
    exemplar = contract()
    exemplar['source_data_reviews'] = [{'line_id': 'line', 'reason': 'inventory',
        'datums': [{'datum': 'value', 'direction': 'request|response', 'evidence_quote': 'quote',
            'mappings': [{'local_exchange_id': 'call', 'field': 'field', 'reason': 'identity'}]}]}]
    exemplar['resource_operation_reviews'] = [{'resource_component_id': 'resource', 'reason': 'source',
        'operations': [{'line_id': 'line', 'caller_component_id': 'caller', 'caller_source_name': 'name',
            'operation': 'source operation', 'evidence_quote': 'quote', 'local_exchange_ids': ['call']}]}]
    lines = [{'line_id': 'clinic.md:L3', 'text': 'LabService reads specimens.'},
        {'line_id': 'clinic.md:L4', 'text': 'NotificationService sends a report.'}]
    schema = audit_output_schema(exemplar, audit_literal_quotes({'input': {'normal_source_lines': lines}}), lines)
    value = output()
    value['source_data_reviews'] = [{'line_id': x['line_id'], 'reason': 'No transfer asserted.', 'datums': []} for x in lines]
    value['resource_operation_reviews'] = [{'resource_component_id': 'specimens', 'reason': 'Missing original caller.',
        'operations': [{'line_id': lines[0]['line_id'], 'caller_component_id': '', 'caller_source_name': 'LabService',
            'operation': 'read', 'evidence_quote': lines[int(wrong_line)]['text'], 'local_exchange_ids': []}]}]
    before = deepcopy(value)
    if wrong_line:
        with pytest.raises(ValueError, match='native output alternatives'):
            validate_output_shape(value, schema)
    else:
        validate_output_shape(value, schema)
        assert value['resource_operation_reviews'][0]['operations'][0]['caller_component_id'] == ''
    assert value == before
    value['source_data_reviews'].pop()
    with pytest.raises(ValueError, match='native output array size'):
        validate_output_shape(value, schema)


@pytest.mark.parametrize('invalid', ['missing_issues', 'extra_field', 'nonboolean', 'enum', 'bad_reference'])
def test_shape_rejects_incomplete_or_invalid_output_without_normalizing(invalid):
    value = output()
    row = value['line_reviews'][0]
    if invalid == 'missing_issues':
        del row['issues']
    elif invalid == 'extra_field':
        row['invented'] = True
    elif invalid == 'nonboolean':
        row['covered'] = 1
    elif invalid == 'enum':
        row['classification'] = 'invented'
    else:
        row['source_refs'][0]['line_start'] = '3'
    before = deepcopy(value)
    with pytest.raises(ValueError, match='native output'):
        validate_output_shape(value, audit_output_schema(contract()))
    assert value == before


def test_native_structured_schema_is_pinned_hashed_and_portable(tmp_path, monkeypatch):
    executable = tmp_path / 'codex.exe'
    executable.write_bytes(b'fixture')
    monkeypatch.setattr('scene_completion.luna_subprocess.shutil.which', lambda _: str(executable))
    def runner(argv, **kwargs):
        schema_path = argv[argv.index('--output-schema') + 1]
        assert json.loads(Path(schema_path).read_text(encoding='utf-8')) == audit_output_schema(contract())
        text = json.dumps(output())
        with open(argv[argv.index('--output-last-message') + 1], 'w', encoding='utf-8') as stream:
            stream.write(text)
        events = [{'type': 'thread.started', 'thread_id': 'native-fixture'},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}},
            {'type': 'turn.completed'}]
        return subprocess.CompletedProcess(argv, 0, ('\n'.join(json.dumps(v) for v in events) + '\n').encode(), b'')
    root = tmp_path / 'original'
    client = LunaSubprocessClient({'native_run_dir': str(root / 'native-runs'),
        'reasoning_effort': 'high', 'native_structured_audit': True}, runner=runner)
    packet = {'batch_id': 'audit-1', 'input_hash': 'a' * 64,
        'stage': 'interaction-model-audit', 'output_contract': contract()}
    result = client.agent(packet)
    result.update(batch_id=packet['batch_id'], input_hash=packet['input_hash'], model=client.model('agent'))
    original_path = root / 'batches/audit/results/audit-1.json'
    validate_result_execution(result, result_path=original_path)
    destination = tmp_path / 'imported/batches/audit/results/audit-1.json'
    copied = copy_execution_sidecars(result, original_path, destination)
    assert len(copied) == 4 and any(p.name == 'output-schema.json' for p in copied)
    validate_result_execution(result, result_path=destination)
    native = result['execution_model_evidence']['native_execution']
    Path(native['schema_path']).write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='output schema'):
        validate_result_execution(result, result_path=original_path)
