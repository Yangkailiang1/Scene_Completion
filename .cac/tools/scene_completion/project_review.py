"""Project-owned concern versions and evidence-bound pending decisions."""
from pathlib import Path
from copy import deepcopy
import re,time,json
from functools import wraps
from .storage import read_json,write_json,fingerprint
from .concern_registry import default_registry,validate_registry
from .execution_events import EventStore

def project_scoped(fn):
    @wraps(fn)
    def call(service,rid,*args,**kwargs):
        from .concern_registry import registry_scope
        with registry_scope(project_registry(service.run_dir(rid))):return fn(service,rid,*args,**kwargs)
    return call

LAYERS={'base','functional','technology','human','relation','shared'}
GROUPS={'base':{'service_base'},'human':{'human'},'relation':{'service_relation'},'shared':{'api_data'},
 'functional':{'display_interaction','query_retrieval','resource_mutation','analysis_generation','release_activation'},'technology':{'database','llm'}}

def project_registry(project):
    project=Path(project);p=project/'run/registry_override.json'
    if p.exists():return read_json(p)
    value=default_registry();manifest=project/'run/run_manifest.json'
    if manifest.exists():
        previous=read_json(manifest).get('registry_hash');used=project/'run/registry_used'/(str(previous)+'.json')
        if used.exists():value=read_json(used)
    # Pin the initial project template, so a later global template update does
    # not silently change definitions in an existing project.
    write_json(p,value);return value


def registry_view(project,version=None):
    project=Path(project);history=project/'concern_versions'
    versions=sorted([read_json(p) for p in history.glob('*.json')],key=lambda v:v['revision'],reverse=True)
    current=project_registry(project)
    manifest=project/'run/run_manifest.json'
    if manifest.exists() and read_json(manifest).get('registry_hash')==current['hash']:
        used=project/'run/registry_used'/(current['hash']+'.json')
        if not used.exists():write_json(used,current)
    for p in (project/'run/registry_used').glob('*.json'):
        if not any(v['hash']==p.stem for v in versions):versions.append({'revision':0,'hash':p.stem,'at':p.stat().st_mtime,'note':'执行时冻结的定义','registry':read_json(p)})
    selected=next((v['registry'] for v in versions if v['hash']==version),None) if version else current
    if selected is None:raise ValueError('未知关注点版本')
    reports=[{'name':p.name,'path':str(p.relative_to(project)).replace('\\','/')} for p in (project/'run/report_versions').glob('*/missing_report.md') if (p.parent/'run_manifest.json').exists() and read_json(p.parent/'run_manifest.json').get('registry_hash')==selected['hash']]
    return {'registry':selected,'current_hash':current['hash'],'revision':max([v['revision'] for v in versions] or [0]),'reports':reports,
      'versions':[{k:v for k,v in row.items() if k!='registry'} for row in versions], 'read_only':bool(version and version!=current['hash'])}


