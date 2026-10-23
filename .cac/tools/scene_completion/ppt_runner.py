"""Independent tasks and a fixed, resumable DAG for ppt-task-v1.

No legacy packets, history vectors, recommendations or external paid calls in
packet/mock mode. Semantic results are evidence-checked before cache promotion.
"""
from pathlib import Path
from copy import deepcopy
import json
from .ppt_contracts import PROTOCOL,TASKS,packet,registry,schema,validate
from .ppt_sources import read_documents,normal_projection,documents_in
from .ppt_method import validate_result,resource_metadata,data_exceptions,deduplicate,compare_report,pending_rules,bind_resource_services,capability_union,complete_data_matches
from .ppt_exports import export_task
from .case_dag import Scheduler,Task,TaskRejected,TaskBlocked,CallGate,run_lock
from .semantic_backend import read_json,write_json
from .sources import fingerprint


def payload(value):
    if value.get('protocol')!=PROTOCOL: raise ValueError('legacy or unversioned task result cannot enter ppt-task-v1')
    return value['payload']


def code_version(task):
    folder=Path(__file__).parent
    names=['ppt_contracts.py','ppt_sources.py','ppt_method.py','ppt_runner.py','ppt_exports.py',
           'semantic_backend.py','model_configuration.py','case_dag.py','interaction_protocol.py','interaction_assignment.py','luna_subprocess.py']
    skill=folder.parents[1]/'skills'/TASKS.get(task,('scene-existing-extract',))[0]/'SKILL.md'
    return fingerprint({**{n:(folder/n).read_text(encoding='utf8') for n in names},'skill':skill.read_text(encoding='utf8') if skill.exists() else ''})


