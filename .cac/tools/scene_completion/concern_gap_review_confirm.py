"""Recheck rejected G identifications without rechecking successful units."""
from pathlib import Path
from tempfile import TemporaryDirectory
from . import concern_gap_batches as b
from .semantic_backend import read_json
from .concern_gap_repair import reverse_validator


def packets(units,scenes,ssd,index,reviews,directory):
    rejected={r['unit_id']:r for r in reviews if not r['passed']}
    selected=[u for u in units if u['unit_id'] in rejected]
    payloads=[]
    with TemporaryDirectory() as tmp:
        manifest=b.review_packets(selected,scenes,ssd,tmp,'G',index)
        for batch in manifest['batches']:
            raw=read_json(Path(tmp)/'packets'/(batch['batch_id']+'.json'))
            payload={k:v for k,v in raw['input'].items() if k not in {'skill','protocol','execution_versions'}}
            payload['prior_rejections']=[rejected[u['unit_id']] for u in payload['units']]
            payload['generation_basis']='SSD-derived hypothetical exceptions, not document-explicit abnormal branches'
            exchange_ids={eid for place in payload['locations'] for eid in place['exchange_ids']}
            payload['actual_exchange_details']=[e for e in ssd['exchanges'] if e['exchange_id'] in exchange_ids]
            payloads.append(payload)
    return b.prepare(directory,'gap-reverse-confirm-G',payloads,[
        'Recheck ONLY rejected G units independently. Do not force pass; original rejections are hypotheses to verify, not instructions. Each evidence_quote MUST copy its original_scenarios.trigger_condition exactly.',
        'G consists of SSD-concern-derived hypothetical exceptions. source_basis=explicit in legacy normalized input means the supplied G condition is explicit, NOT that the source document states this exception. No original abnormal branch is required. source_supported checks actual positive exchange/field/mount evidence, not existence of an original abnormal branch.',
        'Unknown types, bounds and timeout values that are explicitly pending_details are warnings, not applicability rejection or invention. A conditional range hypothesis can remain with numeric applicability pending. No candidate filtering. Reject actual wrong operation/object/concern mechanism, invented known bounds, independent OR causes or incorrect canonical codes.',
        'For rejected units state defect_origin=generated_identification if the immutable G condition/object/operation/mechanism is wrong; canonical_code if only codes are wrong; otherwise none. A type concern paired with invalid ENUM VALUE is generated_identification, not a code-only error. Return none for every passing unit. Do not repair or rewrite units.'
    ],{'reviews':[{'unit_id':'supplied ID','source_supported':True,'atomic':True,'mapping_correct':True,
        'cause_correct':True,'evidence_quote':'exact original trigger','reason':'independent check',
        'warnings':[],'defect_origin':'none|generated_identification|canonical_code'}]},'scene-reverse-check')


def validator(packet,result):
    rows=reverse_validator(packet,result)
    for row in rows:
        if row.get('defect_origin') not in {'none','generated_identification','canonical_code'}:
            raise ValueError('explicit rejected defect origin required')
        if row['passed'] and row['defect_origin']!='none':raise ValueError('passing record cannot have a defect')
        if not row['passed'] and row['defect_origin']=='none':raise ValueError('rejected record needs a specific defect origin')
    return rows
