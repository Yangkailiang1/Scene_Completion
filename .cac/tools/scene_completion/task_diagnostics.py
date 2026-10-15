"""Refresh concrete tool errors from saved executions without spending model calls."""
from pathlib import Path
import copy
import inspect
from types import SimpleNamespace
from .semantic_backend import read_json,write_json
from .interaction_execution_identity import validate_result_execution
from .case_dag import run_lock,failure_signature
from .sources import fingerprint


def run(args):
    from .concern_gap_dag import Pipeline
    root=Path(args.output_dir).resolve()
    with run_lock(root):
        pipeline=Pipeline(SimpleNamespace(**read_json(root/'pipeline_arguments.json')))
        def no_network(*a,**k):raise RuntimeError('diagnostic refresh forbids external calls')
        for name in ('client','embedding'):
            client=getattr(pipeline,name,None)
            if client is not None:
                client.post=no_network
                client.agent=no_network
                client.embeddings=no_network
        try:
            pipeline.build();pipeline.scheduler._refresh()
            selected=set(args.use_case_id or pipeline.contexts)
            if not selected<=set(pipeline.contexts):raise ValueError('unknown selected use case')
            updates=[]
            for case in sorted(selected):
                key=pipeline.key(case,args.stage)
                if key not in pipeline.scheduler.tasks:raise ValueError('unknown selected stage')
                record=pipeline.scheduler.state['tasks'][key]
                failure=record.get('failure') or {}
                if record['status'] not in ('rejected','budget_exhausted') or not failure.get('errors'):continue
                if record['input_hash']!=pipeline.scheduler.input_hash(pipeline.scheduler.tasks[key]):
                    raise ValueError('task dependencies changed; cannot refresh old failure')
                validator=pipeline.contexts[case]['validators'].get(args.stage)
                if not validator:raise ValueError('only semantic validation failures can be refreshed')
                errors={};proofs=[];chosen=None
                folders=[pipeline.contexts[case]['root']/'batches'/args.stage,
                    *sorted((pipeline.contexts[case]['root']/'batches').glob(args.stage+'-repair-*'))]
                for folder in reversed(folders):
                    if not (folder/'manifest.json').exists():continue
                    batches=read_json(folder/'manifest.json')['batches']
                    if not set(failure['errors']) & {b['batch_id'] for b in batches}:continue
                    chosen=folder
                    for batch in batches:
                        bid=batch['batch_id'];packet=read_json(folder/'packets'/(bid+'.json'))
                        if fingerprint({k:v for k,v in packet.items() if k not in ('batch_id','input_hash')})!=batch['input_hash']:
                            raise ValueError('saved diagnostic packet changed')
                        result=folder/'results'/(bid+'.json')
                        if result.exists():raw=read_json(result);evidence=result
                        else:
                            attempts=sorted((folder/'attempts').glob(bid+'-*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
                            evidence=next((p for p in attempts if isinstance(read_json(p).get('result'),dict)),None)
                            if not evidence:raise ValueError('saved failed execution missing; no model call will be made')
                            raw=read_json(evidence)['result']
                        if raw.get('batch_id')!=bid or raw.get('input_hash')!=batch['input_hash']:
                            raise ValueError('saved diagnostic result identity changed')
                        validate_result_execution(raw,result_path=evidence)
                        proofs.append({'path':str(evidence.resolve()),'hash':fingerprint(read_json(evidence))})
                        try:validator(packet,copy.deepcopy(raw))
                        except (ValueError,KeyError,TypeError) as exc:errors[bid]=type(exc).__name__+': '+str(exc)
                    break
                if chosen is None or not errors:continue
                refreshed={**failure,'errors':errors,'pending':sorted(errors),'output':{'folder':str(chosen.resolve())}}
                old_signature=failure_signature(failure);new_signature=failure_signature(refreshed)
                reopened=(record['status']=='budget_exhausted' and record.get('reason')=='same failure; no semantic progress'
                    and old_signature!=new_signature and record['rounds']<pipeline.scheduler.max_rounds)
                record.update(failure=refreshed,failure_hash=new_signature)
                if reopened:
                    record.update(status='rejected',reason='validator diagnostics refined; existing repair budget preserved')
                event={'task':key,'event':'offline_diagnostic_refresh','proofs':proofs,
                    'validator_hash':fingerprint(inspect.getsource(validator)),
                    'old_failure_hash':old_signature,'failure_hash':new_signature,'round':record['rounds'],
                    'remaining_rounds':max(0,pipeline.scheduler.max_rounds-record['rounds']),'reopened':reopened,
                    'errors':errors}
                pipeline.scheduler.state['events'].append(event);updates.append(event)
            pipeline.scheduler.save();pipeline.progress(pipeline.scheduler)
            result={'updated_tasks':updates,'model_calls':0,'repair_rounds_preserved':True}
            write_json(root/'diagnostic_refresh.json',result)
            return result,0
        finally:
            if pipeline.profiler:pipeline.profiler.finish('offline_diagnostic_refresh')