class Execution:
    def __init__(self,root,*,mode='packets',client=None,responses_dir=None,mocks=None,config=None,case_ids=None,auto_repair='bounded',max_rounds=2):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.mode,self.client,self.responses_dir,self.mocks=mode,client,Path(responses_dir) if responses_dir else None,mocks
        self.config=config or getattr(client,'config',{}) or {};self.case_ids=case_ids or []
        if self.config.get('structured_output','json_object') not in {'json_object','json_schema'}:
            raise ValueError('structured_output must be json_object or configured json_schema')
        self.identity={'mode':'mock' if mocks is not None else mode,'model':client.model('agent') if client else None,
                       'config_hash':fingerprint(self.config),'endpoint_hash':fingerprint(getattr(client,'base_url',None))}
        manifest=self.root/'run_manifest.json'
        previous=read_json(manifest) if manifest.exists() else None
        if previous and previous.get('protocol')!=PROTOCOL:raise ValueError('different protocol: use a new run directory')
        if (self.root/'case_tasks.json').exists() and not previous:raise ValueError('unbound/legacy scheduler cache requires a separate run directory')
        if previous and previous.get('execution_identity',{}).get('mode')=='mock' and mocks is None:raise ValueError('mock results cannot be promoted into a real run')
        self.manifest={'protocol':PROTOCOL,'complete':False,'execution_identity':self.identity,
                       'registry_hash':registry()['hash'],'recommendation':{'enabled':False,'status':'未启用'},'formal':False}
        write_json(manifest,self.manifest)
        self.scheduler=Scheduler(self.root,concurrency=self.config.get('max_concurrency',1),auto_repair=auto_repair,max_rounds=max_rounds)
        self.gate=CallGate(self.config.get('max_concurrency',1),adaptive=self.config.get('adaptive_concurrency',True),on_change=lambda s:write_json(self.root/'concurrency_status.json',s),pause_file=self.root/'pause_requested.json')
        prior_limit=self.root/'concurrency_status.json'
        if prior_limit.exists():
            import time
            prior=read_json(prior_limit)
            if prior.get('configured_max')==self.gate.limit:
                self.gate.effective_limit=min(self.gate.limit,prior['effective_max'])
                self.gate.retry_not_before=time.monotonic()+max(0.,min(300.,prior.get('not_before_unix',0)-time.time()))
        # Reuse the existing request-level gate, cooldown and token-budget code.
        if client and hasattr(client,'post'):
            original=client.post
            client.post=lambda *a,**k:self.gate.call(original,*a,**k)

    def semantic(self,task,inputs,record):
        p=packet(task,inputs,self.case_ids)
        p['skill_text']=self.skill_text(task)
        if record.get('rounds'):
            p['repair']={'failure':record.get('failure'),'round':record['rounds'],'rule':'仅修复本任务；不读取其他通道。'}
        p['batch_id']=fingerprint({k:v for k,v in p.items() if k!='batch_id'})
        batch=p['batch_id'];write_json(self.root/'packets'/(batch+'.json'),p)
        raw=None
        if self.mocks is not None:
            value=self.mocks.get(record.get('stage'),self.mocks.get(task))
            if value is None:raise TaskBlocked('pending',{'mock_missing':task})
            raw=value(p) if callable(value) else deepcopy(value)
        elif self.responses_dir and (self.responses_dir/(batch+'.json')).exists():
            envelope=read_json(self.responses_dir/(batch+'.json'))
            if envelope.get('protocol')!=PROTOCOL or envelope.get('batch_id')!=batch or envelope.get('task')!=task:
                raise TaskRejected({'error':'external result is not bound to this protocol/task/input'})
            raw=envelope['payload']
        elif self.mode=='external':
            if not self.client:raise ValueError('external mode needs a configured semantic client')
            raw=self.client.agent(p) if hasattr(self.client,'post') else self.gate.call(self.client.agent,p)
        else:raise TaskBlocked('pending',{'packet':str(self.root/'packets'/(batch+'.json')),'batch_id':batch})
        proof={k:raw[k] for k in ('execution_model_evidence','native_execution') if k in raw}
        value={k:v for k,v in raw.items() if k not in proof}
        attempt=self.root/'attempts'/batch/(str(record.get('rounds',0))+'.json')
        write_json(attempt,{'task':task,'protocol':PROTOCOL,'payload':value,'execution':proof})
        try:
            validate_result(task,value,inputs)
            if task in {'rr-ssd','sr-ssd'} and any(inputs.values()) and not value['interactions']:
                raise ValueError('nonempty positive document requires real SSD interactions, not an empty successful result')
            if task=='components' and any(inputs.values()) and not value['components']:
                raise ValueError('nonempty RR/SR requires evidenced components')
            if self.case_ids and task in {'rr-ssd','sr-ssd','exception-generate','existing-extract','test-ground-truth'}:
                records=value.get('interactions',value.get('scenarios',[]))
                if any(r['case_id'] not in self.case_ids for r in records):raise ValueError('result outside selected case scope')
                if task in {'rr-ssd','sr-ssd'} and set(self.case_ids)!={r['case_id'] for r in records}:
                    raise ValueError('selected SSD cases incomplete')
        except ValueError as exc:raise TaskRejected({'error':str(exc),'rejected_output':str(attempt.relative_to(self.root))}) from exc
        return value,proof

    def skill_text(self,task):
        name=TASKS.get(task,('scene-existing-extract',))[0]
        file=Path(__file__).resolve().parents[2]/'skills'/name/'SKILL.md'
        return file.read_text(encoding='utf8') if file.exists() else ''

    def add(self,key,task,deps=(),static=None,build=None,transform=None,semantic_task=None):
        static=static or {}
        def inputs_for(dependencies):
            values={k:payload(v) for k,v in dependencies.items()}
            return build(values) if build else deepcopy(static)
        def execute(dependencies,record):
            inputs=inputs_for(dependencies)
            if transform:
                value=transform(inputs);proof={}
            elif task=='gap-compare' and (not inputs['left'] or not inputs['right']):value,proof={'decisions':[]},{}
            else:value,proof=self.semantic(semantic_task or task,inputs,record)
            if task=='concern-match':
                value['matches']=complete_data_matches(inputs,value['matches'])
            if task in {'exception-generate','existing-extract','test-ground-truth'}:
                if task=='exception-generate':
                    value['scenarios']=deduplicate(value['scenarios']+data_exceptions(inputs))
                    value['pending']=list({fingerprint(x):x for x in value['pending']+pending_rules(inputs)}.values())
                else:value['scenarios']=deduplicate(value['scenarios'])
            if task in TASKS or task in {'test-ground-truth','test-operation-project'}:
                validate_result(task,value,inputs)
            meta={'input_hash':fingerprint(inputs),'source_channel':'task-scoped','execution':proof}
            if task=='components':meta.update(resource_metadata(value))
            return {'protocol':PROTOCOL,'task':task,'payload':value,'metadata':meta}
        def verify(value):
            if value.get('protocol')!=PROTOCOL or value.get('task')!=task:raise ValueError('wrong task/protocol result')
            # Re-run schema checks on cache reads, not just initial responses.
            if task in TASKS or task in {'test-ground-truth','test-operation-project'}:
                dependencies={dep:read_json(self.root/self.scheduler.state['tasks'][dep]['output_file']) for dep in deps}
                validate_result(task,value['payload'],inputs_for(dependencies))
        version={'protocol':PROTOCOL,'code':code_version(task),'schema':fingerprint(schema(task)) if task in TASKS or task in {'test-ground-truth','test-operation-project'} else None,
                 'static':fingerprint(static),'identity':self.identity,'cases':self.case_ids,'registry':registry()['hash']}
        self.scheduler.add(Task(key,'selected-cases',task,tuple(deps),version=version,execute=execute,repair=execute,verify=verify))

    def finish(self):
        result=self.scheduler.run()
        # Published views must never present stale metrics/artifacts as current.
        # Original successful/rejected attempts remain in task_outputs/attempts.
        artifact_root=self.root/'artifacts'
        known=set(TASKS)|{'test-operation-project','test-ground-truth','G_E','GT_G','GT_E','report'}
        if artifact_root.exists():
            for file in artifact_root.iterdir():
                if file.is_file() and any(file.name.startswith(k+'.') or file.name.startswith(k+'-') for k in known):file.unlink()
        if 'report' not in self.scheduler.state['tasks'] or self.scheduler.state['tasks']['report']['status']!='passed':
            (self.root/'missing_report.json').unlink(missing_ok=True)
        for key,record in self.scheduler.state['tasks'].items():
            if record['status']=='passed':
                value=read_json(self.root/record['output_file'])
                export_task(self.root/'artifacts',key,value['payload'])
                write_json(self.root/'artifacts'/(key+'.metadata.json'),{'protocol':PROTOCOL,**value.get('metadata',{})})
                if key=='report':write_json(self.root/'missing_report.json',value['payload'])
        # Export the logical SR view alongside physical composition and mapping.
        records=self.scheduler.state['tasks']
        if all(k in records and records[k]['status']=='passed' for k in ('components','sr-ssd')):
            views={k:payload(read_json(self.root/records[k]['output_file'])) for k in ('components','sr-ssd')}
            export_task(self.root/'artifacts','sr-ssd',bind_resource_services(views)['sr-ssd'])
        self.manifest.update(complete=result['complete'],tasks={k:r['status'] for k,r in self.scheduler.state['tasks'].items()})
        write_json(self.root/'run_manifest.json',self.manifest)
        return self.manifest


