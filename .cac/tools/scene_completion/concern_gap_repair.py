"""Source-only, rejected G scene repair; never consumes E or provisional GT."""
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
from . import concern_gap_batches as b,interaction_batches as old
from .semantic_backend import read_json,write_json,collect_packets,run_agent_packets
from .interaction_execution_identity import validate_result_execution
from .sources import fingerprint


def reverse_validator(packet,result):
    candidate=deepcopy(result)
    units={u['unit_id']:u for u in packet['input']['units']}
    originals={s['scenario_id']:s for s in packet['input']['original_scenarios']}
    for row in candidate.get('reviews',[]):
        if 'evidence_source_scenario_id' not in row:continue
        unit=units.get(row.get('unit_id'))
        if not unit or row['evidence_source_scenario_id']!=unit['source_scenario_id']:
            raise ValueError('reverse evidence pointer must reference this exact unit original source ID')
        row['evidence_quote']=originals[unit['source_scenario_id']]['trigger_condition']
        row['evidence_reference']='immutable_original_trigger'
    try:return b.review_validator(packet,candidate)
    except ValueError as exc:
        if 'condition evidence' not in str(exc):raise
        originals={s['scenario_id']:s for s in packet['input']['original_scenarios']}
        units={u['unit_id']:u for u in packet['input']['units']};bad=[]
        for row in result.get('reviews',[]):
            if row.get('unit_id') not in units:continue
            source=originals[units[row['unit_id']]['source_scenario_id']]
            options=[source['trigger_condition'],source['failure_mechanism']]
            quote=row.get('evidence_quote','')
            if not quote or not any(quote in text for text in options):
                bad.append({'unit_id':row['unit_id'],'incorrect_quote':quote,'exact_quote_choices':options})
        raise ValueError('For EVERY review you may return evidence_source_scenario_id equal to its input unit.source_scenario_id and omit evidence_quote: the tool attaches that immutable original trigger. Alternatively copy original_scenarios.trigger_condition EXACTLY. Do NOT quote original_evidence.text normal contracts. Keep semantic flags/decisions independent. '+str(exc)+'; incorrect rows and exact quote choices: '+str(bad)) from exc


