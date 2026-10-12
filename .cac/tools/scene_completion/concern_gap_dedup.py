"""Same-channel semantic deduplication of ambiguous necessary-condition views."""
from collections import defaultdict
from copy import deepcopy
from itertools import combinations
from . import concern_gap_batches as b
from .concern_gap import identity,merge_units
from .sources import fingerprint


def pairs(units):
    groups=defaultdict(list)
    for u in units:
        if u['mapping_status']=='mapped':groups[identity(u)[:4]].append(u)
    return [(l,r) for group in groups.values() for l,r in combinations(group,2) if identity(l)!=identity(r)]


def packets(units,ssd,collection,directory):
    ambiguous=pairs(units);payloads=[]
    for offset in range(0,len(ambiguous),12):
        group=ambiguous[offset:offset+12]
        ids={u['use_case_id'] for pair in group for u in pair}
        payloads.append({'collection':collection,'pairs':[{'left':l,'right':r} for l,r in group],
            'exchange_details':[e for e in ssd['exchanges'] if e['use_case_id'] in ids],
            'dedup_rule_version':fingerprint(__import__('inspect').getsource(pairs))})
    return b.prepare(directory,'gap-dedup-'+collection,payloads,[
        'Check ONLY supplied same-collection pairs. Other G/E/T collections are not supplied. They share an independently checked actual location/object/cause, but necessary-condition descriptions differ. Return every pair once.',
        'equivalent=true ONLY when the same actual abnormal cause and all necessary trigger constraints are semantically identical or the apparent difference is an ordinary prerequisite guaranteed by the supplied checked interaction. Explicitly explain why every condition difference does or does not change the exceptional event. Different bounds, scopes, resources, timing or additional causal prerequisites must remain distinct. Partial overlap is NOT equivalence. Responses/recovery cannot distinguish identity.',
        'G conditions are SSD-derived hypotheses; unknown details explicitly pending remain warnings. Do not reinterpret G as document-explicit facts. E/T source information and derivation markers cannot be rewritten. This stage groups duplicate views, never filters candidates or adds new ones.',
        'left_quote and right_quote must copy each unit trigger_condition EXACTLY. Do not quote normal source clauses or paraphrase. Preserve both unit IDs.'
    ],{'pairs':[{'left_unit_id':'supplied ID','right_unit_id':'supplied ID','equivalent':False,
        'left_quote':'exact trigger','right_quote':'exact trigger','condition_difference_reason':'specific necessary-condition reasoning'}]},'scene-reverse')


def validator(packet,result):
    expected={(p['left']['unit_id'],p['right']['unit_id']):p for p in packet['input']['pairs']}
    rows=result.get('pairs',[])
    if len(rows)!=len(expected) or {(r.get('left_unit_id'),r.get('right_unit_id')) for r in rows}!=set(expected):
        raise ValueError('dedup omitted or duplicated a same-channel pair')
    for row in rows:
        pair=expected[(row['left_unit_id'],row['right_unit_id'])]
        if type(row.get('equivalent')) is not bool or not row.get('condition_difference_reason'):
            raise ValueError('dedup needs explicit equivalence and condition reasoning')
        if row.get('left_quote')!=pair['left']['trigger_condition'] or row.get('right_quote')!=pair['right']['trigger_condition']:
            raise ValueError('dedup quotes must be complete original trigger conditions')
    return rows


def merge(units,prefix,decisions):
    expected={(l['unit_id'],r['unit_id']) for l,r in pairs(units)}
    if len(decisions)!=len(expected) or {(r['left_unit_id'],r['right_unit_id']) for r in decisions}!=expected:
        raise ValueError('incomplete same-channel equivalence decisions')
    parent={u['unit_id']:u['unit_id'] for u in units};by_id={u['unit_id']:u for u in units}
    def find(k):
        while parent[k]!=k:k=parent[k]
        return k
    # Already identical canonical identities and semantic equivalents share a unit.
    by_identity={}
    for u in units:
        if u['mapping_status']!='mapped':continue
        key=identity(u)
        if key in by_identity:parent[find(u['unit_id'])]=find(by_identity[key])
        else:by_identity[key]=u['unit_id']
    for d in decisions:
        if d['equivalent']:
            l,r=find(d['left_unit_id']),find(d['right_unit_id']);parent[max(l,r)]=min(l,r)
    if any(not d['equivalent'] and find(d['left_unit_id'])==find(d['right_unit_id']) for d in decisions):
        raise ValueError('contradictory transitive same-channel equivalence')
    lifted=[]
    for original in sorted(units,key=lambda u:(find(u['unit_id']),u['unit_id']!=find(u['unit_id']),u['unit_id'])):
        u=deepcopy(original);representative=by_id[find(u['unit_id'])]
        u['condition_codes']=deepcopy(representative['condition_codes'])
        lifted.append(u)
    result=merge_units(lifted,prefix)
    for row in result:
        for member in row['members']:
            original=by_id[member['unit_id']]
            member['original_necessary_conditions']=original['necessary_conditions']
            member['original_condition_codes']=original['condition_codes']
    return result