def build_pipeline(ex,rr,sr,tests):
    normal_rr=normal_projection(rr);normal_sr=normal_projection(sr)
    for task,inputs in [('components',{'RR':normal_rr,'SR':normal_sr}),('rr-ssd',{'RR':normal_rr}),('sr-ssd',{'SR':normal_sr}),
                        ('api-map',{'SR':normal_sr}),('api-parameters',{'SR':normal_sr})]:ex.add(task,task,static=inputs)
    ex.add('test-operation-project','test-operation-project',static={'test-operation-source':tests},transform=(lambda d:{'objects':[]}) if not tests else None)
    ex.add('object-operations','object-operations',('components','rr-ssd','test-operation-project'),build=lambda d:{
        'components':d['components'],'rr-ssd':d['rr-ssd'],'test-operations':d['test-operation-project']},transform=capability_union)
    normal_deps=('components','rr-ssd','sr-ssd','api-map','api-parameters')
    ex.add('concern-match','concern-match',normal_deps,build=lambda d:{**bind_resource_services(d),'registry':registry()})
    ex.add('exception-generate','exception-generate',normal_deps+('concern-match',),build=lambda d:{**bind_resource_services(d),'registry':registry()})
    ex.add('existing-extract','existing-extract',static={'existing-documents':rr+sr,'registry':registry()})
    # GT uses only test descriptions/framework and explicit normal API constraints.
    ex.add('test-ground-truth','test-ground-truth',('api-parameters',),static={'tests':tests},
           build=lambda d:{'test-documents':tests,'normal-constraints':d['api-parameters'],'registry':registry()},transform=(lambda d:{'scenarios':[]}) if not tests else None)
    pairs={'G_E':('exception-generate','existing-extract'),'GT_G':('test-ground-truth','exception-generate'),'GT_E':('test-ground-truth','existing-extract')}
    for key,(a,b) in pairs.items():
        ex.add(key,'gap-compare',(a,b),build=lambda d,a=a,b=b,key=key:{'left':d[a]['scenarios'],'right':d[b]['scenarios'],'purpose':key})
    ex.add('gap-recommend','gap-recommend',transform=lambda d:{'enabled':False,'status':'未启用'})
    deps=('exception-generate','existing-extract','test-ground-truth','G_E','GT_G','GT_E')
    ex.add('report','report',deps,build=lambda d:d,transform=lambda d:compare_report(
      d['exception-generate']['scenarios'],d['existing-extract']['scenarios'],d['test-ground-truth']['scenarios'],
      d['G_E']['decisions'],d['GT_G']['decisions'],d['GT_E']['decisions']))


