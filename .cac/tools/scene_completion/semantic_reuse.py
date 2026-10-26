"""Reuse verified model responses across tool-only display/identity changes.

Only this v4 run's responses qualify. A seed is rebound to the same independent
task input projection, Skill and model owner, then validated again by the caller.
"""
from copy import deepcopy
from .storage import fingerprint,read_json

DERIVED={'element_id','binding_id','case_id','direction','identification','classification_origin','element_origin','caller','callee',
         'status','status_reason','inheritance_paths','service','functional_types','technologies'}


def identity(task,inputs,skill,output,model,endpoint,guidance):
    from .task_context import semantic_view
    contract=deepcopy(output)
    if task in {'concern-match','existing-concerns','test-concerns'}:
        properties=contract['properties']['matches']['items']['properties']
        for key in DERIVED:properties.pop(key,None)
        contract['properties'].pop('excluded',None)
    if task in {'exception-generate','existing-extract','test-ground-truth'}:
        properties=contract['properties']['scenarios']['items']['properties']
        for key in ('concern_binding_ids','element_anchors','matching_version'):properties.pop(key,None)
    if 'excluded' in contract.get('properties',{}):
        for key in ('interaction_id','object','concern_key'):contract['properties']['excluded']['items']['properties'].pop(key,None)
    return fingerprint([task,semantic_view(task,inputs),skill,contract,model,endpoint,guidance])


def index(root,model,endpoint,conversations):
    from .contracts import PROTOCOL
    eligible={'concern-match','existing-concerns','test-concerns','existing-extract','test-ground-truth'}
    seeds={}
    for path in (root/'packets').glob('*.json'):
        p=read_json(path);task=p.get('task')
        if task not in eligible or p.get('protocol')!=PROTOCOL:continue
        key=p.get('node_key',task);guidance=conversations.revision(key)
        # Historical raw-cache identity predates presentation-independent keys.
        old=fingerprint({'task':task,'input':p['input'],'skill':p.get('skill_text'),'schema':p['output_schema'],
                         'endpoint':endpoint,'model':model,'guidance':guidance})
        file=root/'semantic_responses'/(old+'.json')
        if not file.exists():continue
        try:
            normalized=identity(task,p['input'],p.get('skill_text'),p['output_schema'],model,endpoint,guidance)
        except (KeyError,ValueError,TypeError):continue
        seeds[normalized]=file
    return seeds