def save_registry(project,body):
    project=Path(project);view=registry_view(project);current=view['registry']
    if body.get('expected_hash')!=current['hash']:raise ValueError('关注点版本已变化，请刷新后再保存')
    value=deepcopy(body.get('registry'))
    if not isinstance(value,dict) or not isinstance(value.get('definitions'),dict):raise ValueError('无效关注点定义')
    # Technical IDs are stable. Deleting a key retires it, retaining history and
    # safe lookups in previously emitted artifacts; it is no longer applicable.
    for key,old in current['definitions'].items():
        if key not in value['definitions']:value['definitions'][key]={**old,'enabled':False}
    guards={d['guard'] for d in default_registry()['definitions'].values()}
    kinds={'read','display','create','update','delete','process','publish','external_call'}
    for key,d in value['definitions'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_.]{1,119}',key) or d.get('key')!=key:raise ValueError('关注点ID须为稳定的小写英文、数字、点或下划线')
        if not isinstance(d.get('label'),str) or not d['label'].strip() or not isinstance(d.get('description'),str) or not d['description'].strip():raise ValueError('请填写名称和定义')
        if d.get('layer') not in LAYERS or d.get('group') not in GROUPS[d['layer']]:raise ValueError('关注点层级与分类不一致')
        if key in current['definitions'] and d['layer']!=current['definitions'][key]['layer']:raise ValueError('稳定ID的对象层级不能改写；跨层变更请新建关注点并停用旧项')
        prefix={'human':'human.','relation':'service_relation.','shared':'api.data.'}.get(d['layer'])
        if prefix and not key.startswith(prefix):raise ValueError('该层关注点ID应以 '+prefix+' 开头，以保持类型识别稳定')
        if d.get('kind') not in {'check','family'} or d.get('guard') not in guards:raise ValueError('请使用支持的检查条件类型')
        if not isinstance(d.get('operation_kinds'),list) or set(d['operation_kinds'])-kinds:raise ValueError('未知操作类型')
        if d.get('technology') not in {None,'database','llm'} or not isinstance(d.get('parents'),list):raise ValueError('无效技术身份或父关注点')
        if any(not isinstance(p,str) for p in d['parents']):raise ValueError('父关注点必须是有效ID')
        if not isinstance(d.get('failure_family'),str) or not d['failure_family']:d['failure_family']=key
        if 'enabled' in d and type(d['enabled']) is not bool:raise ValueError('启用状态必须为布尔值')
        if any(not value['definitions'].get(p,{}).get('enabled',True) for p in d['parents']) and d.get('enabled',True):raise ValueError('请先调整子关注点，不能停用仍被启用子项继承的父关注点')
    # Rebuild profiles from actual membership, never trust stale client lists.
    profiles=deepcopy(default_registry()['profiles'])
    def clear(v):
        for k,x in v.items():
            if isinstance(x,dict):clear(x)
            else:v[k]=[]
    clear(profiles)
    for key,d in value['definitions'].items():
        if not d.get('enabled',True):continue
        layer=d['layer']
        if layer in {'base','human','relation'}:profiles[layer].append(key)
        elif layer=='functional':profiles['functional'][d['group']].append(key)
        elif layer=='technology':profiles['technology'][d['group']].append(key)
    value['profiles']=profiles;value['version']=current['version'];value['legacy_mapping']=current['legacy_mapping']
    value['hash']=fingerprint({k:v for k,v in value.items() if k!='hash'});validate_registry(value)
    if value['hash']==current['hash']:return registry_view(project)
    history=project/'concern_versions';history.mkdir(exist_ok=True)
    if not list(history.glob('*.json')):write_json(history/(current['hash']+'.json'),{'revision':0,'hash':current['hash'],'at':time.time(),'note':'项目初始定义','registry':current})
    row={'revision':view['revision']+1,'hash':value['hash'],'at':time.time(),'note':str(body.get('note') or '业务编辑关注点'),'registry':value}
    # A restored definition may have the same content hash as an older version;
    # revision filenames preserve both saves without overwriting either record.
    write_json(history/(str(row['revision'])+'-'+value['hash']+'.json'),row)
    write_json(project/'run/registry_override.json',value)
    EventStore(project/'run').append('registry_updated',revision=row['revision'],registry_hash=value['hash'],note=row['note'])
    return registry_view(project)


def pending_id(case,interaction,reason,refs,concern=None,subject=None,channel='positive'):return fingerprint([case,interaction,reason,refs,concern,subject,channel])[:24]


