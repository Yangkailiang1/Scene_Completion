"""Independent tasks and a fixed, resumable DAG for scene-workflow-v3.

No legacy packets, history vectors, recommendations or external paid calls in
packet/mock mode. Semantic results are evidence-checked before cache promotion.
"""
from pathlib import Path
from copy import deepcopy
import json
from .contracts import PROTOCOL,TASKS,SCHEMAS,packet,registry,schema,validate
from .source_documents import read_documents,normal_projection,documents_in
from .validation import validate_result
from .interaction_enrichment import resource_metadata,bind_resource_services,capability_union,enrich,with_concerns,actual_context,basic_views
from .exception_generation import data_exceptions,deduplicate,pending_rules,query_matches,query_exceptions,service_exceptions,storage_exceptions,attach_provenance
from .concern_matching import complete_data_matches
from .concern_hierarchy import resolve_matches
from .exception_comparison import compare_report,missing_report
from .artifact_exports import export_task
from .reviews import REVIEW_TASKS
from .scheduler import Scheduler,Task,TaskRejected,TaskBlocked,CallGate,run_lock
from .storage import read_json,write_json
from .storage import fingerprint

def canonical_enrich(d):
    from .inverse_alignment import canonical_fused
    raw={'interactions':d['rr-ssd']['interactions']+d['sr-ssd']['interactions'],'rr_sr_links':d['interaction-align']['links']}
    canonical=canonical_fused(raw);ids={i['id'] for i in canonical['interactions']};aliases={a['source_id']:a['interaction_id'] for a in canonical['aliases']}
    value=enrich(d,d['interaction-align'])
    value['interactions']=[i for i in value['interactions'] if i['id'] in ids]
    for i in value['interactions']:
        if i.get('parent_id') in aliases:i['parent_id']=aliases[i['parent_id']]
    return value



def payload(value):
    if value.get('protocol')!=PROTOCOL: raise ValueError('legacy or unversioned task result cannot enter scene-workflow-v3')
    return value['payload']


def code_version(task):
    folder=Path(__file__).parent
    # Semantic contracts and validators are part of every result identity.
    names=['contracts.py','validation.py','interaction_enrichment.py','exception_generation.py',
           'exception_comparison.py','concern_matching.py','assignment.py','workflow.py','source_documents.py','concern_registry.py','concern_hierarchy.py','model_client.py','native_client.py','use_cases.py','reviews.py','deepagents_client.py','execution_events.py','execution_graph.py','streaming.py','inverse_alignment.py','node_conversations.py','api_documents.py']
    skill=skill_path(task)
    implementation=fingerprint({**{n:(folder/n).read_text(encoding='utf8') for n in names},'rules':skill.read_text(encoding='utf8')})
    # Exact reviewed, output-compatible runtime changes may retain paid results.
    # Any subsequent implementation/Skill edit changes this hash and misses the
    # alias; components deliberately has no alias for the new submission mode.
    compatibility=folder/'cache_code_aliases.json'
    aliases=read_json(compatibility).get('aliases',{}) if compatibility.exists() else {}
    return aliases.get(implementation,implementation)

def skill_path(task):
    if task in TASKS:return Path(__file__).resolve().parents[2]/'skills'/TASKS[task][0]/'SKILL.md'
    internal={'test-operation-project','test-ground-truth','interaction-align','semantic-compare','api-index'}
    return Path(__file__).parent/'prompts'/((task if task in internal else 'tool-task')+'.md')


