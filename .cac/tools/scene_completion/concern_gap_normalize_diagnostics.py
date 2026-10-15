"""Precise retry feedback; never fills or edits semantic normalization results."""
from copy import deepcopy
from . import concern_gap_batches as b
from .response_contract import contract_view, source_id_differences


def validator(index):
    check=b.normalize_validator(index)
    def validate(packet,result):
        # RR and its public SR view can name the same real interaction. Resolve
        # only explicit exchange membership; never infer a different operation.
        candidate=contract_view(packet, result)
        if packet['input'].get('normalization_evidence_patch'):
            return check(packet, candidate)
        data=packet['input'];sources={s['scenario_id']:s for s in data['scenarios']}
        for item in candidate.get('items',[]):
            source=sources.get(item.get('source_scenario_id'))
            if not source or data['collection']=='G':continue
            for unit in item.get('units',[]):
                place=next((c for c in data['locations'] if c['use_case_id']==source['use_case_id']
                    and unit.get('location_id') in c['exchange_ids']),None)
                if place and unit.get('mapping_status')=='mapped':unit['location_id']=place['location_id']
        try:return check(packet,candidate)
        except ValueError as exc:
            data=packet['input'];details=[]
            by_id={s['scenario_id']:s for s in data['scenarios']}
            for item in candidate.get('items',[]):
                source=by_id.get(item.get('source_scenario_id'))
                if not source:continue
                one=deepcopy(packet);one['input']['scenarios']=[source]
                try:check(one,{'items':[item]})
                except (ValueError,KeyError,TypeError) as error:
                    details.append({'source_id':source['scenario_id'],'error':str(error),
                        'exact_condition':source['trigger_condition'],
                        'expected_condition_code_count':len(source.get('necessary_conditions',[])),
                        'actual_condition_code_counts':[len(u.get('condition_codes',[]))
                            if isinstance(u.get('condition_codes'),list) else None for u in item.get('units',[])],
                        'allowed_locations':[c['location_id'] for c in data['locations'] if c['use_case_id']==source['use_case_id']]})
            shape = source_id_differences(by_id, [item.get('source_scenario_id') for item in candidate.get('items', [])])
            raise ValueError('evidence_quote MUST copy scenes.trigger_condition exactly, not original_evidence.text/document normal contracts. Mapped location_id MUST be an input.locations.location_id of this same use case (not an exchange_id or step name); absent valid mapping must stay unmapped. concern_key MUST be an exact concern_definitions key. Keep all semantic identification source-backed. '+str(exc)+'; collection_shape: '+str(shape)+'; invalid source units: '+str(details)) from exc
    return validate