def repair_packets(ssd,mounts,features,sources,rejections,directory,execution_version=None):
    by_id={s['scenario_id']:s for s in sources};by_mount={m['mount_id']:m for m in mounts}
    payloads=[]
    for rejection in rejections:
        source=by_id[rejection['source_scenario_id']]
        with TemporaryDirectory() as tmp:
            manifest=b.generation_packets(ssd,[by_mount[source['mount_id']]],features,tmp)
            original=read_json(Path(tmp)/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
        payload={k:v for k,v in original['input'].items() if k not in {'skill','protocol','execution_versions'}}
        payload.update(rejected_scenario_id=source['scenario_id'],rejected_scenario=source,
            independent_rejection=rejection['review'],repair_basis='G and positive SSD only; no E/test evidence',
            repair_tool_version=execution_version or fingerprint(Path(__file__).read_text(encoding='utf8')))
        payloads.append(payload)
    return b.prepare(directory,'gap-generation-repair',payloads,[
        'Re-generate replacement exception(s) for ONLY the supplied rejected G scenario from its existing actual SSD mount. No E or GT is supplied. Return rejected_scenario_id and items for that one mount. Other scenarios are already successful and must not be regenerated.',
        'Keep the actual exchange caller/callee and operation position. A nested service call is not the public entry receiving a request. Use only the current exchange positive contracts and permitted citations. Do not create interfaces/calls or append exceptions from original abnormal branches.',
        'Respect the exact concern cause: api.data.type means one mismatched value TYPE, never format, absent field or nonempty constraint. Missing/empty belongs to completeness. Do not combine type OR format or independently possible causes. If actual legal types are not specified, retain a conditional type-mismatch candidate with that unknown in pending_details, never pretend a format rule defines a type.',
        'For business constraints derive a concrete resource/state/legal positive prerequisite associated with this actual operation. Unknown detail stays pending. Do not invent response/recovery, new database relations or implementation mechanics. Keep at least one replacement for this rejected source; not an applicability filter or deletion.',
    ],{'rejected_scenario_id':'supplied G ID','items':[{'mount_id':'supplied mount ID','scenarios':[{
        'name':'atomic exception','exception_object':'actual object','operation':'actual operation',
        'failure_mechanism':'single cause','trigger_condition':'specific trigger','necessary_conditions':[],
        'pending_details':[],'source_refs':[]}]}]},'scene-concern-gap')


def repair_validator(index):
    def validate(packet,result):
        if result.get('rejected_scenario_id')!=packet['input']['rejected_scenario_id']:
            raise ValueError('wrong rejected source scene replacement')
        scenes=b.generation_validator(index)(packet,result)
        return [{'rejected_scenario_id':result['rejected_scenario_id'],'replacement_scenarios':scenes}]
    return validate


def rejected_sources(root):
    root=Path(root);index=read_json(root/'sources_index.json')
    units,state=collect_packets(root/'batches/gap-normalize-G',b.normalize_validator(index))
    if not state['complete']:raise ValueError('G normalization must be complete before source-only repair')
    by_id={u['unit_id']:u for u in units};folder=root/'batches/gap-reverse-check-G'
    manifest=read_json(folder/'manifest.json');found=[]
    stages=[('gap-reverse-check-G',manifest,reverse_validator)]
    confirm=root/'batches/gap-reverse-confirm-G'
    if (confirm/'manifest.json').exists():
        from .concern_gap_review_confirm import validator as confirm_validator
        stages.append(('gap-reverse-confirm-G',read_json(confirm/'manifest.json'),confirm_validator))
    resolved={}
    for stage,manifest,validator in stages:
      folder=root/'batches'/stage
      for batch in manifest['batches']:
        path=folder/'results'/(batch['batch_id']+'.json')
        if not path.exists():continue
        packet=read_json(folder/'packets'/(batch['batch_id']+'.json'));raw=read_json(path)
        validate_result_execution(raw,result_path=path)
        rows=validator(packet,deepcopy(raw))
        for row in rows:
            resolved[row['unit_id']]=(stage,batch,raw,row)
    for stage,batch,raw,row in resolved.values():
            if row['passed']:continue
            if not (row['source_supported'] is False or row['atomic'] is False or row['mapping_correct'] is False or row.get('defect_origin')=='generated_identification'):
                continue # A code-only error must never trigger generation.
            u=by_id[row['unit_id']]
            found.append({'unit_id':u['unit_id'],'source_scenario_id':u['source_scenario_id'],'review':row,
                'review_batch_id':batch['batch_id'],'review_stage_directory':stage,'review_result_hash':fingerprint(raw)})
    return found


def run(args):
    from .role_cli import _client
    root=Path(args.output_dir).resolve()
    folder=root/'batches/gap-reverse-check-G'
    for status in folder.glob('worker-status*.json'):
        if read_json(status).get('running'):raise ValueError('stop active reverse worker before repairing source G')
    rejections=rejected_sources(root)
    ids=getattr(args,'unit_id',None)
    if ids:
        known={r['unit_id'] for r in rejections}
        if not set(ids)<=known:raise ValueError('repair may select only source-rejected G units')
        rejections=[r for r in rejections if r['unit_id'] in ids]
    if not rejections:raise ValueError('no independently rejected source G scenes')
    ledger=read_json(root/'generation_repairs.json') if (root/'generation_repairs.json').exists() else []
    key=fingerprint(rejections)[:12];name='gap-generation-repair-'+key;directory=root/'batches'/name
    original=read_json(root/'generated_scenarios_base.json')['scenarios'] if (root/'generated_scenarios_base.json').exists() else read_json(root/'generated_scenarios.json')['scenarios']
    sources=[s for s in original if s['scenario_type']=='exception']
    ssd=read_json(root/'diagrams/ssd.json');mounts=read_json(root/'concern_mounts.json');features=read_json(root/'interaction_features.json')
    # Versioned repair stages keep old actual generator results intact.
    repair_packets(ssd,mounts,features,sources,rejections,directory)
    index=read_json(root/'sources_index.json');client=_client(args,root)
    state=run_agent_packets(directory,client,repair_validator(index))
    if not state['complete']:return {'complete':False,'stage':name,'state':state},2
    replacements,state=collect_packets(directory,repair_validator(index))
    for batch in read_json(directory/'manifest.json')['batches']:
        p=directory/'results'/(batch['batch_id']+'.json');validate_result_execution(read_json(p),result_path=p)
    record={'stage_directory':name,'rejections':rejections,'source_set_hash':fingerprint(sources),
        'replacements':replacements,'input_hash':read_json(directory/'manifest.json')['input_hash']}
    if not any(r['stage_directory']==name for r in ledger):ledger.append(record)
    write_json(root/'generation_repairs.json',ledger)
    return {'complete':True,'repaired_sources':len(replacements),'preserved_other_sources':len(sources)-len(replacements)},0


def apply_repairs(root,generated):
    path=Path(root)/'generation_repairs.json'
    if not path.exists():return generated
    result=list(generated)
    for record in read_json(path):
        current={s['scenario_id']:s for s in result};replace={r['rejected_scenario_id'] for r in record['replacements']}
        if not replace<=set(current):raise ValueError('repair targets changed or already replaced')
        replacements={r['rejected_scenario_id']:r['replacement_scenarios'] for r in record['replacements']}
        # Preserve successful packet groups and their order, not just their content.
        result=[v for s in result for v in replacements.get(s['scenario_id'],[s])]
    if len({s['scenario_id'] for s in result})!=len(result):raise ValueError('repair duplicated an existing atomic G scene')
    return result