def pending_items(project):
    project=Path(project);root=project/'run';statefile=root/'workflow_tasks.json';graphfile=root/'workflow_graph.json'
    if not statefile.exists():return []
    state=read_json(statefile)['tasks'];active={n['id'] for n in read_json(graphfile)['nodes']} if graphfile.exists() else set(state)
    signature=fingerprint({'version':'pending-review-two-level-v1','tasks':[(k,r.get('status'),r.get('output_hash'),r.get('failure')) for k,r in state.items() if k in active]})
    cache=root/'pending_index.json'
    if cache.exists():
        saved=read_json(cache)
        if saved['signature']==signature:return saved['items']
    stages={'existing-concerns','test-concerns','normal-rules','concern-match','enriched-view','existing-bind','existing-extract','test-ground-truth','test-supplement','fused-ssd'}
    partitioned={k.split('--part-',1)[0] for k in active if '--part-' in k}
    items={}
    def add(key,r,iid,reason,refs,category='待确认',concern=None,branch=None,subject=None):
        if not reason:return
        channel='test_gt' if r['stage'] in {'test-ground-truth','test-supplement','test-concerns'} else 'existing_e' if r['stage'] in {'existing-bind','existing-extract','existing-concerns'} else 'positive'
        queue='rules' if r['stage']=='concern-match' else 'structure' if r['stage'] in {'enriched-view','fused-ssd'} or str(reason).startswith('规则归属核查：') else 'business'
        legacy=pending_id(r['case'],iid,reason,refs,concern,subject,channel)
        identity=legacy if queue=='business' else fingerprint([legacy,queue])[:24]
        item=items.setdefault(identity,{'id':identity,'case':r['case'],'interaction_id':iid,'reason':reason,'source_refs':refs,'category':category,'queue':queue,'source_channel':channel,'concern_key':concern,'object':subject,'branch_id':branch,'origins':[]})
        if identity!=legacy:item['legacy_id']=legacy
        if key not in item['origins']:item['origins'].append(key)
        return item
    for key,r in state.items():
        if key not in active:continue
        failure=r.get('failure') or {}
        if r.get('status')=='awaiting_answer' and failure.get('question'):
            q=failure['question'];reason=q.get('text') or '模型等待补充信息'
            item=add(key,r,'unbound',reason,[],'模型提问');item.update(question=True,queue='technical')
        elif r.get('status') in {'failed','rejected','awaiting_configuration','budget_exhausted'}:
            reason=failure.get('error') or failure.get('failure_category') or (failure.get('transport_failure') or {}).get('failure_category') or '节点执行未完成，请查看原始诊断'
            item=add(key,r,'unbound',str(reason),[],'执行问题');item.update(technical=True,queue='technical')
        if r.get('status')!='passed' or r.get('stage') not in stages or key in partitioned:continue
        v=read_json(root/r['output_file'])['payload']
        for item in v.get('pending',[]):add(key,r,item.get('interaction_id') or 'unbound',item.get('reason') or item.get('basis'),item.get('source_refs',[]),concern=item.get('concern_key'),subject=item.get('object'))
        if r['stage']=='existing-bind':
            for b in v.get('bindings',[]):
                if b['status']=='pending':add(key,r,b.get('interaction_id') or 'unbound',b['basis'],b['source_refs'],'已有异常绑定',branch=b['branch_id'])
        if r['stage'] in {'concern-match','existing-concerns','test-concerns'}:
            for m in v.get('matches',[]):
                if m.get('status')=='pending':add(key,r,m['interaction_id'],m.get('status_reason') or m['basis'],m['source_refs'],'关注点适用条件',m['concern_key'],subject=m['object'])
    result=list(items.values());write_json(cache,{'signature':signature,'items':result});return result


def decisions(project):
    path=Path(project)/'pending_decisions.json'
    return read_json(path) if path.exists() else {'revision':0,'items':{},'history':[]}


def item_decision(saved,item):
    current=saved['items'].get(item['id'])
    if current:return current
    old=saved['items'].get(item.get('legacy_id'))
    # Preserve pre-queue reviews only for the actual originating node; never
    # copy a decision to a different diagnostic which happens to share text.
    return old if old and set(old.get('origins',[]))&set(item['origins']) else None


