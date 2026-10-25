"""Project-owned snapshots, imports and business feedback; never an automatic GT feed."""
from pathlib import Path
from threading import RLock
from copy import deepcopy
import time
from functools import wraps
from .concern_registry import registry_scope,default_registry
from .storage import read_json,write_json,fingerprint
from .scenario_patterns import normalize_settings,VERSION
_LOCK=RLock()


def project_scoped(fn):
    @wraps(fn)
    def scoped(project,*args,**kwargs):
        from .project_review import project_registry
        snapshot=project_registry(project);file=Path(project)/'run/registry_used'/(snapshot['hash']+'.json')
        if not file.exists():write_json(file,snapshot)
        with registry_scope(snapshot):return fn(project,*args,**kwargs)
    return scoped

@project_scoped
def settings(project,version=None):
    root=Path(project);pointer=root/'pattern-settings.json'
    with _LOCK:
        if not pointer.exists():
            v=normalize_settings();initial=v['hash'];write_json(root/'pattern-versions'/(initial+'.json'),v);write_json(pointer,{'version':initial,'history':[{'version':initial,'at':time.time()}]})
        index=read_json(pointer);selected=version or index['version'];f=root/'pattern-versions'/(selected+'.json')
        if not f.exists() or selected not in {h['version'] for h in index['history']}:raise ValueError('未知模式设置版本')
        raw=read_json(f)
        if version:
            registry_file=root/'run/registry_used'/(str(raw.get('concern_registry_hash'))+'.json')
            pinned=read_json(registry_file) if registry_file.exists() else default_registry()
            with registry_scope(pinned):value=normalize_settings(raw)
            if 'concern_registry_hash' not in raw:value=deepcopy(raw)
        else:value=normalize_settings(raw)
        if version is None and value['hash']!=selected:
            selected=value['hash'];write_json(root/'pattern-versions'/(selected+'.json'),value)
            index['version']=selected;index['history'].append({'version':selected,'at':time.time(),'note':'模式结构元数据升级，旧快照保留'});write_json(pointer,index)
        return {'version':selected,'history':index['history'],'settings':value}

@project_scoped
def save_settings(project,body):
    with _LOCK:
        old=settings(project)
        if body.get('expected_version')!=old['version']:raise ValueError('模式设置已更新，请刷新')
        v=normalize_settings(body['settings']);version=v['hash'];root=Path(project);index=read_json(root/'pattern-settings.json')
        if version!=old['version']:
            write_json(root/'pattern-versions'/(version+'.json'),v);index['history'].append({'version':version,'at':time.time()});index['version']=version;write_json(root/'pattern-settings.json',index)
        return settings(project)

def history(project):
    f=Path(project)/'recommendation-history.json';return read_json(f) if f.exists() else {'revision':0,'items':[],'feedback':[]}

@project_scoped
def import_history(project,body):
    with _LOCK:
        old=history(project)
        if body.get('revision')!=old['revision']:raise ValueError('历史记录已变化，请刷新')
        known={p['id']:p for p in settings(project)['settings']['library']['patterns']};seen={r['id'] for r in old['items']}
        rows=body.get('items',[])
        if not isinstance(rows,list) or len(rows)>5000:raise ValueError('一次最多导入5000条已审核记录')
        for r in rows:
            required={'id','pattern_id','context','human_reviewed','decision','source_channel','case_id','run_id','reviewed_at','source'}
            if not required<=set(r) or r['id'] in seen or r['pattern_id'] not in known:raise ValueError('历史缺字段、ID重复或模式未知')
            if r['human_reviewed'] is not True or r['source_channel'] not in {'business_review','business_adoption'} or r['decision'] not in {'adopt','not_needed'}:raise ValueError('仅导入已人工审核的业务采纳/明确无需纳入记录；禁止GT或未审核机器结果')
            if not isinstance(r['context'],dict) or not r['source'] or not isinstance(r['reviewed_at'],(int,float)):raise ValueError('历史缺少上下文、审核时间或来源')
            for feature in ('functional_types','technologies'):
                if feature in r['context'] and (not isinstance(r['context'][feature],list) or any(not isinstance(x,str) for x in r['context'][feature])):raise ValueError('历史功能/技术特性必须为文本列表')
            for feature in ('actual_operation','boundary','direction','timeliness'):
                if r['context'].get(feature) is not None and not isinstance(r['context'][feature],str):raise ValueError('历史特征格式无效')
            seen.add(r['id'])
        for row in rows:
            if row.get('pattern_hash')!=known[row['pattern_id']]['definition_hash']:raise ValueError('历史模式定义与当前不同，请重新审核并记录pattern_hash')
            if row.get('library_version')!=VERSION:raise ValueError('已审核历史需要与当前模式库版本一致；旧版本先重新审核')
        old['items']+=deepcopy(rows);old['revision']+=1;write_json(Path(project)/'recommendation-history.json',old);return old

