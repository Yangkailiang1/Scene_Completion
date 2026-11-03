"""Import-to-DAG preview built by the real workflow registrars, never executed.

Temporary outputs exist only to expand known API directories. They are not
project task results, case confirmations, artifacts, cache hits or progress.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from copy import deepcopy
from .storage import read_json,write_json,fingerprint
from .artifact_imports import snapshot,selections,purpose
from .execution_graph import LABELS,INPUTS,expected_files
from .deepagents_client import role_for

VERSION='input-dependency-preview-v3-complete-behavior'
MODES={'reuse':'可复用，跳过对应LLM抽取','partial':'部分已提供，仍补缺项','basis':'作为依据，仍需分析','pending':'未采用，待确认','execute':'仍需执行','tool':'工具整理，不调用模型'}


def with_execution(project,plan):
    result=deepcopy(plan);root=Path(project)/'run'
    state=read_json(root/'workflow_tasks.json').get('tasks',{}) if (root/'workflow_tasks.json').exists() else {}
    manifest=read_json(root/'run_manifest.json') if (root/'run_manifest.json').exists() else {}
    aliases={}
    for group in plan.get('case_candidates',[]):
        found=[g for g in manifest.get('case_correspondence',[]) if set(g['rr_ids'])==set(group['rr_ids']) and set(g['sr_ids'])==set(group['sr_ids']) and g['status']=='confirmed']
        if len(found)==1:aliases[group['id']]=found[0]['id']
    for node in result['nodes']:
        key=node.get('target_key') or ''
        if ':' in key:
            case,suffix=key.split(':',1);key=aliases.get(case,'unconfirmed')+':'+suffix
        record=state.get(key,{})
        if not record:continue
        node['execution_task_key']=key;node['execution_status']=record['status']
        current={b['file_id']:b['revision'] for b in node.get('input_bindings',[])}
        actual=record.get('import_sources',[])
        node['actual_input_used']=record['status']=='passed' and bool(actual) and all(s['file_id'] in current and s['revision']==current[s['file_id']] for s in actual)
        node['actual_import_reuse']=node['actual_input_used'] and record.get('provenance') in {'同事产物导入','已有文件输入'}
        from .artifact_imports import provenance_label
        node['execution_provenance']=provenance_label(record.get('provenance','原流程生成'))
    return result

class Plan:
    def __init__(self,root,imports,config):
        self.root=Path(root);self.import_snapshot=imports;self.config={**config,'partition_tasks':False};self.case_ids=[]
        self.manifest={};self.partitions=[];self.session_id='preview';self.pattern_settings={};self.recommendation_history=[]
        self.evaluation_scope='SR';self.scheduler=SimpleNamespace(tasks={},state={'tasks':{}},priority_cases=[])
    def add(self,key,stage,deps=(),**kwargs):
        if key in self.scheduler.tasks:raise ValueError('duplicate preview task '+key)
        self.scheduler.tasks[key]=SimpleNamespace(key=key,stage=stage,deps=deps,case=kwargs.get('case','shared'),display_label=None,**kwargs_to_task(kwargs))

def kwargs_to_task(kwargs):return {'transform':kwargs.get('transform'),'build':kwargs.get('build'),'static':kwargs.get('static',{})}


def build(project):
    from .source_documents import read_project_documents
    from .structure_models import imported_sources,catalogue as structured_catalogue,existing_branches
    from .workflow import build_pipeline,_build_cases
    from .api_layers import merge_mappings,qualify_index
    from .api_documents import index_interfaces
    project=Path(project);meta=read_json(project/'project.json');imports=snapshot(project)
    if not imports:return None
    config=read_json(project/'model.local.json') if (project/'model.local.json').exists() else {}
    flags={k:bool(config.get(k,False)) for k in ('scenario_patterns','supplement_tests')}
    identity=fingerprint([VERSION,[(x['id'],x['revision'],x.get('structure_enabled',True)) for x in imports],meta['sources'],meta.get('case_ids',[]),flags,Path(__file__).with_name('workflow.py').read_text()])
    cache=project/'imports/dependency-preview.json'
    if cache.exists() and (saved:=read_json(cache)).get('identity')==identity:return with_execution(project,saved)
    docs={role:read_project_documents(project,meta['sources'].get(role,[]),'test' if role=='test' else 'existing') for role in ('RR','SR','AR','test')}
    structured=imported_sources(imports)
    for layer,doc in structured.items():docs[layer]=[doc]
    catalogues={layer:structured_catalogue(docs[layer],layer) for layer in ('RR','SR')}
    groups=[];case_labels={}
    if all(catalogues.values()):
        # Names suggest a preview only; the real use-case-align task still runs.
        for n,rr in enumerate(catalogues['RR']['cases'],1):
            matches=[sr for sr in catalogues['SR']['cases'] if sr['name']==rr['name']]
            if len(matches)!=1:continue
            cid='preview-case-'+str(n).zfill(3)
            if meta.get('case_ids') and not set(meta['case_ids'])&{rr['id'],matches[0]['id']}:continue
            groups.append({'id':cid,'rr_ids':[rr['id']],'sr_ids':[matches[0]['id']],'status':'confirmed','reason':'仅用于依赖预览，同名候选未确认为执行对应','source_refs':rr['source_refs']})
            case_labels[cid]=rr['name']+'（待用例对应）'
    with TemporaryDirectory(prefix='scene-import-plan-') as temporary:
        ex=Plan(Path(temporary)/'run',imports,flags);ex.root.mkdir()
        build_pipeline(ex,docs['RR'],docs['SR'],docs['test'],ar=docs['AR'])
        # Expand only interfaces literally supplied and accepted, with real IDs.
        maps={layer:{'services':[s for a in selections(project,'api-map',frozen=imports) if a.get('source_layer')==layer for s in a['payload']['services']]} for layer in ('RR','SR')}
        def put(key,value):
            from .contracts import PROTOCOL
            name=key+'.json';write_json(ex.root/name,{'protocol':PROTOCOL,'payload':value});ex.scheduler.state['tasks'][key]={'status':'passed','output_file':name}
        for layer in ('RR','SR'):put(layer.lower()+'-api-map',maps[layer])
        put('api-map',merge_mappings([(layer,maps[layer]) for layer in ('RR','SR')]))
        indexes={}
        # The literal directory index must use the same API documents as execution.
        for layer in ('RR','SR'):
            imported_docs=[a['document'] for task in ('api-map','api-parameters') for a in selections(project,task,frozen=imports) if a.get('source_layer')==layer]
            indexes[layer]=index_interfaces({layer:docs[layer]+imported_docs,'api-map':maps[layer]})
        put('api-index',{'apis':qualify_index(indexes['RR'],'RR')['apis']+qualify_index(indexes['SR'],'SR')['apis']})
        ex.expand_api()
        if groups:_build_cases(ex,docs['RR'],docs['SR'],docs['test'],{layer:catalogues[layer]['cases'] for layer in ('RR','SR')},groups,{}, {},ar=docs['AR'])
        tasks=list(ex.scheduler.tasks.values())
    file_rows=[{'file_id':r['id'],'name':r['name'],'purpose':purpose(r),'revision':r['revision'],'original':r['original']} for r in imports]
    active={(a['file_id'],a['id']) for task in ('business-entities','api-map','api-parameters') for a in selections(project,task,frozen=imports)}
    nodes=[];edges=[]
    for task in tasks:
        bindings=[];mode='tool' if task.transform else 'execute'
        for row in imports:
            hit=None;why='';model=row.get('structure_model')
            behavior=row.get('behavior_product')
            from .behavior_imports import VERSION as behavior_version
            behavior_active=bool(row.get('behavior_enabled') and behavior and behavior.get('version')==behavior_version)
            if behavior and task.case in case_labels:
                group=next((g for g in groups if g['id']==task.case),{})
                scope=group.get('rr_ids',[])+group.get('sr_ids',[])+[case_labels[task.case].removesuffix('（待用例对应）')]
                belongs=behavior.get('case_name') in scope or bool(set(behavior.get('case_ids',[]))&set(scope))
                if belongs and task.stage in {'ssd-context','fused-ssd','rr-ssd','sr-ssd','normal-rules','business-crud'}:
                    hit='basis' if behavior_active else 'pending'
                    why=('SR内部交互定义来自完整行为；未被主成功时序引用的内容继续按SR场景分流' if behavior['kind']=='sr_complete' else
                         '主成功文件只提供时序引用，定义向同操作完整行为解析' if behavior['kind']=='sr_main' else
                         'RR外部交互及已分类场景补充本用例')+'；完整融合与最小调用身份仍须校验，缺项由原流程补齐'
                if belongs and task.stage=='existing-branches' and behavior['kind']=='scenarios':
                    hit='basis' if behavior_active else 'pending'
                    why='仅明示exception进入已有异常E；主成功/备选分离，不作为测试GT'
            if model and row.get('structure_enabled',True):
                layer=model['layer']
                if task.key==layer.lower()+'-use-cases':hit='reuse';why='已提供结构化用例目录，运行时工具校验复用'
                elif task.stage=='existing-branches' and task.case in case_labels:hit='reuse';why='已有异常分支来自本层结构化场景；绑定与关注点识别仍执行'
                elif task.stage in {'fused-ssd','components','use-case-align'}:hit='basis';why='提供用例、正向描述及对象依据，仍需本任务分析'
            if row.get('role')=='test':
                if task.key=='test-inventory':hit='reuse';why='测试逆向需求场景可直接整理目录；不跳过绑定和GT识别'
                elif task.stage in {'test-case-align','test-concerns','test-ground-truth'}:hit='basis';why='独立测试通道，需要用例、交互与关注点对应'
            for a in row['artifacts']:
                selected=(row['id'],a['id']) in active
                if a['task']=='api-map' and task.key==(a.get('source_layer') or 'SR').lower()+'-api-map':
                    hit='reuse' if selected and a['coverage']=='complete' else 'partial' if selected else 'pending';why='复用已声明层级的接口归属；不同层不混用'
                elif a['task']=='api-parameters' and task.stage=='api-parameters' and task.key.startswith('api-parameters-part-'):
                    from .storage import fingerprint as fp
                    ids={aapi['id'] if str(aapi['id']).startswith(('RR::','SR::')) else (a.get('source_layer') or 'SR')+'::'+aapi['id'] for aapi in a['payload']['apis']}
                    if task.key not in {'api-parameters-part-'+fp(aid)[:12] for aid in ids}:continue
                    hit='partial' if selected else 'pending';why='请求字段已提供；未声明的成功/失败响应与属性仍补抽'
                elif a['task']=='business-entities':
                    if task.key=='business-entities-imports':hit='reuse' if selected else 'pending';why='导入已声明实体属性部分，不代表项目全部实体完成'
                    elif task.stage in {'business-entities','business-crud','business-attribute-map','interaction-enrich'} and not task.key.startswith('business-entities-part-'):
                        hit='basis' if selected else 'pending';why='按用例范围提供实体及属性依据，不直接证明CRUD和关注点'
            if hit:
                bindings.append({**next(f for f in file_rows if f['file_id']==row['id']),'mode':hit,'explanation':why})
        if bindings:
            modes={b['mode'] for b in bindings};mode=next((m for m in ('partial','reuse','basis','pending') if m in modes),mode)
        key='planned:'+task.key
        deps=['planned:'+k for k in task.deps]
        nodes.append({'id':key,'target_key':task.key,'stage':task.stage,'case':case_labels.get(task.case,task.case),'role':role_for(task.stage),'label':task.display_label or LABELS.get(task.stage,task.stage),
          'planned':True,'status':'planned','phase':'planned','deps':deps,'expected_files':expected_files(task.key,task.case,task.stage),'artifacts':[],'input_summary':INPUTS.get(task.key,INPUTS.get(task.stage,'依赖上游校验产物')),
          'blocked_by':[],'failure':None,'attempt':0,'elapsed_seconds':None,'last_event_at':None,'import_mode':mode,'import_label':MODES[mode],'input_bindings':bindings})
        edges.extend({'id':d+'->'+key,'source':d,'target':key} for d in deps)
    ids={n['id'] for n in nodes};edges=[e for e in edges if e['source'] in ids]
    # Real global fan-out is dependency-specific and is not known before analysis.
    for role,stage,label,parents in [('modeler','global-concerns','全局关注点与场景分析',['business-dependencies']),('checker','global-compare','全局关注点／场景匹配',['global-concerns']),('recommender','global-recommend','全局风险推荐与指标',['global-compare'])]:
        key='planned:'+stage
        if key in ids:continue
        deps=['planned:'+p for p in parents]
        nodes.append({'id':key,'target_key':None,'stage':stage,'case':'全局依赖待分析','role':role,'label':label,'planned':True,'status':'planned','phase':'planned','deps':deps,'expected_files':[],'artifacts':[],'input_summary':'具体依赖边或级联组确定后动态展开','blocked_by':[],'failure':None,'attempt':0,'elapsed_seconds':None,'last_event_at':None,'import_mode':'execute','import_label':'动态展开，仍需执行','input_bindings':[]})
        edges.extend({'id':d+'->'+key,'source':d,'target':key} for d in deps if d in ids);ids.add(key)
    result={'identity':identity,'version':VERSION,'preview_only':True,'model_calls':0,'nodes':nodes,'edges':edges,'files':file_rows,'definition_available':True,'case_expansion_pending':True,'case_preview_count':len(groups),'case_candidates':[{**g,'status':'candidate'} for g in groups],
      'summary':{m:sum(n['import_mode']==m for n in nodes) for m in MODES},'roles':[{'id':r,'label':label,'completed':0,'known':0,'disabled':False} for r,label in [('modeler','建模器'),('checker','检查器'),('recommender','推荐器')]]}
    write_json(cache,result);return with_execution(project,result)