class Execution:
    def __init__(self,root,*,mode='packets',client=None,responses_dir=None,mocks=None,config=None,case_ids=None,auto_repair='bounded',max_rounds=2):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.mode,self.client,self.responses_dir,self.mocks=mode,client,Path(responses_dir) if responses_dir else None,mocks
        self.config=config or getattr(client,'config',{}) or {};self.case_ids=case_ids or []
        from .reviews import Reviews
        from .node_conversations import Conversations
        self.conversations=Conversations(self.root)
        self.reviews=Reviews(self.root,self.config.get('review_mode','auto'))
        self.expand_pipeline=None
        self.expand_api=None
        if self.config.get('structured_output','json_object') not in {'json_object','json_schema'}:
            raise ValueError('structured_output must be json_object or configured json_schema')
        self.identity={'mode':'mock' if mocks is not None else mode,'model':client.model('agent') if client else None,
                       'config_hash':fingerprint(self.config),'endpoint_hash':fingerprint(getattr(client,'base_url',None))}
        self.reviews.execution_identity=fingerprint({**{k:v for k,v in self.identity.items() if k!='config_hash'},'config_hash':fingerprint({k:v for k,v in self.config.items() if k!='review_mode'})})
        manifest=self.root/'run_manifest.json'
        previous=read_json(manifest) if manifest.exists() else None
        if previous and previous.get('protocol')!=PROTOCOL:raise ValueError('different protocol: use a new run directory')
        if any((self.root/n).exists() for n in ('case_tasks.json','workflow_tasks.json')) and not previous:raise ValueError('unbound/legacy scheduler cache requires a separate run directory')
        if previous and previous.get('execution_identity',{}).get('mode')=='mock' and mocks is None:raise ValueError('mock results cannot be promoted into a real run')
        self.manifest={'protocol':PROTOCOL,'complete':False,'execution_identity':self.identity,
                       'registry_hash':registry()['hash'],'registry_version':registry()['version'],'recommendation':{'enabled':False,'status':'未启用'},'formal':False}
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
        p=packet(task,inputs,[record['case']] if record.get('case') not in (None,'shared') else [])
        from .execution_events import context
        _,event_context=context()
        p['node_key']=event_context.get('task_key',task)
        p['skill_text']=self.skill_text(task)
        if task=='exception-generate':
            # These are derived only from this task's positive inputs. They are
            # not E/GT, previous G, or semantic answers from another channel.
            p['tool_rule_coverage']={'data':data_exceptions(inputs),'query':query_exceptions(inputs),'availability':service_exceptions(inputs),'storage':storage_exceptions(inputs),'pending':pending_rules(inputs)}
            p['tool_rule_instruction']='工具会合并上述确定性候选。模型只需返回其他有具体正常规则支持的双方/操作异常，可返回空scenarios；不要改写字段规则或编造后续行为。'
        if task=='concern-match':
            p['tool_rule_instruction']='程序会依照既定注册表自动继承基础、功能、技术及关系关注点，并由明确字段属性补齐数据关注点。你只补充需要语义理解的具体适用依据（如认证/授权条件、技术身份、明确的业务规则），不要穷举所有关注点或重复字段规则；没有额外依据可返回空matches，未知项写pending。'
        if record.get('rounds'):
            p['repair']={'failure':record.get('failure'),'round':record['rounds'],'rule':'仅修复本任务；不读取其他通道。'}
            candidate=(record.get('failure') or {}).get('rejected_output')
            if candidate:
                path=(self.root/candidate).resolve()
                if path.is_relative_to(self.root.resolve()) and path.is_file():
                    previous=read_json(path)
                    if previous.get('task')==task and previous.get('node_key')==p['node_key'] and previous.get('input_hash')==fingerprint(inputs):
                        p['repair']['candidate']=previous['payload']
                        p['repair']['rule']='候选尚未通过校验。只定向修复列出的错误，保留有据且合法的部分；所有字段仍须重新满足Schema、当前指导与原文引用。'
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
            try:
                if task in {'gap-compare','semantic-compare'}:
                    from .comparison_batches import compare_in_batches
                    raw=compare_in_batches(p,self.client,self.root,self.conversations.revision(p['node_key']),
                      call=lambda child:self.client.agent(child) if hasattr(self.client,'post') else self.gate.call(self.client.agent,child))
                else:raw=self.client.agent(p) if hasattr(self.client,'post') else self.gate.call(self.client.agent,p)
            except ValueError as exc:
                diagnostic=getattr(exc,'response_diagnostic',None)
                if diagnostic:
                    attempt=self.root/'attempts'/batch/(str(record.get('rounds',0))+'.json')
                    write_json(attempt,{'task':task,'protocol':PROTOCOL,'rejected_response':diagnostic})
                    raise TaskRejected({'error':str(exc),'rejected_output':str(attempt.relative_to(self.root))}) from exc
                raise
        else:raise TaskBlocked('pending',{'packet':str(self.root/'packets'/(batch+'.json')),'batch_id':batch})
        if not isinstance(raw,dict):raise TaskRejected({'error':'model result must be a JSON object'})
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
            scope=p['case_ids']
            if scope and task in {'rr-ssd','sr-ssd','exception-generate','existing-extract','test-ground-truth'}:
                records=value.get('interactions',value.get('scenarios',[]))
                if any(r['case_id'] not in scope for r in records):raise ValueError('result outside selected case scope')
                if task in {'rr-ssd','sr-ssd'} and set(scope)!={r['case_id'] for r in records}:
                    raise ValueError('selected SSD cases incomplete')
        except ValueError as exc:raise TaskRejected({'error':str(exc),'rejected_output':str(attempt.relative_to(self.root))}) from exc
        return value,proof

    def skill_text(self,task):
        return skill_path(task).read_text(encoding='utf8')

    def add(self,key,task,deps=(),static=None,build=None,transform=None,semantic_task=None,case=None):
        static=static or {}
        review_identity=fingerprint([self.reviews.execution_identity,code_version(task),schema(task) if task in SCHEMAS else None,self.conversations.revision(key)])
        def inputs_for(dependencies):
            values={k:payload(v) for k,v in dependencies.items()}
            return build(values) if build else deepcopy(static)
        def execute(dependencies,record):
            inputs=inputs_for(dependencies)
            reviewed=self.reviews.cached(key,task,inputs,review_identity) if task in REVIEW_TASKS else None
            if reviewed is not None:
                value=reviewed;proof={'reviewed':True}
            elif transform:
                value=transform(inputs);proof={}
            elif task in {'gap-compare','semantic-compare'} and (not inputs['left'] or not inputs['right']):value,proof={'decisions':[],**({'missing':deduplicate(inputs['left'])} if task=='gap-compare' else {})},{}
            else:value,proof=self.semantic(semantic_task or task,inputs,record)
            if task=='concern-match':
                resolved=resolve_matches(inputs,value['matches'])
                value['matches']=resolved['matches']
                value['pending']=list({fingerprint(v):v for v in value['pending']+resolved['pending']}.values())
            if task in {'exception-generate','existing-extract','test-ground-truth'}:
                if task=='exception-generate':
                    value['scenarios']=deduplicate(attach_provenance(inputs,value['scenarios']+data_exceptions(inputs)+query_exceptions(inputs)+service_exceptions(inputs)+storage_exceptions(inputs)))
                    value['pending']=list({fingerprint(x):x for x in value['pending']+pending_rules(inputs)}.values())
                else:value['scenarios']=deduplicate(value['scenarios'])
            if task=='existing-extract' and 'fused-ssd' in inputs:
                from .inverse_alignment import expand_inverse
                value=expand_inverse(value,inputs)
            if task=='test-ground-truth' and 'fused-ssd' in inputs:
                from .inverse_alignment import expand_truth
                value=expand_truth(value,inputs)
            from .execution_events import phase
            phase('validating')
            if task in SCHEMAS:
                validate_result(task,value,inputs)
            if reviewed is None:self.reviews.propose(key,task,inputs,value,review_identity)
            meta={'input_hash':fingerprint(inputs),'source_channel':'task-scoped','execution':proof}
            if task=='components':meta.update(resource_metadata(value))
            return {'protocol':PROTOCOL,'task':task,'payload':value,'metadata':meta}
        def verify(value):
            if value.get('protocol')!=PROTOCOL or value.get('task')!=task:raise ValueError('wrong task/protocol result')
            # Re-run schema checks on cache reads, not just initial responses.
            if task in SCHEMAS:
                dependencies={dep:read_json(self.root/self.scheduler.state['tasks'][dep]['output_file']) for dep in deps}
                validate_result(task,value['payload'],inputs_for(dependencies))
        version={'protocol':PROTOCOL,'code':code_version(task),'schema':fingerprint(schema(task)) if task in SCHEMAS else None,
                 'static':fingerprint(static),'identity':self.identity,'guidance_revision':self.conversations.revision(key),'review_revision':self.reviews.revision(key),'cases':self.case_ids,'registry':registry()['hash'] if task in {'concern-match','exception-generate','existing-extract','test-ground-truth','gap-compare','semantic-compare','enriched-view','missing-report','exception-evaluation'} else None}
        self.scheduler.add(Task(key,case or 'shared',task,tuple(deps),version=version,execute=execute,repair=execute,verify=verify))

    def finish(self):
        def update():
            records=self.scheduler.state['tasks']
            api=records.get('api-index',{})
            if self.expand_api and api.get('status')=='passed':
                self.scheduler.tasks.pop('api-parameters',None)
                expand=self.expand_api;self.expand_api=None;expand()
            elif self.expand_api and api.get('status') in {'failed','rejected','pending','rate_limited','awaiting_configuration','budget_exhausted','awaiting_answer','awaiting_review'}:
                # A blocked index still declares the final dependency target;
                # the scheduler will never treat it as a complete API table.
                active=api.get('status') in {'failed','rejected'} and api.get('rounds',0)<self.scheduler.rounds
                if not active:
                    if 'api-parameters' not in self.scheduler.tasks:
                        self.add('api-parameters','api-parameters',('api-index',),transform=lambda d:{'apis':[]})
            if self.expand_pipeline and records.get('use-case-align',{}).get('status')=='passed':
                expand=self.expand_pipeline;self.expand_pipeline=None;expand()
        self.scheduler.on_update=update
        result=self.scheduler.run()
        self.scheduler.on_update=None
        if self.expand_api:
            self.scheduler.tasks.pop('api-parameters',None)
            expand=self.expand_api;self.expand_api=None;expand();result=self.scheduler.run()
        if self.expand_pipeline and self.scheduler.state['tasks'].get('use-case-align',{}).get('status')=='passed':
            expand=self.expand_pipeline;self.expand_pipeline=None;expand();result=self.scheduler.run()
        artifact_root=self.root/'artifacts'
        import shutil
        # Keep independently completed task files; failed siblings cannot erase them.
        (self.root/'missing_report.json').unlink(missing_ok=True)
        (self.root/'missing_report.md').unlink(missing_ok=True)
        reports={};evaluations={};cases={}
        records=self.scheduler.state['tasks']
        for key,record in records.items():
            if key not in self.scheduler.tasks:continue
            cid=record.get('case','shared')
            cases.setdefault(cid,{})[record['stage']]=record['status']
            if record['status']!='passed':
                if record['status']!='awaiting_review':
                    from .execution_graph import artifact_folder
                    folder=artifact_folder(self.root,key,cid);stem=(key if cid=='shared' else key[len(cid)+1:]).replace(':','--')
                    for old in folder.glob(stem+'.*'):
                        archive=self.root/'previous_artifacts'/fingerprint([key,record.get('identity')])[:16]/old.name
                        archive.parent.mkdir(parents=True,exist_ok=True);old.replace(archive)
                continue
            value=read_json(self.root/record['output_file']);stage=value['task']
            destination=artifact_root/(safe_case(cid) if cid!='shared' else 'shared')
            stem=(key if cid=='shared' else key[len(cid)+1:]).replace(':','--')
            export_task(destination,stage,value['payload'],artifact_name=stem)
            write_json(destination/(stem+'.metadata.json'),value.get('metadata',{}))
            if stage=='missing-report':reports[cid]=value['payload']
            if stage=='exception-evaluation':evaluations[cid]=value['payload']
        if reports:
            from .artifact_exports import export_missing_report
            combined={'protocol':PROTOCOL,'cases':reports,'evaluation':evaluations,
              'recommendation':{'enabled':False,'status':'未启用'},'evaluation_status':{
                  c:'已评测' if c in evaluations else '未评测或任务未完成' for c in reports}}
            export_missing_report(self.root,combined)
        analysis_stages={'fused-ssd','rr-ssd','sr-ssd','object-operations','interaction-align','interaction-enrich','concern-match','enriched-view','exception-generate','existing-extract','gap-compare','missing-report'}
        analysis={c:all(stages.get(s)=='passed' for s in analysis_stages) for c,stages in cases.items() if c!='shared'}
        self.manifest.update(complete=result['complete'] and not any(g['status']=='pending' for g in self.manifest.get('case_correspondence',[])),analysis_complete=bool(analysis) and all(analysis.values()),
          analysis_by_case=analysis,evaluation_by_case={c:s.get('exception-evaluation','未评测') for c,s in cases.items() if c!='shared'},
          tasks={k:r['status'] for k,r in records.items() if k in self.scheduler.tasks})
        write_json(self.root/'run_manifest.json',self.manifest)
        return self.manifest


