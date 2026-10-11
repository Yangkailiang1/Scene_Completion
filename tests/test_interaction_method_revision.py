"""Cross-domain checks of actor completion and atomic one-to-one assessment."""
import copy
import itertools
import pytest

from scene_completion.interaction_assignment import assign_one_to_one
from scene_completion.interaction_equivalence import recommendation_units, eligible_pairs
from scene_completion.interaction_participants import architecture_context, participant_validator
from scene_completion.interaction_context import model_context_sections
from scene_completion.interaction_protocol import build_ssd, route_mounts
from scene_completion.interaction_metrics import compare, adoption
from scene_completion.sources import index_sources, validate_refs
from tests.test_interaction_protocol import model, scene, pair


def test_one_broad_candidate_cannot_cover_multiple_original_conditions():
    value = compare([scene('G')], [scene('C1'), scene('C2')], [pair('C1', 'G'), pair('C2', 'G')])
    assert value['layers']['RR']['overall']['miss_count'] == 1
    assert value['layers']['RR']['overall']['completeness'] == 1
    assert len(value['assignment']['eligible_but_unselected_pairs']) == 1


def test_assignment_reroutes_greedy_full_to_preserve_two_real_conditions():
    decisions = [pair('A', 'X'), pair('A', 'Y', 'partial'), pair('B', 'X')]
    result = assign_one_to_one(decisions)
    assert {(p['checker_scenario_id'], p['generated_scenario_id']) for p in result['selected_pairs']} == {('A', 'Y'), ('B', 'X')}
    assert result['full_count'] == result['partial_count'] == 1
    for ordering in itertools.permutations(decisions):
        assert assign_one_to_one(ordering) == result


def test_assignment_prefers_full_when_cardinality_equal_and_empty_is_valid():
    decisions = [pair('A', 'X', 'partial'), pair('A', 'Y'), pair('B', 'X'), pair('B', 'Y', 'partial')]
    result = assign_one_to_one(decisions)
    assert result['full_count'] == 2 and result['partial_count'] == 0
    assert assign_one_to_one([])['selected_pairs'] == []


def test_independent_partial_review_must_agree_on_each_condition_not_just_status():
    from scene_completion.interaction_batches import comparison_signature
    first = {**pair('C', 'G', 'partial'), 'condition_evidence': [
        {'checker_condition': 'deleted', 'relation': 'missing'}, {'checker_condition': 'off-sale', 'relation': 'supported'}],
        'missing_condition_evidence': [{'checker_field': 'necessary_conditions', 'checker_quote': 'deleted', 'detail': 'deleted'}]}
    independent = {**first, 'condition_evidence': [
        {'checker_condition': 'deleted', 'relation': 'supported'}, {'checker_condition': 'off-sale', 'relation': 'missing'}],
        'missing_condition_evidence': [{'checker_field': 'necessary_conditions', 'checker_quote': 'off-sale', 'detail': 'off-sale'}]}
    assert comparison_signature(first) != comparison_signature(independent)
    reordered = {**first, 'reason': 'Different wording', 'condition_evidence': list(reversed(first['condition_evidence']))}
    assert comparison_signature(first) == comparison_signature(reordered)