def register(sub):
    parser=sub.add_parser('scene-task',help='independent ppt-task-v1 task; packets by default, no paid call')
    parser.add_argument('--task',choices=TASKS,required=True)
    parser.add_argument('--input-json',required=True,help='task input object; named inputs must follow the versioned schema')
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--agent-mode',choices=('packets','external'),default='packets')
    parser.add_argument('--responses-dir')
    parser.add_argument('--config');parser.add_argument('--env-file',default='.env')
    parser.add_argument('--agent-runtime',choices=('ecnu','openai-compatible','luna-subprocess'))
    parser.add_argument('--max-repair-rounds',type=int,choices=(0,1,2),default=2)
    parser.add_argument('--use-case-id',action='append')
    score=sub.add_parser('score-ppt-extraction',help='offline GT-hit Acc for one extraction task')
    score.add_argument('--task',choices=('components','rr-ssd','sr-ssd','object-operations','api-map','api-parameters'),required=True)
    score.add_argument('--extracted',required=True);score.add_argument('--truth',required=True)
    score.add_argument('--decisions');score.add_argument('--output',required=True)


def run(args):
    root=Path(args.output_dir).resolve()
    # Validate inputs before publishing a manifest or touching an existing run.
    independent=args.command=='scene-task'
    if independent:
        inputs=read_json(args.input_json);packet(args.task,inputs,getattr(args,'use_case_id',None))
    else:
        if getattr(args,'spec_document',None):raise ValueError('explicit RR/SR Markdown sources required')
        for legacy_arg in ('model','history_run','reuse_run','ssd_manifest','ar_spec_document'):
            if getattr(args,legacy_arg,None):raise ValueError(legacy_arg+' belongs to an explicit legacy protocol; ppt-task-v1 reads scoped RR/SR directly')
        if getattr(args,'execution_mode',None)=='stage-barrier':raise ValueError('ppt-task-v1 uses the persistent DAG')
        rr_paths=getattr(args,'rr_spec_document',None) or getattr(args,'requirement_document',None) or []
        sr_paths=getattr(args,'sr_spec_document',None) or getattr(args,'design_document',None) or []
        if not rr_paths or not sr_paths:raise ValueError('RR and SR Markdown sources required')
        test_paths=getattr(args,'test_spec_document',None) or []
        rr_set,sr_set,test_set=({str(Path(p).resolve()) for p in paths} for paths in (rr_paths,sr_paths,test_paths))
        if rr_set&sr_set or test_set&(rr_set|sr_set):raise ValueError('RR, SR and tests must be distinct inputs')
        rr=read_documents(rr_paths,'existing');sr=read_documents(sr_paths,'existing');tests=read_documents(test_paths,'test')
    root.mkdir(parents=True,exist_ok=True)
    with run_lock(root):
        from .role_cli import _client
        client=_client(args,root) if args.agent_mode=='external' and (not independent or args.task not in {'gap-recommend','object-operations'}) else None
        config=read_json(args.config) if args.config else {}
        ex=Execution(root,mode=args.agent_mode,client=client,config=getattr(client,'config',config),responses_dir=getattr(args,'responses_dir',None),
                     case_ids=getattr(args,'use_case_id',None),auto_repair=getattr(args,'auto_repair',None) or 'bounded',max_rounds=getattr(args,'max_repair_rounds',None) if getattr(args,'max_repair_rounds',None) is not None else 2)
        if independent:
            if args.task=='gap-recommend':ex.add(args.task,args.task,transform=lambda d:{'enabled':False,'status':'未启用'})
            elif args.task=='object-operations':ex.add(args.task,args.task,static=inputs,transform=capability_union)
            else:ex.add(args.task,args.task,static=inputs)
        else:build_pipeline(ex,rr,sr,tests)
        result=ex.finish()
        return result,0 if result['complete'] else 2