def safe_case(case):
    return fingerprint(case)[:12]


def build_pipeline(ex,rr,sr,tests,extraction_truth=None,adjudications=None):
    from .source_documents import discover_cases,case_projection,current_projection
    extraction_truth=extraction_truth or {};adjudications=adjudications or {}
    rr=current_projection(rr);sr=current_projection(sr)
    normal_rr=normal_projection(rr);normal_sr=normal_projection(sr)
    for task,inputs in [('components',{'RR':normal_rr,'SR':normal_sr}),('api-map',{'SR':normal_sr})]:
        ex.add(task,task,static=inputs)
    from .api_documents import index_interfaces
    ex.add('api-index','api-index',('api-map',),build=lambda d:{'SR':normal_sr,'api-map':d['api-map']},transform=index_interfaces)
    def expand_api():
        record=ex.scheduler.state['tasks'].get('api-index',{})
        if record.get('status')!='passed':
            ex.add('api-parameters','api-parameters',('api-index',),transform=lambda d:{'apis':[]})
            return
        index=payload(read_json(ex.root/record['output_file']))['apis'];keys=[]
        mapped=payload(read_json(ex.root/ex.scheduler.state['tasks']['api-map']['output_file']))
        interfaces={i['id']:i for s in mapped['services'] for i in s['interfaces']}
        for n,entry in enumerate(index):
            key='api-parameters-part-'+fingerprint(entry['id'])[:12]
            if key in keys:raise ValueError('duplicate API index identity')
            docs=[]
            for d in normal_sr:
                ranges=[r for r in entry['source_ranges'] if r['source_id']==d['source_id']]
                lines=[r for r in d['lines'] if any(span['start']<=r['number']<=span['end'] for span in ranges)]
                if lines:docs.append({**d,'lines':lines})
            if not docs:raise ValueError('API index has no valid source range')
            interface={**interfaces[entry['id']]}
            ex.add(key,'api-parameters',('api-index',),build=lambda d,docs=docs,interface=interface:{'SR':docs,'interface':interface})
            ex.scheduler.tasks[key].display_label='接口参数 · '+entry['name']
            keys.append(key)
        def merge(d):
            apis=[a for key in keys for a in d[key]['apis']]
            ids=[a['id'] for a in apis]
            if len(ids)!=len(set(ids)):raise ValueError('API subtask IDs conflict; review interface identity')
            return {'apis':apis}
        ex.add('api-parameters','api-parameters',tuple(keys) or ('api-index',),build=lambda d:d,transform=merge)
    ex.expand_api=expand_api
    ex.add('rr-use-cases','use-case-extract',static={'documents':normal_rr,'layer':'RR'})
    ex.add('sr-use-cases','use-case-extract',static={'documents':normal_sr,'layer':'SR'})
    ex.add('gap-recommend','gap-recommend',transform=lambda d:{'enabled':False,'status':'未启用'})
    ex.add('use-case-align','use-case-align',('rr-use-cases','sr-use-cases'),
      build=lambda d:{'rr-cases':d['rr-use-cases'],'sr-cases':d['sr-use-cases']})
    def expand():
        state=ex.scheduler.state['tasks']
        get=lambda key:payload(read_json(ex.root/state[key]['output_file']))
        catalogue={'RR':get('rr-use-cases')['cases'],'SR':get('sr-use-cases')['cases']}
        groups=get('use-case-align')['groups']
        if ex.case_ids:groups=[g for g in groups if g['id'] in ex.case_ids or set(ex.case_ids)&set(g['rr_ids']+g['sr_ids'])]
        ex.manifest['case_correspondence']=groups
        _build_cases(ex,rr,sr,tests,catalogue,groups,extraction_truth,adjudications)
    ex.expand_pipeline=expand