def test_nested_architecture_context_retains_parent_and_its_unheaded_members(tmp_path):
    path = tmp_path / 'clinic.md'
    path.write_text('# System architecture\nAuditService is internal.\n## External systems\nExternalLab is external.\n# Consult\nPatient opens a consultation.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    regions = architecture_context(index)
    assert len(regions) == 1 and regions[0]['line_start'] == 1 and regions[0]['line_end'] == 4
    assert 'AuditService' in regions[0]['numbered_text'] and 'ExternalLab' in regions[0]['numbered_text']


def medical_source(tmp_path):
    path = tmp_path / 'clinic.md'
    path.write_text('# System architecture\nExternalLab is an external service.\n# Consult-7\nParticipants: Patient\n## Basic flow\n1. ConsultAPI sends a specimen request to ExternalLab.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    refs = lambda n: validate_refs([{'document': path.name, 'line_start': n, 'line_end': n}], index)
    sections = [c for c in index['documents'][0]['chapters'] if c['title'] == 'Consult-7']
    packet = {'input': {'use_case_id': 'Consult-7', 'sections': sections, 'architecture_sections': architecture_context(index),
        'model_result_hash': 'source-bound-model', 'normal_model': {
            'components': [{'component_id': 'lab', 'name': 'ExternalLab', 'kind': 'external_service', 'layer': 'SR'}],
            'exchanges': [{'local_id': 'call-lab', 'requirement_layer': 'SR', 'from_component_id': 'entry', 'to_component_id': 'lab'}]}}}
    row = {'component_id': 'lab', 'status': 'missing_declaration', 'role_quote': 'ExternalLab is an external service.',
        'role_refs': refs(2), 'interaction_quote': 'ConsultAPI sends a specimen request to ExternalLab.',
        'interaction_refs': refs(6), 'declared_participant_quote': '', 'participant_refs': [],
        'reason': 'Participant list omits the lab while normal flow explicitly invokes it.'}
    return index, packet, {'component_reviews': [row], 'missing_model_calls': [], 'unresolved_candidates': []}


def test_actor_completion_has_real_call_but_does_not_authorize_source_edits(tmp_path):
    index, packet, result = medical_source(tmp_path)
    value = participant_validator(index)(packet, result)[0]
    assert value['passed'] and value['actor_completions'][0]['participant_name'] == 'ExternalLab'
    assert value['actor_completions'][0]['document_edit_requires_confirmation']
    assert not {'generated', 'checker', 'test_scenarios'} & packet['input'].keys()


def test_unlabelled_optional_actor_requires_source_audit_bound_to_its_exchange(tmp_path):
    index, packet, result = medical_source(tmp_path)
    doc = index['documents'][0]
    doc['text'] = doc['text'].replace('## Basic flow', '## Alternative flows')
    packet['input']['normal_model']['exchanges'][0]['path_type'] = 'alternative'
    with pytest.raises(ValueError, match='actual own-use-case normal interaction'):
        participant_validator(index)(packet, result)
    packet['input']['normal_source_audit'] = {'passed': True, 'model_result_hash': packet['input']['model_result_hash'],
        'exchange_reviews': [{'local_exchange_id': 'call-lab', 'supported': True,
            'source_refs': result['component_reviews'][0]['interaction_refs']}]}
    assert participant_validator(index)(packet, result)[0]['passed']
    packet['input']['normal_source_audit']['model_result_hash'] = 'stale'
    with pytest.raises(ValueError, match='actual own-use-case normal interaction'):
        participant_validator(index)(packet, result)


@pytest.mark.parametrize('mutation', ['architecture_only', 'not_involved', 'fake_boundary', 'fake_AR', 'missing_review'])
def test_actor_completeness_cannot_be_faked_from_architecture_alone(tmp_path, mutation):
    index, packet, result = medical_source(tmp_path)
    row = result['component_reviews'][0]
    if mutation == 'architecture_only':
        row.update(interaction_quote=row['role_quote'], interaction_refs=row['role_refs'])
    elif mutation == 'not_involved':
        row['status'] = 'not_involved'
    elif mutation == 'fake_boundary':
        row['status'] = 'logical_boundary'
    elif mutation == 'fake_AR':
        row['status'] = 'implementation_only'
    else:
        result['component_reviews'] = []
    with pytest.raises(ValueError):
        participant_validator(index)(packet, result)


def test_global_reference_definitions_are_context_not_new_use_cases(tmp_path):
    path = tmp_path / 'clinic.md'
    path.write_text('# Requirement definitions\n| R-Care-8 | Specimen processing |\n# Consult-7\nRelated requirement: R-Care-8\n## Basic flow\n1. Patient requests a specimen collection.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    sections = [c for c in index['documents'][0]['chapters'] if c['title'] == 'Consult-7']
    original = copy.deepcopy(sections)
    contexts = model_context_sections(index, sections)
    assert sections == original
    assert len(contexts) == 1 and contexts[0]['line_start'] == contexts[0]['line_end'] == 2
    assert contexts[0]['context_kind'] == 'referenced_requirement_definition'


def test_rr_business_role_has_real_layer_mapping_and_cancel_is_not_exception(tmp_path):
    path = tmp_path / 'rr.md'
    path.write_text('# Requirements\n## UC-1\n系统查询商品编号并显示结果。\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    raw = model(index)
    rr = raw['use_cases'][0]['exchanges'][0]
    rr.update(cancellable=True, business_service_roles=[{'service_type': 'query_retrieval',
        'source_refs': rr['source_refs'], 'evidence_quote': '系统查询商品编号并显示结果。', 'mapped_sr_local_ids': ['sr1', 'sr2']}])
    ssd = build_ssd(raw)
    mounts = route_mounts(ssd)
    business = [m for m in mounts if m.get('business_role_id')]
    assert len(business) == 3 and all(m['requirement_layer'] == 'RR' for m in business)
    assert len(business[0]['mapped_sr_exchange_ids']) == 2
    assert not any(m['concern_key'] == 'service.workflow.interruption' for m in mounts)
    rr['business_service_roles'][0]['mapped_sr_local_ids'] = ['invented-call']
    with pytest.raises(ValueError, match='real SR expansions'):
        build_ssd(raw)


def test_cross_layer_recommendations_same_cause_count_once_but_other_concern_remains():
    key = 'api.data.format'
    rr, sr, other = scene('rr', keys=[key]), scene('sr', 'SR', keys=['internal_database.resource_existence']), scene('other', 'SR', keys=['api.data.type'])
    other.update(failure_mechanism='字段类型不符', trigger_condition='字段类型与契约不符')
    rr['exchange_id'], sr['exchange_id'], other['exchange_id'] = 'rr-call', 'sr-call', 'sr-call'
    ssd = {'exchanges': [{'exchange_id': 'rr-call'}, {'exchange_id': 'sr-call', 'parent_exchange_id': 'rr-call'}]}
    pairs = eligible_pairs([rr, sr, other], ssd)
    assert len(pairs) == 2
    decisions = [{'left_id': 'rr', 'right_id': 'sr', 'equivalent': True}, {'left_id': 'rr', 'right_id': 'other', 'equivalent': False}]
    result = recommendation_units([rr, sr, other], ssd, decisions)
    assert result['original_recommendation_count'] == 3 and result['unique_unit_count'] == 2
    joint = next(s for s in result['units'] if len(s['member_scenario_ids']) == 2)
    assert joint['member_scenario_ids'] == ['rr', 'sr'] and joint['source_layers'] == ['RR', 'SR']
    assert joint['representative_scenario_id'] == 'sr'
    assert joint['causal_unit_count'] == 1
    assert joint['member_concerns'] == {'rr': ['api.data.format'], 'sr': ['internal_database.resource_existence']}
    assert joint['concern_keys'] == ['api.data.format', 'internal_database.resource_existence']
    with pytest.raises(ValueError, match='incomplete'):
        recommendation_units([rr, sr, other], ssd, [])


def test_equivalence_cannot_hide_extra_or_contradictory_necessary_conditions():
    from scene_completion.interaction_equivalence import equivalence_validator
    left, right = scene('RR'), scene('SR', 'SR')
    left['necessary_conditions'] = ['under same owner']
    packet = {'input': {'left': left, 'right': right, 'left_concerns': left['concern_keys'], 'right_concerns': right['concern_keys']}}
    result = {'equivalent': True, 'same_actual_cause': True, 'same_necessary_conditions': True, 'reason': 'same cause',
        'evidence': {k: {'left': left[k], 'right': right[k]} for k in ('exception_object', 'operation', 'failure_mechanism', 'trigger_condition')}}
    with pytest.raises(ValueError, match='every necessary condition'):
        equivalence_validator(packet, result)
    right['necessary_conditions'] = ['for identical owner']
    result['condition_equivalence'] = [{'left_condition': 'under same owner', 'right_condition': 'for identical owner',
        'same_condition': True, 'reason': 'same ownership prerequisite'}]
    assert equivalence_validator(packet, result)[0]['equivalent']
    result['condition_equivalence'][0]['same_condition'] = False
    with pytest.raises(ValueError, match='contradictory'):
        equivalence_validator(packet, result)
    left['necessary_conditions'].append('same revision')
    result['condition_equivalence'][0]['same_condition'] = True
    result['condition_equivalence'].append({'left_condition': 'same revision', 'right_condition': 'for identical owner',
        'same_condition': True, 'reason': 'fabricated repeated support'})
    with pytest.raises(ValueError, match='one-to-one atomic'):
        equivalence_validator(packet, result)


def test_batched_equivalence_keeps_negative_decisions_and_rejects_omissions(tmp_path):
    from scene_completion.interaction_equivalence import equivalence_packets, equivalence_validator
    from scene_completion.semantic_backend import read_json
    left = scene('rr')
    left['exchange_id'] = 'rr-call'
    right = [scene('sr'+str(i), 'SR') for i in range(17)]
    for item in right:
        item['exchange_id'] = 'sr-call'
    ssd = {'exchanges': [{'exchange_id':'rr-call'}, {'exchange_id':'sr-call','parent_exchange_id':'rr-call'}]}
    manifest = equivalence_packets([left,*right],ssd,tmp_path)
    packets = [read_json(tmp_path/'packets'/(b['batch_id']+'.json')) for b in manifest['batches']]
    assert sum(len(p['input']['pairs']) for p in packets) == len(eligible_pairs([left,*right],ssd))
    packet = packets[0]
    decisions = []
    for data in packet['input']['pairs']:
        decisions.append({'left_id':data['left']['scenario_id'],'right_id':data['right']['scenario_id'],
            'equivalent':False,'same_necessary_conditions':False,'same_actual_cause':False,'reason':'Different actual cause.',
            'evidence':{k:{side:data[side][k] for side in ('left','right')}
                for k in ('exception_object','operation','failure_mechanism','trigger_condition')}})
    assert all(not r['equivalent'] for r in equivalence_validator(packet,{'decisions':decisions}))
    with pytest.raises(ValueError,match='every source-mapped pair'):
        equivalence_validator(packet,{'decisions':decisions[:-1]})
    with pytest.raises(ValueError,match='every source-mapped pair'):
        equivalence_validator(packet,{'decisions':[decisions[0]]*len(decisions)})


def test_one_test_unit_cannot_adopt_two_recommendations_and_derived_is_labeled():
    recs = [scene('r1', 'SR'), scene('r2')]
    tests = [{**scene('t', 'TEST'), 'source_basis': 'framework_derived'}]
    result = adoption(recs, tests, [pair('t', 'r1'), pair('t', 'r2')])
    assert result['adopted_count'] == 1 and result['adoption_rate'] == .5
    assert result['derived_adopted_count'] == 1 and result['explicit_adopted_count'] == 0
