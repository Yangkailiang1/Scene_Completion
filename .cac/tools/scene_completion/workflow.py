"""Independent tasks and a fixed, resumable DAG for scene-workflow-v4.

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
from .task_context import generation_matches
from .normal_rules import documented_normal_tolerance
from .scenario_types import normal_replay_record
from .test_alignment import known_catalogue,exact_alignment
from .exception_comparison import compare_report,missing_report
from .artifact_exports import export_task
from .reviews import REVIEW_TASKS
from .scheduler import Scheduler,Task,TaskRejected,TaskBlocked,CallGate,run_lock
from .storage import read_json,write_json
from .storage import fingerprint
from .concern_registry import default_registry,scoped_execution

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
    if value.get('protocol')!=PROTOCOL: raise ValueError('legacy or unversioned task result cannot enter scene-workflow-v4')
    return value['payload']


def code_version(task):
    folder=Path(__file__).parent
    # The output schema, actual dependency payloads and cache validation already
    # guard shared contracts. Unrelated task implementations must not trigger
    # paid re-extraction of successfully verified upstream models.
    modules={
      'components':['composition_drawing.py'], 'api-map':['api_documents.py'],
      'api-index':['api_documents.py'], 'api-parameters':['api_documents.py'],
      'source-index':['indexed_context.py','source_documents.py'], 'document-context':['indexed_context.py'],
      'use-case-extract':['use_cases.py'], 'use-case-align':['use_cases.py'],
      'fused-ssd':['ssd_tools.py','use_cases.py'], 'ssd-context':['task_context.py'],
      'rr-ssd':['ssd_tools.py'], 'sr-ssd':['ssd_tools.py'],
      'object-operations':['interaction_enrichment.py'], 'interaction-align':['ssd_tools.py'],
      'interaction-enrich':['interaction_enrichment.py','inverse_alignment.py'],
      'normal-rules':['normal_rules.py','task_partitions.py'],
      'existing-concerns':['concern_alignment.py','task_partitions.py','task_context.py'],
      'test-concerns':['scenario_types.py','concern_alignment.py','task_partitions.py','task_context.py'],
      'test-inventory':['test_alignment.py','test_sources.py'], 'test-case-align':['test_alignment.py'],
      'concern-compare':['concern_alignment.py'], 'concern-evaluation':['concern_alignment.py'],
      'concern-match':['concern_alignment.py','normal_rules.py','concern_matching.py','concern_hierarchy.py','task_context.py','task_partitions.py'],
      'exception-generate':['concern_alignment.py','normal_rules.py','exception_generation.py','concern_hierarchy.py','task_context.py','task_partitions.py'],
      'existing-branches':['source_documents.py','branch_evidence.py'], 'existing-bind':['inverse_alignment.py','normal_rules.py','task_partitions.py'],
      'existing-extract':['concern_alignment.py','inverse_alignment.py','normal_rules.py','task_partitions.py'],
      'test-ground-truth':['concern_alignment.py','inverse_alignment.py','normal_rules.py','task_partitions.py'],
      'gap-compare':['exception_comparison.py','comparison_batches.py','assignment.py','normal_rules.py'],
      'semantic-compare':['comparison_batches.py','assignment.py','normal_rules.py'],
      'missing-report':['exception_comparison.py','artifact_exports.py'],
      'exception-evaluation':['exception_comparison.py','assignment.py'],
      'extraction-evaluation':['evaluation.py','assignment.py'], 'enriched-view':['interaction_enrichment.py'],
      'test-operation-project':['source_documents.py'], 'gap-recommend':['recommendation.py','scenario_patterns.py'], 'pattern-applicability':['scenario_patterns.py','exception_generation.py','normal_rules.py']}
    names=modules.get(task,[])
    if task in {'components','api-map','api-parameters','use-case-extract','use-case-align','fused-ssd','normal-rules','test-operation-project'}:names=names+['positive_reuse.py']
    if task=='test-supplement':names=['test_supplement.py','task_partitions.py','task_context.py','scenario_patterns.py']
    if task in {'test-expanded','test-additional-truth','test-additional-dedup'}:names=['test_supplement.py']
    if task in {'exception-generate','existing-extract','test-ground-truth','existing-branches'}:names=names+['scenario_types.py','test_sources.py']
    if task in {'existing-bind','existing-extract','test-ground-truth'}:names=names+['failure_units.py']
    if task in {'existing-extract','test-ground-truth','test-additional-truth'}:names=names+['scenario_patterns.py']
    if task in {'gap-compare','semantic-compare'}:names=names+['task_context.py']
    if task in {'interaction-enrich','exception-generate','pattern-applicability','existing-extract','test-ground-truth','test-supplement','test-additional-truth'}:names=names+['data_requirements.py']
    if task in {'existing-extract','test-ground-truth'}:names=names+['refinement_context.py']
    if task=='test-ground-truth':names=names+['validation.py']
    if task in TASKS or task in {'use-case-extract','use-case-align','fused-ssd','test-ground-truth','semantic-compare','test-operation-project'}:names=names+['deepagents_client.py','model_client.py','indexed_context.py']
    skill=skill_path(task)
    implementation=fingerprint({**{n:(folder/n).read_text(encoding='utf8') for n in names},'rules':skill.read_text(encoding='utf8')})
    return implementation

def skill_path(task):
    tool_skills={'source-index':'scene-context-index','ssd-context':'scene-context-index','interaction-enrich':'scene-interaction-attributes','interaction-align':'scene-ssd-structure'}
    if task in tool_skills:return Path(__file__).resolve().parents[2]/'skills'/tool_skills[task]/'SKILL.md'
    if task in TASKS:return Path(__file__).resolve().parents[2]/'skills'/TASKS[task][0]/'SKILL.md'
    internal={'test-operation-project','test-ground-truth','interaction-align','semantic-compare','api-index'}
    return Path(__file__).parent/'prompts'/((task if task in internal else 'tool-task')+'.md')


class Execution:
    def __init__(self,root,*,mode='packets',client=None,responses_dir=None,mocks=None,config=None,case_ids=None,auto_repair='bounded',max_rounds=2):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.registry_snapshot=read_json(self.root/'registry_override.json') if (self.root/'registry_override.json').exists() else default_registry()
        self.mode,self.client,self.responses_dir,self.mocks=mode,client,Path(responses_dir) if responses_dir else None,mocks
        self.config=config or getattr(client,'config',{}) or {};self.case_ids=case_ids or []
        from .scenario_patterns import normalize_settings
        from .concern_registry import registry_scope
        with registry_scope(self.registry_snapshot):
            self.pattern_settings=normalize_settings(read_json(self.root/'pattern_settings_used.json')) if (self.root/'pattern_settings_used.json').exists() else normalize_settings()
        self.recommendation_history=read_json(self.root/'recommendation_history_used.json') if (self.root/'recommendation_history_used.json').exists() else []
        from .reviews import Reviews
        from .node_conversations import Conversations
        self.conversations=Conversations(self.root)
        self.reviews=Reviews(self.root,self.config.get('review_mode','auto'))
        self.expand_pipeline=None
        self.expand_api=None
        self.partitions=[]
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
        used=self.root/'registry_used'/(self.registry_snapshot['hash']+'.json')
        if not used.exists():write_json(used,self.registry_snapshot)
        if previous and previous.get('registry_hash') and previous['registry_hash']!=self.registry_snapshot['hash']:
            import shutil,time
            archive=self.root/'report_versions'/(previous['registry_hash'][:16]+'-'+str(time.time_ns()))
            for name in ('missing_report.json','missing_report.md','run_manifest.json','workflow_tasks.json','workflow_graph.json'):
                source=self.root/name
                if source.exists():archive.mkdir(parents=True,exist_ok=True);shutil.copy2(source,archive/name)
        if previous and self.config.get('scenario_patterns',False) and previous.get('pattern_settings_hash')!=self.pattern_settings['hash']:
            import shutil,time
            archive=self.root/'report_versions'/('patterns-'+str(previous.get('pattern_settings_hash','legacy'))[:16]+'-'+str(time.time_ns()))
            for name in ('missing_report.json','missing_report.md','run_manifest.json','workflow_tasks.json','workflow_graph.json'):
                source=self.root/name
                if source.exists():archive.mkdir(parents=True,exist_ok=True);shutil.copy2(source,archive/name)
        from .normal_rules import RULESET_VERSION
        if previous and previous.get('ruleset_version') and previous['ruleset_version']!=RULESET_VERSION:
            import shutil,time
            archive=self.root/'report_versions'/('rules-'+previous['ruleset_version']+'-'+str(time.time_ns()))
            archive.mkdir(parents=True,exist_ok=True)
            from .result_views import ResultView
            old_metrics=ResultView(self.root.parent).metrics()
            write_json(archive/'metrics_summary.json',{k:old_metrics.get(k) for k in ('metrics','ruleset_version','matching_version','cases','test_set')})
            for name in ('missing_report.json','missing_report.md','run_manifest.json','workflow_tasks.json','workflow_graph.json'):
                if (self.root/name).exists():shutil.copy2(self.root/name,archive/name)
        self.manifest={'protocol':PROTOCOL,'complete':False,'execution_identity':self.identity,
                       'registry_hash':self.registry_snapshot['hash'],'registry_version':self.registry_snapshot['version'],'recommendation':{'enabled':False,'status':'未启用'},'formal':False}
        self.manifest['ruleset_version']=RULESET_VERSION
        self.manifest['evaluation_version']=RULESET_VERSION
        from .concern_alignment import VERSION
        self.manifest['matching_version']=VERSION
        if self.config.get('scenario_patterns',False):self.manifest.update(pattern_settings_hash=self.pattern_settings['hash'],pattern_library_version=self.pattern_settings['library']['version'],recommendation={'enabled':True,'status':'等待缺失集合M'})
        write_json(manifest,self.manifest)
        self.scheduler=Scheduler(self.root,concurrency=self.config.get('max_concurrency',1),auto_repair=auto_repair,max_rounds=max_rounds)
        import time
        self.session_id=fingerprint([time.time_ns(),str(self.root)])[:20]
        sessions=read_json(self.root/'execution_sessions.json') if (self.root/'execution_sessions.json').exists() else []
        sessions.append({'id':self.session_id,'started_at':time.time(),'finished_at':None,'status':'running'})
        write_json(self.root/'execution_sessions.json',sessions)
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
            client.shared_call_gate=self.gate
            original=client.post
            client.post=lambda *a,**k:self.gate.call(original,*a,**k)

    def semantic(self,task,inputs,record):
        p=packet(task,inputs,[record['case']] if record.get('case') not in (None,'shared') else [])
        from .execution_events import context
        _,event_context=context()
        p['node_key']=event_context.get('task_key',task)
        from .usage_audit import context_summary
        from .execution_events import emit
        emit('context_prepared',task=task,context=context_summary(inputs))
        p['skill_text']=self.skill_text(task)
        if task=='exception-generate':
            # These are derived only from this task's positive inputs. They are
            # not E/GT, previous G, or semantic answers from another channel.
            from .normal_rules import rule_exceptions
            p['tool_rule_coverage']={'data':data_exceptions(inputs),'query':query_exceptions(inputs),'availability':service_exceptions(inputs),'storage':storage_exceptions(inputs),'normal_rules':rule_exceptions(inputs),'pending':pending_rules(inputs)}
            p['tool_rule_instruction']='工具会合并上述确定性候选。模型只需返回其他有具体正常规则支持的双方/操作异常，可返回空scenarios；不要改写字段规则或编造后续行为。'
        if task=='concern-match':
            p['tool_rule_instruction']='本任务先独立识别本片四要素对象上的全部适用具体关注点，包括可用性和明示字段约束。注册表只是候选，工具不会补成识别结果。逐项返回证据；未知规则写pending，不输出具体异常场景。'
        if record.get('rounds'):
            p['repair']={'failure':record.get('failure'),'round':record['rounds'],'rule':'仅修复本任务；不读取其他通道。'}
            candidate=(record.get('failure') or {}).get('rejected_output')
            if candidate:
                path=(self.root/candidate).resolve()
                if path.is_relative_to(self.root.resolve()) and path.is_file():
                    previous=read_json(path)
                    if previous.get('task')==task and previous.get('node_key')==p['node_key'] and previous.get('input_hash')==fingerprint(inputs):
                        p['repair']['candidate']=previous['payload']
                        if previous.get('candidate_format')=='model':p['repair']['candidate_format']='model'
                        p['repair']['rule']='候选尚未通过校验。只定向修复列出的错误，保留有据且合法的部分；所有字段仍须重新满足Schema、当前指导与原文引用。'
        p['batch_id']=fingerprint({k:v for k,v in p.items() if k!='batch_id'})
        batch=p['batch_id'];write_json(self.root/'packets'/(batch+'.json'),p)
        if self.mode=='external' and self.mocks is None:
            from .positive_reuse import find
            reused=find(self.root,task,inputs,p['case_ids'],p['skill_text'])
            if reused:
                value,source=reused;emit('result_reused',**source,reason='unchanged positive source/contract/Skill; actual scope and evidence revalidated')
                return value,{'provider':'verified_positive_reuse',**source}
        semantic_identity=fingerprint({'task':task,'input':inputs,'skill':p['skill_text'],'schema':p['output_schema'],
          'endpoint':self.identity['endpoint_hash'],'model':self.identity['model'],'guidance':self.conversations.revision(p['node_key'])})
        cached_response=self.root/'semantic_responses'/(semantic_identity+'.json')
        if self.mode=='external' and self.mocks is None and cached_response.exists() and not record.get('rounds'):
            cached=read_json(cached_response)
            try:validate_result(task,cached['payload'],inputs)
            except ValueError:pass
            else:
                emit('result_reused',source_file=str(cached_response.relative_to(self.root)),reason='相同语义输入、Schema、Skill、模型及指导；重新执行工具规范化')
                return deepcopy(cached['payload']),{'semantic_response_reused':True,'original_execution':cached.get('proof')}
        if self.mode=='external' and self.mocks is None and task in {'concern-match','existing-concerns','test-concerns','existing-extract','test-ground-truth'}:
            from .semantic_reuse import identity as reuse_identity,index as reuse_index
            if not hasattr(self,'_semantic_seeds'):
                self._semantic_seeds=reuse_index(self.root,self.identity['model'],self.identity['endpoint_hash'],self.conversations)
            projected=reuse_identity(task,inputs,p['skill_text'],p['output_schema'],self.identity['model'],self.identity['endpoint_hash'],self.conversations.revision(p['node_key']))
            seed=self._semantic_seeds.get(projected)
            if seed:
                cached=read_json(seed);value=deepcopy(cached['payload'])
                if task in {'concern-match','existing-concerns','test-concerns'}:
                    from .concern_alignment import recognize
                    value=recognize(inputs,value,inverse=task!='concern-match')
                try:validate_result(task,value,inputs)
                except (ValueError,KeyError,TypeError):pass
                else:
                    emit('result_reused',source_file=str(seed.relative_to(self.root)),reason='同一识别输入与Skill，工具定位/展示字段变化；已重新规范化及校验，不重复调用模型')
                    return value,{'semantic_response_reused':True,'tool_only_reprocessing':True,'original_execution':cached.get('proof')}
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
        if self.mode=='external' and self.mocks is None:write_json(cached_response,{'identity':semantic_identity,'payload':value,'proof':proof})
        return value,proof

    def skill_text(self,task):
        return skill_path(task).read_text(encoding='utf8')

    @scoped_execution
    def add(self,key,task,deps=(),static=None,build=None,transform=None,semantic_task=None,case=None,skip_review=False):
        static=static or {}
        review_identity=fingerprint([self.reviews.execution_identity,code_version(task),schema(task) if task in SCHEMAS else None,self.conversations.revision(key)])
        def inputs_for(dependencies):
            values={k:payload(v) for k,v in dependencies.items()}
            return build(values) if build else deepcopy(static)
        def execute(dependencies,record):
            inputs=inputs_for(dependencies)
            reviewed=self.reviews.cached(key,task,inputs,review_identity) if task in REVIEW_TASKS and not skip_review else None
            if reviewed is not None:
                value=reviewed;proof={'reviewed':True}
            elif transform:
                value=transform(inputs);proof={}
            elif task=='test-inventory' and (known:=known_catalogue(inputs['test-documents'])) is not None:
                value=known;proof={'provider':'explicit_test_structure','reason':'按原文明示字段/EXT标签整理，不改变场景类型'}
            elif task=='test-case-align' and (aligned:=exact_alignment(inputs)) is not None:
                value=aligned;proof={'provider':'explicit_case_identifiers'}
            elif task=='test-ground-truth' and documented_normal_tolerance(inputs):
                value={'scenarios':[],'pending':[]};proof={'provider':'documented_normal_tolerance','reason':'本测试明确为可选容错且预期允许隐藏/缺省，不违反约定，不进入异常GT；测试原文保存在任务输入'}
            elif task=='test-supplement' and not any(not r['concern_key'].startswith('api.data.') for r in inputs['normal-rules']['rules']):
                value={'tests':[]};proof={'provider':'independent_positive_contract_tests','reason':'明确字段约束和服务可用性由独立测试工具补全，不读取G/E'}
            elif task=='existing-extract' and 'bindings' in inputs and not any(b['status']=='confirmed' for b in inputs['bindings']['bindings']):
                value={'scenarios':[]};proof={'provider':'unconfirmed_branch','reason':'没有已确认的异常交互绑定；保留待确认分支，不调用模型补造'}
            elif task in {'test-concerns','test-ground-truth'} and (source:=normal_replay_record(inputs)) is not None:
                value={('matches' if task=='test-concerns' else 'scenarios'):[],'pending':[],'excluded':[{'original_id':source['id'],'scenario_type':'normal','reason':'原始表标为异常，但触发仅相同幂等键正常重试、预期返回已有且不重复创建；不计关注点或异常场景','source_refs':source['source_refs']}]};proof={'provider':'documented_normal_replay'}
            elif task in {'existing-extract','test-ground-truth'} and 'identified-concerns' in inputs and not any(m.get('status')=='applicable' for m in inputs['identified-concerns']['matches']):
                from .source_documents import evidence_refs
                source=inputs.get('test-documents',inputs.get('existing-documents',[]))
                pending=deepcopy(inputs['identified-concerns'].get('pending',[]))
                excluded=deepcopy(inputs['identified-concerns'].get('excluded',[]))
                if not pending and not excluded:
                    pending=[{'interaction_id':'unbound','object':'待定位对象','concern_key':'未识别',
                              'reason':'本片异常来源尚未识别到确定关注点，场景细化暂缓；未将其视为正常或已覆盖','source_refs':[{'source_id':d['source_id'],'line_start':r['number'],'line_end':r['number'],'quote':r['text']} for d in source for r in d['lines'] if r['text'].strip()]}]
                value={'scenarios':[],'pending':pending,'excluded':excluded};proof={'provider':'awaiting_identified_concerns'}
            elif task=='exception-generate' and not generation_matches(inputs) and not self.conversations.revision(key):
                value={'scenarios':[],'pending':[]};proof={'provider':'deterministic_rule_coverage','reason':'没有额外适用语义规则；字段/查询/可用性等由独立工具生成，不额外调用模型'}
            elif task in {'gap-compare','semantic-compare'} and (not inputs['left'] or not inputs['right']):value,proof={'decisions':[],**({'missing':deduplicate(inputs['left'])} if task=='gap-compare' else {})},{}
            else:value,proof=self.semantic(semantic_task or task,inputs,record)
            candidate=deepcopy(value)
            try:
                if task=='existing-branches':
                    from .scenario_types import filter_branches
                    from .branch_evidence import complete
                    value=filter_branches(complete(value,inputs))
                if task=='test-supplement':
                    from .test_supplement import mechanical_tests
                    value['tests']=list({fingerprint(t):t for t in value['tests']+mechanical_tests(inputs)['tests']}.values())
                if task=='use-case-align' and self.mocks is None:
                    from .use_cases import canonical_correspondence
                    value=canonical_correspondence(value,inputs)
                if task=='normal-rules':
                    for rule in value['rules']:rule['id']='normal-'+fingerprint({k:v for k,v in rule.items() if k!='id'})[:20]
                if task=='existing-bind':
                    from .failure_units import normalize_bindings
                    value=normalize_bindings(value,inputs)
                if task in {'existing-concerns','test-concerns'}:
                    from .concern_alignment import recognize
                    value=recognize(inputs,value,inverse=True)
                if task=='concern-match':
                    resolved=resolve_matches(inputs,value['matches'])
                    value['matches']=resolved['matches']
                    value['pending']=list({fingerprint(v):v for v in value['pending']+resolved['pending']}.values())
                if task in {'exception-generate','existing-extract','test-ground-truth'} and 'pattern-applicability' not in inputs:
                    from .normal_rules import normalize_scenarios
                    value=normalize_scenarios(value,inputs,truth=task=='test-ground-truth')
                    if task=='exception-generate':
                        from .normal_rules import rule_exceptions
                        value['scenarios']=deduplicate(attach_provenance(inputs,value['scenarios']+data_exceptions(inputs)+query_exceptions(inputs)+service_exceptions(inputs)+storage_exceptions(inputs)+rule_exceptions(inputs)))
                        value['pending']=list({fingerprint(x):x for x in value['pending']+pending_rules(inputs)}.values())
                    else:value['scenarios']=deduplicate(value['scenarios'])
                if task=='existing-extract' and 'fused-ssd' in inputs:
                    from .inverse_alignment import expand_inverse
                    value=expand_inverse(value,inputs)
                if task=='test-ground-truth' and 'fused-ssd' in inputs:
                    from .inverse_alignment import expand_truth
                    value=expand_truth(value,inputs)
                    from .failure_units import normalize_test_assertions
                    value=normalize_test_assertions(value,inputs)
                if task in {'test-ground-truth','existing-extract'}:
                    from .failure_units import normalize_inverse_units
                    value=normalize_inverse_units(value,inputs)
                if task in {'test-ground-truth','existing-extract','exception-generate'} and 'pattern-applicability' not in inputs:
                    from .scenario_types import filter_scenarios
                    value=filter_scenarios(value,inputs,task)
                if self.config.get('scenario_patterns',False) and task in {'existing-extract','test-ground-truth','test-additional-truth'}:
                    from .scenario_patterns import inverse_metadata
                    value=inverse_metadata(value,inputs,self.pattern_settings,truth=task=='test-ground-truth')
                from .execution_events import phase
                phase('validating')
                if task in {'exception-generate','existing-extract','test-ground-truth'}:
                    from .concern_alignment import bind_scenarios
                    identified=inputs.get('concern-match') if task=='exception-generate' else inputs.get('identified-concerns')
                    if identified is not None:
                        value=bind_scenarios(value,inputs,identified,gate=True)
                if task in SCHEMAS:
                    validate_result(task,value,inputs)
            except ValueError as exc:
                rejection=self.root/'agent_rejections'/(fingerprint([key,inputs,candidate,str(exc),'postprocess'])+'.json')
                write_json(rejection,{'task':task,'node_key':key,'input_hash':fingerprint(inputs),'payload':candidate,'error':str(exc)})
                raise TaskRejected({'error':str(exc),'phase':'postprocess','rejected_output':str(rejection.relative_to(self.root))}) from exc
            if reviewed is None and not skip_review:self.reviews.propose(key,task,inputs,value,review_identity)
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
                 'static':fingerprint(static),'identity':self.identity,'guidance_revision':self.conversations.revision(key),'review_revision':self.reviews.revision(key),'cases':self.case_ids,'registry':registry()['hash'] if task in {'existing-concerns','test-concerns','concern-compare','concern-evaluation','normal-rules','concern-match','exception-generate','existing-extract','test-ground-truth','gap-compare','semantic-compare','enriched-view','missing-report','exception-evaluation'} else None}
        if self.config.get('scenario_patterns',False) and task in {'pattern-applicability','existing-extract','test-ground-truth','test-additional-truth','gap-recommend'}:version['pattern_settings_hash']=self.pattern_settings['hash']
        if self.config.get('scenario_patterns',False) and task=='gap-recommend':version.update(history_hash=fingerprint(self.recommendation_history),recommendation_run=self.session_id)
        self.scheduler.add(Task(key,case or 'shared',task,tuple(deps),version=version,execute=execute,repair=execute,verify=verify))

    def partitioned(self,key,task,deps,build,case):
        """Expand after inputs validate; each child has its own review/cache/retry."""
        from .task_partitions import split_task,merge_parts
        def waiting(d):raise TaskBlocked('dependency_wait',{'reason':'等待子任务展开'})
        self.add(key,task,deps,build=build,transform=waiting,case=case)
        self.scheduler.tasks[key].deferred=True
        def expand():
            inputs=build({d:payload(read_json(self.root/self.scheduler.state['tasks'][d]['output_file'])) for d in deps})
            units=split_task(task,inputs);children=[]
            for unit,part in units:
                child=key+'--part-'+fingerprint(unit)[:10];children.append(child)
                inherited={m['detail'].get('parent_message_id') for m in self.conversations.list(child)}
                for message in self.conversations.list(key):
                    if message['kind']=='guidance' and message['id'] not in inherited:
                        self.conversations.append(child,'guidance',message['text'],{'parent_message_id':message['id'],'parent_task':key})
                self.add(child,task,deps,static=part,build=lambda d,part=part:deepcopy(part),case=case)
                self.scheduler.tasks[child].display_label=TASKS.get(task,('',task))[1]+' · '+unit
            self.scheduler.tasks.pop(key)
            self.add(key,task,tuple(children) or deps,build=lambda d,inputs=inputs:inputs,
              transform=lambda d,children=children:merge_parts(task,[payload(read_json(self.root/self.scheduler.state['tasks'][c]['output_file'])) for c in children]),case=case,skip_review=True)
        self.partitions.append((tuple(deps),expand))

    @scoped_execution
    def finish(self):
        def update():
            records=self.scheduler.state['tasks']
            resolved=getattr(self.scheduler,'resolved_tasks',set())
            ready=lambda dependencies:all(d in resolved and records.get(d,{}).get('status')=='passed' for d in dependencies)
            for dependencies,expand in list(self.partitions):
                if ready(dependencies):
                    self.partitions.remove((dependencies,expand));expand()
            api=records.get('api-index',{})
            if self.expand_api and ready(('api-index',)):
                self.scheduler.tasks.pop('api-parameters',None)
                expand=self.expand_api;self.expand_api=None;expand()
            elif self.expand_api and api.get('status') in {'failed','rejected','pending','rate_limited','awaiting_configuration','budget_exhausted','awaiting_answer','awaiting_review'}:
                # A blocked index still declares the final dependency target;
                # the scheduler will never treat it as a complete API table.
                active=api.get('status') in {'failed','rejected'} and api.get('rounds',0)<self.scheduler.rounds
                if not active:
                    if 'api-parameters' not in self.scheduler.tasks:
                        self.add('api-parameters','api-parameters',('api-index',),transform=lambda d:{'apis':[]})
                        self.scheduler.tasks['api-parameters'].deferred=True
            if self.expand_pipeline and ready(('use-case-align','test-case-align')):
                expand=self.expand_pipeline;self.expand_pipeline=None;expand()
            for dependencies,expand in list(self.partitions):
                if ready(dependencies):
                    self.partitions.remove((dependencies,expand));expand()
        self.scheduler.on_update=update
        result=self.scheduler.run()
        if self.expand_api:
            self.scheduler.tasks.pop('api-parameters',None)
            expand=self.expand_api;self.expand_api=None;expand();result=self.scheduler.run()
        if self.expand_pipeline and all(self.scheduler.state['tasks'].get(k,{}).get('status')=='passed' for k in ('use-case-align','test-case-align')):
            expand=self.expand_pipeline;self.expand_pipeline=None;expand();result=self.scheduler.run()
        before=set(self.scheduler.tasks);update()
        if before!=set(self.scheduler.tasks):result=self.scheduler.run()
        self.scheduler.on_update=None
        artifact_root=self.root/'artifacts'
        import shutil
        # Keep independently completed task files; failed siblings cannot erase them.
        (self.root/'missing_report.json').unlink(missing_ok=True)
        (self.root/'missing_report.md').unlink(missing_ok=True)
        reports={};evaluations={};cases={};recommendations={}
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
            if stage=='gap-recommend' and cid!='shared':recommendations[cid]=value['payload']
        if reports:
            from .artifact_exports import export_missing_report
            combined={'protocol':PROTOCOL,'cases':reports,'evaluation':evaluations,
              'recommendation':{'enabled':True,'cases':recommendations} if self.config.get('scenario_patterns',False) else {'enabled':False,'status':'未启用'},'evaluation_status':{
                  c:'已评测' if c in evaluations else '未评测或任务未完成' for c in reports}}
            export_missing_report(self.root,combined)
        analysis_stages={'existing-concerns','concern-compare','fused-ssd','rr-ssd','sr-ssd','object-operations','interaction-align','interaction-enrich','concern-match','enriched-view','exception-generate','existing-extract','gap-compare','missing-report'}
        analysis={c:all(stages.get(s)=='passed' for s in analysis_stages) for c,stages in cases.items() if c!='shared'}
        if self.config.get('scenario_patterns',False):self.manifest['recommendation']={'enabled':True,'status':'已推荐' if recommendations and all(c in recommendations for c in reports) else '等待缺失比较','case_count':len(recommendations)}
        self.manifest.update(complete=result['complete'] and not self.manifest.get('test_import_pending_count',0) and not any(g['status']=='pending' for g in self.manifest.get('case_correspondence',[])) and not any(m['status']!='confirmed' for m in self.manifest.get('test_case_correspondence',[])),analysis_complete=bool(analysis) and all(analysis.values()),
          analysis_by_case=analysis,evaluation_by_case={c:s.get('exception-evaluation','未评测') for c,s in cases.items() if c!='shared'},
          tasks={k:r['status'] for k,r in records.items() if k in self.scheduler.tasks})
        write_json(self.root/'run_manifest.json',self.manifest)
        import time
        sessions=read_json(self.root/'execution_sessions.json')
        for session in sessions:
            if session['id']==self.session_id:session.update(finished_at=time.time(),status='complete' if self.manifest['complete'] else 'waiting')
        write_json(self.root/'execution_sessions.json',sessions)
        return self.manifest


def safe_case(case):
    return fingerprint(case)[:12]


def build_pipeline(ex,rr,sr,tests,extraction_truth=None,adjudications=None):
    ex.manifest.update(test_policy='exception-only-v1',test_source_hash=fingerprint(tests),test_supplement_enabled=bool(ex.config.get('supplement_tests',False)))
    if (ex.root.parent/'project.json').exists():
        project=read_json(ex.root.parent/'project.json');ex.manifest['test_source_version']=project.get('test_source_version',fingerprint(project['sources']['test'])[:20])
    from .source_documents import discover_cases,case_projection,current_projection
    extraction_truth=extraction_truth or {};adjudications=adjudications or {}
    from .indexed_context import markdown_index,task_document_view,catalogue_context
    ex.add('source-index','source-index',static={'documents':rr+sr},transform=lambda d:markdown_index(d['documents']))
    rr=current_projection(rr);sr=current_projection(sr)
    normal_rr=normal_projection(rr);normal_sr=normal_projection(sr)
    root_contexts=[('components',{'RR':normal_rr,'SR':normal_sr},'components'),('api-map',{'SR':normal_sr},'api-map')]
    for task,documents,intent in root_contexts:
        context_key=task+'-context'
        ex.add(context_key,'document-context',('source-index',),static=documents,
          transform=lambda d,intent=intent:{role:task_document_view(docs,intent) for role,docs in d.items()})
        ex.scheduler.tasks[context_key].display_label=('系统组成' if task=='components' else 'API映射')+'取片（工具）'
        ex.add(task,task,(context_key,),build=lambda d,k=context_key:d[k])
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
            import re
            source_text='\n'.join(r['text'] for doc in docs for r in doc['lines'])
            if re.search(r'(发送|发起|调用).{0,40}\b(GET|POST|PUT|PATCH|DELETE)\s+/',source_text) and not re.search(r'请求参数|请求头|路径参数|查询参数|数据类型|参数名称|必填|可选|枚举',source_text):
                interface['source_role']='invocation_only'
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
    for layer,docs in [('RR',normal_rr),('SR',normal_sr)]:
        k=layer.lower()+'-catalogue-context'
        ex.add(k,'document-context',('source-index',),static={'documents':docs},
          build=lambda d,docs=docs:{'documents':docs,'index':d['source-index']},transform=lambda d:catalogue_context(d['documents'],d['index']))
        ex.scheduler.tasks[k].display_label=layer+'用例元数据取片（工具）'
        ex.add(layer.lower()+'-use-cases','use-case-extract',(k,),build=lambda d,k=k,layer=layer:{**d[k],'layer':layer})
    if not ex.config.get('scenario_patterns',False):ex.add('gap-recommend','gap-recommend',transform=lambda d:{'enabled':False,'status':'未启用'})
    ex.add('use-case-align','use-case-align',('rr-use-cases','sr-use-cases'),
      build=lambda d:{'rr-cases':d['rr-use-cases'],'sr-cases':d['sr-use-cases']})
    ex.add('test-inventory','test-inventory',static={'test-documents':tests})
    ex.add('test-case-align','test-case-align',('test-inventory','rr-use-cases','sr-use-cases','use-case-align'),
      build=lambda d:{'test-inventory':{**d['test-inventory'],'tests':[]},'rr-cases':d['rr-use-cases'],'sr-cases':d['sr-use-cases'],'case-groups':d['use-case-align']})
    def expand():
        state=ex.scheduler.state['tasks']
        get=lambda key:payload(read_json(ex.root/state[key]['output_file']))
        catalogue={'RR':get('rr-use-cases')['cases'],'SR':get('sr-use-cases')['cases']}
        groups=get('use-case-align')['groups']
        if ex.case_ids:groups=[g for g in groups if g['id'] in ex.case_ids or set(ex.case_ids)&set(g['rr_ids']+g['sr_ids'])]
        ex.manifest['case_correspondence']=groups
        test_catalogue=get('test-inventory');test_alignment=get('test-case-align')
        ex.manifest['test_case_correspondence']=test_alignment['matches']
        ex.manifest['test_import_pending_count']=len(test_catalogue.get('pending',[]))
        _build_cases(ex,rr,sr,tests,catalogue,groups,extraction_truth,adjudications,test_catalogue,test_alignment)
    ex.expand_pipeline=expand


def _build_cases(ex,rr,sr,tests,catalogue,groups,extraction_truth,adjudications,test_catalogue=None,test_alignment=None):
    from .use_cases import select_documents
    from .source_documents import case_projection
    from .api_documents import case_parameters
    cases=[g['id'] for g in groups if g['status']=='confirmed']
    extraction_jobs=[('shared',t,t) for t in ('components','api-map','api-parameters')]
    for cid in cases:
        key=lambda t:cid+':'+t
        # Translate scheduler keys to task contract names only within this case.
        def add(task,deps=(),static=None,build=None,transform=None,cid=cid,partition=False):
            local=lambda t:t if t in {'components','api-map','api-parameters'} else cid+':'+t
            def construct(d):
                values={t:d[local(t)] for t in deps}
                return build(values) if build else deepcopy(static or {})
            if partition and ex.config.get('partition_tasks',True):ex.partitioned(cid+':'+task,task,tuple(local(t) for t in deps),construct,cid)
            else:ex.add(cid+':'+task,task,tuple(local(t) for t in deps),static=static,build=construct,transform=transform,case=cid)
        group=next(g for g in groups if g['id']==cid)
        scoped_rr=select_documents(rr,[c for c in catalogue['RR'] if c['id'] in group['rr_ids']],catalogue['RR'])
        scoped_sr=select_documents(sr,[c for c in catalogue['SR'] if c['id'] in group['sr_ids']],catalogue['SR'])
        test_ids=list(dict.fromkeys(x for g in groups for x in g['rr_ids']+g['sr_ids']))
        scoped_test=[]
        for tid in group['rr_ids']+group['sr_ids']:scoped_test+=case_projection(tests,tid,test_ids)
        if test_catalogue is not None:
            from .test_alignment import scoped_tests
            scoped_test,case_test_catalogue=scoped_tests(test_catalogue,test_alignment,tests,cid)
        merged_test={}
        for document in scoped_test:
            part=merged_test.setdefault(document['source_id'],{**document,'lines':[]})
            rows={r['number']:r for r in part['lines']}
            for row in document['lines']:
                if row['number'] in rows and rows[row['number']]['text']!=row['text']:raise ValueError('conflicting source text for the same test line')
                rows[row['number']]=row
            part['lines']=[rows[n] for n in sorted(rows)]
        scoped_test=list(merged_test.values())
        from .test_sources import exception_documents,records
        if test_catalogue is not None:
            from .test_alignment import as_records
            test_records=as_records(case_test_catalogue,scoped_test)
            abnormal_catalogue={**case_test_catalogue,'tests':[t for t in case_test_catalogue['tests'] if t['scenario_type']=='exception']}
            abnormal_test=scoped_test if abnormal_catalogue['tests'] else []
            test_input={'test-inventory':abnormal_catalogue}
        else:test_records=records(scoped_test);abnormal_test=exception_documents(scoped_test);test_input={}
        write_json(ex.root/'test_catalogues'/(cid+'.json'),{'records':test_records,'policy':'exception-only','version':'exception-test-sources-v1'})
        add('existing-branches',static={'existing-documents':scoped_rr+scoped_sr})
        from .task_context import ssd_context
        add('ssd-context',('components',),static={'RR':normal_projection(scoped_rr),'SR':normal_projection(scoped_sr),'case-group':group},
          build=lambda d,rr=normal_projection(scoped_rr),sr=normal_projection(scoped_sr),g=group:{'RR':rr,'SR':sr,'components':d['components'],'case-group':g},transform=ssd_context)
        add('fused-ssd',('ssd-context',),build=lambda d:d['ssd-context'])
        for layer in ('RR','SR'):
            add(layer.lower()+'-ssd',('fused-ssd',),build=lambda d:d,transform=lambda d,l=layer:{'interactions':[i for i in d['fused-ssd']['interactions'] if i['layer']==l]})
        add('test-operation-project',static={'test-operation-source':scoped_test},transform=(lambda d:{'objects':[]}) if not scoped_test else None)
        add('object-operations',('components','rr-ssd','test-operation-project'),build=lambda d:{'components':d['components'],'rr-ssd':d['rr-ssd'],'test-operations':d['test-operation-project']},transform=capability_union)
        add('interaction-align',('components','rr-ssd','sr-ssd','fused-ssd'),build=lambda d:d,transform=lambda d:{'aliases':[],'links':d['fused-ssd']['rr_sr_links']})
        positive=normal_projection(scoped_rr)+normal_projection(scoped_sr)
        add('normal-rules',('fused-ssd',),build=lambda d,positive=positive:{'normal-documents':positive,'fused-ssd':d['fused-ssd'],**({'registry':registry()} if registry()['hash']!=default_registry()['hash'] else {})},partition=True)
        normal=('components','rr-ssd','sr-ssd','api-map','api-parameters','object-operations','normal-rules')
        add('interaction-enrich',normal+('interaction-align',),build=lambda d:d,transform=lambda d:canonical_enrich(d))
        positive=normal_projection(scoped_rr)+normal_projection(scoped_sr)
        def concern_input(d,positive=positive):
            v={k:d[k] for k in normal};v=bind_resource_services(v)
            v.update(basic_views(d['interaction-enrich']))
            v['api-parameters']=case_parameters(v,d['interaction-enrich'])
            return {**v,'enriched-interactions':d['interaction-enrich'],'normal-documents':positive,'registry':registry()}
        add('concern-match',normal+('interaction-enrich',),static={'normal-documents':positive},build=concern_input,partition=True)
        add('enriched-view',('interaction-enrich','concern-match'),build=lambda d:d,transform=lambda d:with_concerns(d['interaction-enrich'],d['concern-match']))
        def generation_input(d):
            v=bind_resource_services({k:d[k] for k in normal if k!='object-operations'})
            v.update(basic_views(d['enriched-view']))
            v['api-parameters']=case_parameters(v,d['enriched-view'])
            return {**v,'enriched-interactions':actual_context(d['enriched-view']),'concern-match':d['concern-match'],'registry':registry()}
        if ex.config.get('scenario_patterns',False):
            from .scenario_patterns import applicability,generated
            add('pattern-applicability',tuple(k for k in normal if k!='object-operations')+('enriched-view','concern-match'),
                build=lambda d:{'positive':generation_input(d),'settings':ex.pattern_settings},transform=lambda d:applicability(d['positive'],d['settings']))
            add('exception-generate',('pattern-applicability',),build=lambda d:d,transform=lambda d:generated(d['pattern-applicability']))
        else:
            add('exception-generate',tuple(k for k in normal if k!='object-operations')+('enriched-view','concern-match'),build=generation_input,partition=True)

        add('existing-bind',('existing-branches','fused-ssd','normal-rules'),
            build=lambda d,g=group:{'branches':d['existing-branches'],'fused-ssd':d['fused-ssd'],'case-group':g,'registry':registry(),'normal-rules':d['normal-rules']},partition=True)
        add('existing-concerns',('existing-branches','existing-bind','fused-ssd','api-parameters','api-map','normal-rules'),
            build=lambda d,docs=scoped_rr+scoped_sr:{'existing-documents':docs,'registry':registry(),'branches':d['existing-branches'],'bindings':d['existing-bind'],'fused-ssd':d['fused-ssd'],'normal-constraints':case_parameters(d,d['fused-ssd']),'normal-rules':d['normal-rules']},partition=True)
        from .concern_alignment import compare as compare_concerns,attach_report,bind_scenarios
        add('concern-compare',('concern-match','existing-concerns'),build=lambda d:d,transform=lambda d:compare_concerns(d['concern-match'],d['existing-concerns']))
        add('existing-extract',('existing-branches','existing-bind','fused-ssd','api-parameters','api-map','normal-rules','existing-concerns'),
            build=lambda d,docs=scoped_rr+scoped_sr:{'existing-documents':docs,'registry':registry(),'branches':d['existing-branches'],'bindings':d['existing-bind'],'fused-ssd':d['fused-ssd'],'normal-constraints':case_parameters(d,d['fused-ssd']),'normal-rules':d['normal-rules'],'identified-concerns':d['existing-concerns']},partition=True)
        add('gap-compare',('exception-generate','existing-extract'),build=lambda d:{'left':d['exception-generate']['scenarios'],'right':d['existing-extract']['scenarios'],'purpose':'G_E'})
        add('missing-report',('exception-generate','existing-extract','gap-compare','enriched-view','concern-match','existing-branches','existing-bind','normal-rules','concern-compare'),build=lambda d:d,
            transform=lambda d:{**missing_report(d['exception-generate']['scenarios'],d['existing-extract']['scenarios'],d['gap-compare']['decisions']),
              'interactions':d['enriched-view'],'concerns':d['concern-match']['matches'],'concern_level':d['concern-compare'],
              'original_branches':[b for b in d['existing-branches']['branches'] if b['id'] in {v['branch_id'] for v in d['existing-bind']['bindings'] if v['status']!='not_this_case'}],
              'inverse_bindings':d['existing-bind']['bindings'],
              'pending':d['normal-rules']['pending']+d['enriched-view']['pending']+d['concern-match']['pending']+d['exception-generate']['pending']+[{'interaction_id':b.get('interaction_id') or ('unbound:'+b['branch_id']),'reason':b['basis'],'source_refs':b['source_refs']} for b in d['existing-bind']['bindings'] if b['status']=='pending']})
        if ex.config.get('scenario_patterns',False):
            from .recommendation import rank
            add('gap-recommend',('missing-report','pattern-applicability'),
                build=lambda d,cid=cid:{**d,'settings':ex.pattern_settings,'history':ex.recommendation_history,'case_id':cid,'run_id':ex.session_id},
                transform=lambda d,cid=cid:rank(d['missing-report']['M'],d['pattern-applicability'],d['settings'],d['history'],case_id=d['case_id'],run_id=d['run_id']))
        add('test-concerns',('api-parameters','api-map','fused-ssd','normal-rules'),build=lambda d,tt=abnormal_test,ti=test_input:{'test-documents':tt,**ti,'normal-constraints':case_parameters(d,d['fused-ssd']),'fused-ssd':d['fused-ssd'],'registry':registry(),'normal-rules':d['normal-rules']},transform=(lambda d:{'matches':[],'pending':[]}) if not abnormal_test else None,partition=bool(abnormal_test))
        add('test-ground-truth',('api-parameters','api-map','fused-ssd','normal-rules','test-concerns'),static={'tests':abnormal_test},build=lambda d,tt=abnormal_test,ti=test_input:{'test-documents':tt,**ti,'normal-constraints':case_parameters(d,d['fused-ssd']),'fused-ssd':d['fused-ssd'],'registry':registry(),'normal-rules':d['normal-rules'],'identified-concerns':d['test-concerns']},transform=(lambda d:{'scenarios':[],'pending':[]}) if not abnormal_test else None,partition=bool(abnormal_test))
        for task,target in [('GT_G','exception-generate'),('GT_E','existing-extract')]:
            # internal semantic comparison, not the public missing-report task
            a,b='test-ground-truth',target
            ex.add(key(task),'semantic-compare',(key(a),key(b)),build=lambda d,a=key(a),b=key(b),task=task:{'left':d[a]['scenarios'],'right':d[b]['scenarios'],'purpose':task},case=cid)
        if ex.config.get('supplement_tests',False):
            from .test_supplement import positive_inputs,to_truth,combine_truth,dedup_candidates,deduplicate_truth
            add('test-supplement',('fused-ssd','api-parameters','normal-rules'),build=lambda d,cat=test_records:positive_inputs(d['fused-ssd'],case_parameters(d,d['fused-ssd']),d['normal-rules'],cat,registry()),partition=True)
            from .concern_alignment import supplemental_concerns
            add('test-additional-concerns',('test-supplement','fused-ssd','api-parameters','api-map'),build=lambda d:d,transform=lambda d:supplemental_concerns(d['test-supplement'],d['fused-ssd'],case_parameters(d,d['fused-ssd'])))
            add('test-additional-truth',('test-supplement','fused-ssd','test-additional-concerns','api-parameters','api-map'),build=lambda d:d,transform=lambda d:bind_scenarios(to_truth(d['test-supplement'],{'fused-ssd':d['fused-ssd']}),{'fused-ssd':d['fused-ssd'],'normal-constraints':case_parameters(d,d['fused-ssd'])},d['test-additional-concerns'],gate=True))
            ex.add(key('GT_self'),'semantic-compare',(key('test-additional-truth'),),build=lambda d,a=key('test-additional-truth'):{'left':dedup_candidates(d[a]),'right':dedup_candidates(d[a]),'purpose':'GT_self'},case=cid)
            add('test-additional-dedup',('test-additional-truth','GT_self'),build=lambda d:d,transform=lambda d:deduplicate_truth(d['test-additional-truth'],d['GT_self']['decisions']))
            ex.add(key('GT_dedup'),'semantic-compare',(key('test-additional-dedup'),key('test-ground-truth')),build=lambda d,a=key('test-additional-dedup'),b=key('test-ground-truth'):{'left':d[a]['scenarios'],'right':d[b]['scenarios'],'purpose':'GT_dedup'},case=cid)
            add('test-expanded',('test-ground-truth','test-additional-dedup','GT_dedup'),build=lambda d:d,transform=lambda d:combine_truth(d['test-ground-truth'],d['test-additional-dedup'],d['GT_dedup']['decisions']))
            for task,target in [('GT_expanded_G','exception-generate'),('GT_expanded_E','existing-extract')]:
                ex.add(key(task),'semantic-compare',(key('test-expanded'),key(target)),build=lambda d,a=key('test-expanded'),b=key(target),target=target:{'left':d[a]['scenarios'],'right':d[b]['scenarios'],'purpose':'GT_G' if target=='exception-generate' else 'GT_E'},case=cid)
        concern_extra=('test-additional-concerns',) if ex.config.get('supplement_tests',False) else ()
        def concern_evaluation(d):
            original=compare_concerns(d['concern-match'],d['existing-concerns'],d['test-concerns'])
            expanded={**d['test-concerns'],'matches':d['test-concerns']['matches']+d.get('test-additional-concerns',{}).get('matches',[])}
            value=compare_concerns(d['concern-match'],d['existing-concerns'],expanded) if 'test-additional-concerns' in d else original
            return {**value,'original_evaluation':original}
        add('concern-evaluation',('concern-match','existing-concerns','test-concerns')+concern_extra,build=lambda d:d,transform=concern_evaluation)
        if scoped_test or ex.config.get('supplement_tests',False):
            extra=('test-expanded','GT_expanded_G','GT_expanded_E') if ex.config.get('supplement_tests',False) else ()
            from .test_supplement import evaluate_test_sets
            if ex.config.get('scenario_patterns',False):
                extra=extra+('gap-recommend',)
                from .recommendation import evaluate as evaluate_recommendation
                base_evaluate=evaluate_test_sets
                def evaluate_test_sets(d):
                    report=base_evaluate(d)
                    report=evaluate_recommendation(report,d['gap-recommend'])
                    if 'original_evaluation' in report:report['original_evaluation']=evaluate_recommendation(report['original_evaluation'],d['gap-recommend'])
                    return report
            scene_evaluate=evaluate_test_sets
            def evaluate_two_levels(d,fn=scene_evaluate):
                return attach_report(fn(d),d['concern-evaluation'],original=d['concern-evaluation']['original_evaluation'])
            add('exception-evaluation',('exception-generate','existing-extract','test-ground-truth','gap-compare','GT_G','GT_E','concern-evaluation')+extra,build=lambda d:d,transform=evaluate_two_levels)
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