def _build_cases(ex,rr,sr,tests,catalogue,groups,extraction_truth,adjudications):
    from .use_cases import select_documents
    from .source_documents import case_projection
    from .api_documents import case_parameters
    cases=[g['id'] for g in groups if g['status']=='confirmed']
    extraction_jobs=[('shared',t,t) for t in ('components','api-map','api-parameters')]
    for cid in cases:
        key=lambda t:cid+':'+t
        # Translate scheduler keys to task contract names only within this case.
        def add(task,deps=(),static=None,build=None,transform=None,cid=cid):
            local=lambda t:t if t in {'components','api-map','api-parameters'} else cid+':'+t
            def construct(d):
                values={t:d[local(t)] for t in deps}
                return build(values) if build else deepcopy(static or {})
            ex.add(cid+':'+task,task,tuple(local(t) for t in deps),static=static,build=construct,transform=transform,case=cid)
        group=next(g for g in groups if g['id']==cid)
        scoped_rr=select_documents(rr,[c for c in catalogue['RR'] if c['id'] in group['rr_ids']],catalogue['RR'])
        scoped_sr=select_documents(sr,[c for c in catalogue['SR'] if c['id'] in group['sr_ids']],catalogue['SR'])
        test_ids=list(dict.fromkeys(x for g in groups for x in g['rr_ids']+g['sr_ids']))
        scoped_test=[]
        for tid in group['rr_ids']+group['sr_ids']:scoped_test+=case_projection(tests,tid,test_ids)
        scoped_test=list({fingerprint(d):d for d in scoped_test}.values())
        add('existing-branches',static={'existing-documents':scoped_rr+scoped_sr})
        add('fused-ssd',('components',),static={'RR':normal_projection(scoped_rr),'SR':normal_projection(scoped_sr),'case-group':group},
          build=lambda d,rr=normal_projection(scoped_rr),sr=normal_projection(scoped_sr),g=group:{'RR':rr,'SR':sr,'components':d['components'],'case-group':g})
        for layer in ('RR','SR'):
            add(layer.lower()+'-ssd',('fused-ssd',),build=lambda d:d,transform=lambda d,l=layer:{'interactions':[i for i in d['fused-ssd']['interactions'] if i['layer']==l]})
        add('test-operation-project',static={'test-operation-source':scoped_test},transform=(lambda d:{'objects':[]}) if not scoped_test else None)
        add('object-operations',('components','rr-ssd','test-operation-project'),build=lambda d:{'components':d['components'],'rr-ssd':d['rr-ssd'],'test-operations':d['test-operation-project']},transform=capability_union)
        add('interaction-align',('components','rr-ssd','sr-ssd','fused-ssd'),build=lambda d:d,transform=lambda d:{'aliases':[],'links':d['fused-ssd']['rr_sr_links']})
        normal=('components','rr-ssd','sr-ssd','api-map','api-parameters','object-operations')
        add('interaction-enrich',normal+('interaction-align',),build=lambda d:d,transform=lambda d:canonical_enrich(d))
        positive=normal_projection(scoped_rr)+normal_projection(scoped_sr)
        def concern_input(d,positive=positive):
            v={k:d[k] for k in normal};v=bind_resource_services(v)
            v.update(basic_views(d['interaction-enrich']))
            v['api-parameters']=case_parameters(v,d['interaction-enrich'])
            return {**v,'enriched-interactions':d['interaction-enrich'],'normal-documents':positive,'registry':registry()}
        add('concern-match',normal+('interaction-enrich',),static={'normal-documents':positive},build=concern_input)
        add('enriched-view',('interaction-enrich','concern-match'),build=lambda d:d,transform=lambda d:with_concerns(d['interaction-enrich'],d['concern-match']))
        def generation_input(d):
            v=bind_resource_services({k:d[k] for k in normal if k!='object-operations'})
            v.update(basic_views(d['enriched-view']))
            v['api-parameters']=case_parameters(v,d['enriched-view'])
            return {**v,'enriched-interactions':actual_context(d['enriched-view']),'concern-match':d['concern-match'],'registry':registry()}
        add('exception-generate',tuple(k for k in normal if k!='object-operations')+('enriched-view','concern-match'),build=generation_input)
        add('existing-bind',('existing-branches','fused-ssd'),
            build=lambda d,g=group:{'branches':d['existing-branches'],'fused-ssd':d['fused-ssd'],'case-group':g,'registry':registry()})
        add('existing-extract',('existing-branches','existing-bind','fused-ssd','api-parameters','api-map'),
            build=lambda d,docs=scoped_rr+scoped_sr:{'existing-documents':docs,'registry':registry(),'branches':d['existing-branches'],'bindings':d['existing-bind'],'fused-ssd':d['fused-ssd'],'normal-constraints':case_parameters(d,d['fused-ssd'])})
        add('gap-compare',('exception-generate','existing-extract'),build=lambda d:{'left':d['exception-generate']['scenarios'],'right':d['existing-extract']['scenarios'],'purpose':'G_E'})
        add('missing-report',('exception-generate','existing-extract','gap-compare','enriched-view','concern-match','existing-branches','existing-bind'),build=lambda d:d,
            transform=lambda d:{**missing_report(d['exception-generate']['scenarios'],d['existing-extract']['scenarios'],d['gap-compare']['decisions']),
              'interactions':d['enriched-view'],'concerns':d['concern-match']['matches'],
              'original_branches':[b for b in d['existing-branches']['branches'] if b['id'] in {v['branch_id'] for v in d['existing-bind']['bindings'] if v['status']!='not_this_case'}],
              'inverse_bindings':d['existing-bind']['bindings'],
              'pending':d['enriched-view']['pending']+d['concern-match']['pending']+d['exception-generate']['pending']+[{'interaction_id':b.get('interaction_id') or ('unbound:'+b['branch_id']),'reason':b['basis'],'source_refs':b['source_refs']} for b in d['existing-bind']['bindings'] if b['status']=='pending']})
        add('test-ground-truth',('api-parameters','api-map','fused-ssd'),static={'tests':scoped_test},build=lambda d,tt=scoped_test:{'test-documents':tt,'normal-constraints':case_parameters(d,d['fused-ssd']),'fused-ssd':d['fused-ssd'],'registry':registry()},transform=(lambda d:{'scenarios':[]}) if not scoped_test else None)
        for task,target in [('GT_G','exception-generate'),('GT_E','existing-extract')]:
            # internal semantic comparison, not the public missing-report task
            a,b='test-ground-truth',target
            ex.add(key(task),'semantic-compare',(key(a),key(b)),build=lambda d,a=key(a),b=key(b),task=task:{'left':d[a]['scenarios'],'right':d[b]['scenarios'],'purpose':task},case=cid)
        if scoped_test:
            add('exception-evaluation',('exception-generate','existing-extract','test-ground-truth','gap-compare','GT_G','GT_E'),build=lambda d:d,
                transform=lambda d:compare_report(d['exception-generate']['scenarios'],d['existing-extract']['scenarios'],d['test-ground-truth']['scenarios'],d['gap-compare']['decisions'],d['GT_G']['decisions'],d['GT_E']['decisions']))
        for task in ('rr-ssd','sr-ssd','object-operations'):extraction_jobs.append((cid,task,key(task)))
    # Each checker reads only its own case, in parallel to positive modeling.
    branch_keys=tuple(cid+':existing-branches' for cid in cases)
    ex.add('existing-branches','existing-branches',branch_keys,build=lambda d:d,
      transform=lambda d:{'branches':[{**b,'id':key+'::'+b['id']} for key,part in d.items() for b in part['branches']]})
    for cid,task,source in extraction_jobs:
        truth_key=task if cid=='shared' else cid+':'+task
        gt=extraction_truth.get(truth_key);decisions=adjudications.get(truth_key)
        from .evaluation import accuracy,not_evaluated
        ex.add(truth_key+':accuracy','extraction-evaluation',(source,),static={'truth':gt,'decisions':decisions},
          build=lambda d,source=source,gt=gt,ds=decisions:{'actual':d[source],'truth':gt,'decisions':ds},
          transform=lambda d,task=task:accuracy(task,d['actual'],d['truth'],d['decisions']) if d['truth'] is not None else not_evaluated(task),case=cid)