def pending_view(project,status='unresolved',case=None,offset=0,limit=50,search='',channel=None,queue='business'):
    if status not in {'all','unresolved','anomaly','not_anomaly','needs_info'} or offset<0 or not 1<=limit<=200:raise ValueError('无效待确认项筛选')
    rows=pending_items(project);saved=decisions(project)
    for row in rows:row['decision']=item_decision(saved,row)
    if queue not in {'all','business','rules','structure','technical'}:raise ValueError('无效审核类型')
    queue_counts={q:{'total':sum(r['queue']==q for r in rows),'unresolved':sum(r['queue']==q and not r['decision'] for r in rows)} for q in ('business','structure','rules','technical')}
    cases=sorted({r['case'] for r in rows})
    rows=[r for r in rows if queue=='all' or r['queue']==queue]
    counts={k:sum((r.get('decision') or {}).get('choice','unresolved')==k for r in rows) for k in ('unresolved','anomaly','not_anomaly','needs_info')}
    found=[r for r in rows if (status=='all' or (r.get('decision') or {}).get('choice','unresolved')==status) and (not case or r['case']==case) and (not channel or r['source_channel']==channel) and (not search or search.casefold() in json.dumps(r,ensure_ascii=False).casefold())]
    return {'items':found[offset:offset+limit],'count':len(found),'counts':counts,'queue_counts':queue_counts,'queue':queue,'revision':saved['revision'],'cases':cases}


def decide_pending(project,item_id,body):
    project=Path(project);item=next((i for i in pending_items(project) if i['id']==item_id),None)
    if item is None:raise ValueError('待确认项已变化，请刷新')
    if item.get('question') or item.get('technical'):raise ValueError('请在来源节点处理提问或执行错误，不能把技术问题直接判成异常场景')
    if item['queue']!='business':raise ValueError('这是规则或结构诊断，请在来源节点补充依据或核对模型，不直接判作异常场景')
    saved=decisions(project);previous=item_decision(saved,item)
    if body.get('revision',0)!=(previous or {}).get('revision',0):raise ValueError('审核已变化，请刷新')
    choice=body.get('choice');key=body.get('concern_key')
    if len(str(body.get('note') or ''))>8000:raise ValueError('审核说明最多8000字符')
    if choice not in {'anomaly','not_anomaly','needs_info'}:raise ValueError('请选择是否为异常')
    reg=project_registry(project);definition=reg['definitions'].get(key,{})
    if choice=='anomaly' and (not definition.get('enabled',True) or definition.get('kind')!='check'):raise ValueError('请选择当前启用的具体关注点')
    row={'item_id':item_id,'revision':(previous or {}).get('revision',0)+1,'choice':choice,'concern_key':key if choice=='anomaly' else None,'note':str(body.get('note') or ''),'at':time.time(),'registry_hash':reg['hash'],'origins':item['origins'],'item_snapshot':item}
    saved['items'][item_id]=row;saved['history'].append(row);saved['revision']+=1;write_json(project/'pending_decisions.json',saved)
    # Explicit user review is isolated to each originating node. Do not call a
    # model, alter old artifacts, or copy checker/test answers into generation.
    if choice!='needs_info':
        from .node_conversations import Conversations
        store=Conversations(project/'run');text='业务审核待确认项 '+item_id+'：'+('不算异常，跳过此项' if choice=='not_anomaly' else '确认为异常，归入 '+key+'（'+definition['label']+'）')+'。原问题：'+item['reason'][:12000]+'。审核说明：'+row['note']+'。保留其他任务事实边界，不补造未知约束。'
        for origin in item['origins']:store.append(origin,'guidance',text,{'pending_item_id':item_id,'review_revision':row['revision'],'channel_isolated':True})
    EventStore(project/'run').append('pending_reviewed',item_id=item_id,choice=choice,concern_key=row['concern_key'],revision=row['revision'])
    return row
