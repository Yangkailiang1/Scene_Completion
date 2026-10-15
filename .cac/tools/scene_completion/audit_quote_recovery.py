"""Explicit, offline revalidation of source-audit quote layout failures."""
from pathlib import Path
from types import SimpleNamespace
from .case_dag import run_lock
from .semantic_backend import read_json, write_json, collect_packets
from .sources import fingerprint
from .interaction_audit import recover_quote_format_attempts, checker_audit_validator


def recover_graph_attempts(folder,index):
    import copy
    from .concern_gap_batches import graph_validator
    from .interaction_execution_identity import validate_result_execution
    root=Path(folder);recovered=[]
    for batch in read_json(root/'manifest.json')['batches']:
        target=root/'results'/(batch['batch_id']+'.json')
        if target.exists():continue
        packet=read_json(root/'packets'/target.name)
        if fingerprint({k:v for k,v in packet.items() if k not in ('batch_id','input_hash')})!=batch['input_hash']:
            raise ValueError('graph format recovery packet changed')
        for attempt in sorted((root/'attempts').glob(batch['batch_id']+'-*.json'),reverse=True):
            record=read_json(attempt);raw=record.get('result')
            if record.get('validation_error')!='graph check must inspect every node and exchange' or not isinstance(raw,dict):continue
            if raw.get('batch_id')!=batch['batch_id'] or raw.get('input_hash')!=batch['input_hash']:continue
            validate_result_execution(raw,result_path=attempt)
            try:rows=graph_validator(index)(packet,copy.deepcopy(raw))
            except (ValueError,KeyError,TypeError):continue
            if not all(row['valid'] for row in rows):continue
            target.parent.mkdir(parents=True,exist_ok=True);write_json(target,raw)
            recovered.append({'batch_id':batch['batch_id'],'source_attempt':str(attempt.resolve()),
                'source_attempt_hash':fingerprint(record),'result_hash':fingerprint(raw),
                'reason':'Unique supplied local exchange IDs resolved to canonical IDs; original graph checks fully revalidated.'})
            break
    return recovered


def run(args):
    from .concern_gap_dag import Pipeline
    root=Path(args.output_dir).resolve()
    with run_lock(root):
        manifest=read_json(root/'run_manifest.json')
        if manifest.get('execution_mode')!='case-dag' or manifest.get('protocol')!='rr-sr-concern-gap-v2':
            raise ValueError('offline quote revalidation requires a v2 case-DAG run')
        if manifest.get('complete'):
            return {'already_complete':True,'model_calls':0,'recovered_batches':[]},0
        stage=(args.stage if args.command=='revalidate-cached-task' else
            ('graphs' if args.command=='revalidate-graph-format' else 'E-audit'))
        saved=read_json(root/'pipeline_arguments.json')
        pipeline=Pipeline(SimpleNamespace(**saved))
        if any(pipeline.manifest.get(key)!=manifest.get(key) for key in ('source_hash','base_hash','scope')):
            raise ValueError('offline format revalidation cannot change original source, base model or selected scope')
        def no_network(*a,**k):
            raise RuntimeError('offline quote revalidation forbids model or embedding calls')
        pipeline.client.agent=no_network
        pipeline.client.post=no_network
        pipeline.embedding.embeddings=no_network
        pipeline.embedding.post=no_network
        try:
            pipeline.build()
            selected=set(getattr(args,'use_case_id',None) or pipeline.contexts)
            if not selected<=set(pipeline.contexts):raise ValueError('unknown selected use case')
            pipeline.scheduler._refresh()
            if stage=='graphs':
                pipeline.scheduler.run(pipeline.progress,allowed=[pipeline.key(case,'authorization') for case in selected])
                pipeline.scheduler._refresh()
            recovered=[];allowed=[]
            for case in sorted(selected):
                key=pipeline.key(case,stage)
                if key not in pipeline.scheduler.tasks:raise ValueError('unknown selected semantic stage')
                record=pipeline.scheduler.state['tasks'][key]
                if record['status']=='passed':continue
                if record.get('input_hash')!=pipeline.scheduler.input_hash(pipeline.scheduler.tasks[key]):continue
                context=pipeline.contexts[case]
                if args.command=='revalidate-cached-task':
                    task=pipeline.scheduler.tasks[key]
                    if not task.compatible or not record.get('output_file') or not any(a['status']=='passed' for a in record['attempts']):
                        continue
                    output=read_json(root/record['output_file'])
                    deps={k:read_json(root/pipeline.scheduler.state['tasks'][k]['output_file']) for k in task.deps}
                    task.compatible(deps,output)
                    proof=[{'original_output':record['output_file'],'result_hash':fingerprint(output),
                        'reason':'Semantic payload, instructions and contract unchanged; current validator and execution proof rechecked offline.'}]
                    write_json(context['root']/'active'/(stage+'.json'),{'input_hash':record['input_hash'],'output':output})
                    pipeline.scheduler.state['events'].append({'task':key,'event':'offline_compatible_revalidation',
                        'previous_status':record['status'],'round':record['rounds'],'recoveries':proof})
                    record['status']='pending';record.pop('reuse_reserved_round',None)
                    recovered.extend(proof);allowed.append(key)
                    continue
                folders=[context['root']/'batches'/stage,
                    *sorted((context['root']/'batches').glob(stage+'-repair-*'))]
                # Keep the latest real execution, without changing its identity.
                for folder in reversed(folders):
                    if not (folder/'manifest.json').exists():continue
                    validator=pipeline.graph_validator if stage=='graphs' else checker_audit_validator(pipeline.index)
                    proof=(recover_graph_attempts if stage=='graphs' else recover_quote_format_attempts)(folder,pipeline.index)
                    values,status=collect_packets(folder,validator)
                    flag='valid' if stage=='graphs' else 'passed'
                    if not status['complete'] or not all(row[flag] for row in values):continue
                    if not proof:
                        prior=record.get('output_file')
                        if not prior or read_json(root/prior).get('folder')!=str(folder.resolve()):continue
                        proof=[{'existing_execution_revalidated':str(folder.resolve()),'reason':'Original source-bound checks remain valid under format normalization.'}]
                    output=pipeline.packets.execute(folder,validator)
                    if stage=='graphs':output=pipeline.component_records(output)
                    write_json(context['root']/'active'/(stage+'.json'),
                        {'input_hash':record['input_hash'],'output':output})
                    pipeline.scheduler.state['events'].append({'task':key,'event':'offline_format_revalidation',
                        'previous_status':record['status'],'round':record['rounds'],'recoveries':proof,
                        'output_hash':fingerprint(output)})
                    # Schedule the original validator; never write a passed label.
                    record['status']='pending'
                    record.pop('reuse_reserved_round',None)
                    recovered.extend(proof);allowed.append(key)
                    break
            pipeline.scheduler.save()
            pipeline.scheduler.run(pipeline.progress,allowed=allowed)
            tasks={pipeline.key(case,stage):pipeline.scheduler.state['tasks'][pipeline.key(case,stage)]['status'] for case in sorted(selected)}
            result={'recovered_batches':recovered,'tasks':tasks,
                'model_calls':0,'repair_rounds_preserved':True}
            write_json(root/(stage+'_format_revalidation.json'),result)
            return result,0 if all(value=='passed' for value in result['tasks'].values()) else 2
        finally:
            if pipeline.profiler:pipeline.profiler.finish('offline_quote_revalidation')