def feedback(project,body,result):
    with _LOCK:
        old=history(project)
        if body.get('revision')!=old['revision']:raise ValueError('审核记录已变化，请刷新')
        if body.get('settings_hash')!=result.get('settings_hash'):raise ValueError('推荐版本已变化，请刷新')
        choice=body.get('choice')
        if choice not in {'adopt','not_needed','already_covered','defer','not_applicable'}:raise ValueError('请选择有效审核结论')
        item=next((r for r in result['ranked'] if r['scenario_id']==body.get('scenario_id')),None)
        if item is None:raise ValueError('推荐场景已变化')
        row={'id':fingerprint([body,time.time_ns()])[:24],'scenario_id':item['scenario_id'],'pattern_id':item['pattern_id'],'context':item['scenario']['scenario_context'],'decision':choice,'human_reviewed':True,'source_channel':'business_adoption','case_id':result['case_id'],'run_id':result['run_id'],'reviewed_at':time.time(),'pattern_hash':item['scenario'].get('pattern_versions',{}).get(item['pattern_id']),'library_version':result.get('library_version'),'source':'网页业务审核','note':str(body.get('note',''))[:8000]}
        old['feedback'].append(row)
        # Latest review replaces prior label, no repeated exposure inflation.
        old['items']=[r for r in old['items'] if (r.get('scenario_id'),r.get('run_id'))!=(row['scenario_id'],row['run_id'])]
        if choice in {'adopt','not_needed'}:old['items'].append(row)
        old['revision']+=1;write_json(Path(project)/'recommendation-history.json',old);return old

def review_candidate(project,body,matrix):
    current=settings(project)
    if current['version']!=matrix.get('settings_hash'):raise ValueError('候选使用旧设置，继续运行更新候选后再审核')
    if current['version']!=body.get('expected_version'):raise ValueError('设置已变化，请刷新')
    item=next((r for r in matrix['instances'] if r['id']==body.get('candidate_id')),None)
    if item is None or item['status']!='pending':raise ValueError('只审核当前待确认候选')
    choice=body.get('choice');note=str(body.get('note','')).strip();condition=str(body.get('positive_condition','')).strip()
    if choice not in {'confirm','reject','needs_info'} or not note:raise ValueError('需要审核结论及说明')
    if choice=='confirm' and not condition:raise ValueError('确认适用必须补充明确的正常业务规则')
    v=current['settings'];row={'choice':choice,'note':note,'positive_condition':condition,'at':time.time()};row['policy_hash']=fingerprint(row)[:24];v['reviews'][item['id']]=row
    return save_settings(project,{'expected_version':current['version'],'settings':v})


def adoption(project,result):
    ids={s['id'] for s in result.get('Q',[])};latest={}
    for r in history(project)['feedback']:
        if r['run_id']==result.get('run_id') and r['scenario_id'] in ids:latest[r['scenario_id']]=r
    labels=[r for r in latest.values() if r['decision'] in {'adopt','not_needed'}]
    n=sum(r['decision']=='adopt' for r in labels);d=len(labels)
    return {'value':100*n/d if d else None,'numerator':n,'denominator':d,'reviewed':len(latest),'total_recommended':len(ids),'status':'已审核明确决策' if d else '待审核','note':'人工采纳率，分母仅采纳/明确无需；暂缓、已覆盖及未审核不作负反馈'}
