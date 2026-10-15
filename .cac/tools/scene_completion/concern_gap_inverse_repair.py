"""Repair rejected inverse units from the same original channel only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
from . import concern_gap_batches as b
from .semantic_backend import read_json,write_json,collect_packets,run_agent_packets
from .concern_gap_normalize_diagnostics import validator
from .concern_gap_repair import reverse_validator
from .interaction_execution_identity import validate_result_execution,copy_execution_sidecars
from .sources import fingerprint
from .artifact_paths import relative_artifact_path


def packets(source,ssd,index,collection,rejections,prior,directory):
    payloads=[]
    with TemporaryDirectory() as tmp:
        manifest=b.normalized_packets(source,ssd,tmp,collection,index)
        for batch in manifest['batches']:
            packet=read_json(Path(tmp)/'packets'/(batch['batch_id']+'.json'))
            payload={k:v for k,v in packet['input'].items() if k not in {'skill','protocol','execution_versions'}}
            ids={s['scenario_id'] for s in payload['scenarios']}
            payload['prior_rejected_units']=[u for u in prior if u['source_scenario_id'] in ids]
            payload['source_only_rejections']=rejections
            payloads.append(payload)
    instructions=packet['instructions']+[
        'Repair ONLY this independent channel from its supplied original conditions and positive checked interaction graph. Other G/E/T collections are absent. Prior rejection is evidence to verify, not an instruction to pass. Preserve all source conditions, including valid atomic alternatives of the same source. No source-document edits or new calls/objects/concerns.',
        'Local entrance authentication/authorization/parameter checks belong to the incoming request boundary, not a downstream business call merely sharing the use case. Use actual location operations and exchange_details. No established location must remain faithfully unmapped. Evidence_quote must copy original scenario trigger_condition exactly.'
    ]
    return b.prepare(directory,'gap-normalization-repair-'+collection,payloads,instructions,
        packet['output_contract'],'scene-reverse')


def ledger(root,collection):
    path=Path(root)/('normalization_repairs_'+collection+'.json')
    return read_json(path) if path.exists() else []


def apply(units,records):
    result=deepcopy(units)
    for record in records:
        ids={s['scenario_id'] for s in record['sources']}
        before=[u for u in result if u['source_scenario_id'] in ids]
        if before!=record['prior_units']:raise ValueError('inverse repair prior units changed')
        replacements=record['replacements']
        if {u['source_scenario_id'] for u in replacements}!=ids:raise ValueError('inverse repair dropped or added a source scenario')
        remaining={k:[u for u in replacements if u['source_scenario_id']==k] for k in ids}
        result=[v for u in result for v in (remaining.pop(u['source_scenario_id'],[]) if u['source_scenario_id'] in ids else [u])]
    if len({u['unit_id'] for u in result})!=len(result):raise ValueError('inverse repair duplicated unit IDs')
    return result


def run(args):
    from .role_cli import _client
    root=Path(args.output_dir).resolve();collection=args.collection
    index=read_json(root/('test_sources_index.json' if collection=='T' else 'sources_index.json'))
    units,state=collect_packets(root/'batches'/('gap-normalize-'+collection),validator(index))
    if not state['complete']:raise ValueError('inverse base normalization incomplete')
    records=ledger(root,collection);units=apply(units,records);by_id={u['unit_id']:u for u in units}
    source_file={'G':'generated_scenarios.json','E':'existing_scenarios.json','T':'test_conditions.json'}[collection]
    sources=read_json(root/source_file)['scenarios'];sources=[s for s in sources if s.get('scenario_type')=='exception']
    review_dir=root/'batches'/('gap-reverse-check-'+collection)
    reviews,state=collect_packets(review_dir,reverse_validator)
    bad=[r for r in reviews if not r['passed'] and (not args.unit_id or r['unit_id'] in args.unit_id)]
    if not bad:raise ValueError('no actually rejected current inverse units selected')
    if args.unit_id and set(args.unit_id)!={r['unit_id'] for r in bad}:raise ValueError('unknown or passing repair selection')
    ids={by_id[r['unit_id']]['source_scenario_id'] for r in bad}
    sources=[s for s in sources if s['scenario_id'] in ids]
    prior=[u for u in units if u['source_scenario_id'] in ids]
    name='gap-normalization-repair-'+collection+'-'+fingerprint([bad,prior])[:12];directory=root/'batches'/name
    rejections=[]
    for batch in read_json(review_dir/'manifest.json')['batches']:
        result_path=review_dir/'results'/(batch['batch_id']+'.json')
        if not result_path.exists():continue
        packet=read_json(review_dir/'packets'/(batch['batch_id']+'.json'));raw=read_json(result_path)
        found=[r for r in reverse_validator(packet,deepcopy(raw)) if r in bad]
        if not found:continue
        validate_result_execution(raw,result_path=result_path)
        destination=root/'inverse_repair_evidence'/fingerprint(raw)/'result.json'
        write_json(destination,raw);copy_execution_sidecars(raw,result_path,destination)
        write_json(destination.with_name('packet.json'),packet)
        rejections.append({'reviews':found,'result_path':destination.relative_to(root).as_posix(),
            'packet_path':destination.with_name('packet.json').relative_to(root).as_posix(),'result_hash':fingerprint(raw)})
    graph=read_json(root/('historical_ssd.json' if collection=='E' else 'diagrams/ssd.json'))
    packets(sources,graph,index,collection,rejections,prior,directory)
    state=run_agent_packets(directory,_client(args,root),validator(index))
    if not state['complete']:return {'complete':False,'stage':name,'state':state},2
    replacement,state=collect_packets(directory,validator(index))
    record={'stage_directory':name,'sources':sources,'prior_units':prior,'rejections':rejections,'replacements':replacement}
    apply(units,[record])
    if not any(r['stage_directory']==name for r in records):records.append(record)
    write_json(root/('normalization_repairs_'+collection+'.json'),records)
    return {'complete':True,'collection':collection,'repaired_source_count':len(sources)},0


def verify(root,units,records,outputs):
    root=Path(root);current=deepcopy(units)
    for record in records:
        prior={u['unit_id']:u for u in record['prior_units']}
        for evidence in record['rejections']:
            path=relative_artifact_path(root,evidence['result_path']);raw=read_json(path)
            packet=read_json(relative_artifact_path(root,evidence['packet_path']))
            if (fingerprint(raw)!=evidence['result_hash'] or raw['input_hash']!=packet['input_hash']
                or packet['input_hash']!=fingerprint({k:v for k,v in packet.items() if k not in {'batch_id','input_hash'}})):
                raise ValueError('inverse rejection execution changed')
            validate_result_execution(raw,result_path=path)
            actual=reverse_validator(packet,deepcopy(raw))
            if not all(r in actual and not r['passed'] and r['unit_id'] in prior for r in evidence['reviews']):
                raise ValueError('inverse repair is not backed by actual rejected units')
            for u in packet['input']['units']:
                if u['unit_id'] in prior and u!=prior[u['unit_id']]:raise ValueError('inverse rejected unit changed')
        if outputs[record['stage_directory']]!=record['replacements']:raise ValueError('inverse replacement differs from actual execution')
        current=apply(current,[record])
    return current
