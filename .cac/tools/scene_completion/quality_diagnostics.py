"""Frozen, read-only metric loss accounting. Never a business-node input."""
from pathlib import Path
from copy import deepcopy
import time
from .storage import read_json,write_json,fingerprint
from .result_views import ResultView
VERSION='quality-diagnostics-v1'
CAUSES={
 'recognition':'关注点识别或适用条件', 'localization':'交互、方向或对象定位',
 'taxonomy':'分类冲突、定义重叠或体系缺口','patterns':'异常模式或展开粒度',
 'truth':'GT类型、重复或测试覆盖','matching':'场景匹配或宽泛分支覆盖',
 'ranking':'推荐候选、排序或风险配置','incomplete':'任务、版本或材料未就绪',
 'unverified':'GT未验证','unknown':'待查明'}
METRICS={
 'missing_exception_miss_rate':('关注点缺失异常漏报率','↓','(1−|M_c∩(GT_c−E_c)|/|GT_c−E_c|)×100%'),
 'generation_validity':('关注点生成有效率','↑','|G_c∩GT_c|/|G_c|×100%'),
 'recommendation_adoption':('推荐采纳率（GT命中）','↑','|Q∩GT|/|Q|×100%'),
 'recommendation_false_positive':('推荐误报率','↓','|Q−(Q∩GT)|/|GT|×100%；可能超过100%'),
 'critical_missing_recall':('关键缺失召回率','↑','|Q∩关键(GT−E)|/|关键(GT−E)|×100%'),
 'human_adoption':('实际人工采纳率','↑','采纳数/(采纳数＋明确无需纳入数)×100%'),
 'Acc':('抽取准确率','↑','H/N×100%')}

def load(path,default=None):return read_json(path) if Path(path).exists() else deepcopy(default)
def store(project):return Path(project)/'quality-diagnostics'
def report(project,did):
 if len(did)!=24 or any(c not in 'abcdef0123456789' for c in did):raise ValueError('无效诊断ID')
 p=store(project)/did/'report.json'
 if not p.exists():raise ValueError('诊断不存在')
 return read_json(p)
def save(project,value):
 write_json(store(project)/value['id']/'report.json',value)
 write_json(store(project)/value['id']/'metadata.json',{k:value.get(k) for k in ('id','created_at','status','test_set','case_id','snapshot_hash','coverage','error','automatic','applied')})
def listing(project):
 return sorted([{k:v.get(k) for k in ('id','created_at','status','test_set','case_id','snapshot_hash','coverage','error','automatic','applied','after_comparison')} for p in store(project).glob('*/report.json') for v in [load(p.parent/'metadata.json') or read_json(p)]],key=lambda r:r['created_at'],reverse=True)

def freeze(project,test_set=None,case_id=None):
 """Capture authoritative active outputs, not orphan/historical tasks or model contexts."""
 view=ResultView(project)
 test_set=test_set or ('expanded' if view.manifest.get('supplement_tests') else 'original')
 if test_set not in {'original','expanded','business'}:raise ValueError('未知测试来源')
 cases=view.cases()
 if case_id and case_id not in {c['id'] for c in cases}:raise ValueError('未知用例')
 cases=[c for c in cases if not case_id or c['id']==case_id]
 meta=load(Path(project)/'project.json',{})
 source_hashes={s['path']:fingerprint((Path(project)/s['path']).read_bytes().hex()) for values in meta.get('sources',{}).values() for s in values if (Path(project)/s['path']).is_file()}
 outputs={k:view.payload(k) for k,r in view.state.items() if r.get('case')=='shared' or r.get('case') in {c['id'] for c in cases}}
 summary=view.metrics(test_set);summary['cases']=[r for r in summary['cases'] if r['id'] in {c['id'] for c in cases}]
 if case_id:
  from .result_alignment import aggregate_metrics
  from .recommendation import aggregate_comparison
  summary['metrics']=aggregate_metrics(summary['cases']);summary['recommendation_comparison']=aggregate_comparison([r.get('recommendation_comparison') for r in summary['cases']])
 if test_set=='business':
  from .business_truth import snapshot
  for c in cases:outputs[c['id']+':exception-evaluation']=snapshot(project,c['id'])['evaluation']
 registry=load(Path(project)/'run/registry_override.json',{})
 pointer=load(Path(project)/'pattern-settings.json',{})
 settings=load(Path(project)/'pattern-versions'/(str(pointer.get('version'))+'.json'),{})
 pinned=load(Path(project)/'run/registry_used'/(str(view.manifest.get('registry_hash'))+'.json'),{})
 versions={'diagnostic':VERSION,'execution':summary.get('execution_id'),'test_set':test_set,'test_source':summary.get('test_source_version'),
  'matching':view.manifest.get('matching_version'),'rules':view.manifest.get('ruleset_version'),'registry':view.manifest.get('registry_hash'),
  'current_registry':registry.get('hash'),'pattern':pointer.get('version'),'source_hashes':source_hashes,
  'output_hashes':{k:fingerprint(v) for k,v in outputs.items()},'business':summary.get('business_versions'),'human_review':fingerprint(load(Path(project)/'recommendation-history.json',{}))}
 return {'versions':versions,'hash':fingerprint(versions),'summary':summary,'outputs':outputs,'cases':cases,'registry':registry,'pinned_registry':pinned,'settings':settings,'scope':case_id,'nodes':{k:{'case':r.get('case'),'stage':r.get('stage')} for k,r in view.state.items()},'usage':usage_snapshot(project)}

def selected_evaluation(snap,cid):
 value=snap['outputs'].get(cid+':exception-evaluation',{})
 return value.get('original_evaluation',value) if snap['versions']['test_set']=='original' else value

def build(project,snap,automatic=False):
 did=fingerprint([snap['hash'],VERSION,snap['scope']])[:24]
 old=store(project)/did/'report.json'
 if old.exists():return read_json(old)
 losses=[];cards=[];excluded={};integrity=[]
 if snap['summary'].get('test_source_changed'):integrity.append({'metric':'all','reason':'当前测试来源已变化，正式评测尚未重算；诊断仅解释冻结旧结果'})
 if snap['versions'].get('registry')!=snap['versions'].get('current_registry'):integrity.append({'metric':'all','reason':'当前关注点版本与本轮冻结版本不同；不得混算'})
 def loss(cid,metric,anchor,cells,reason='unknown',certainty='待查明',note='',scope='current'):
  lid=fingerprint([cid,metric,anchor,scope])[:24]
  if any(x['id']==lid for x in losses):return
  losses.append({'id':lid,'case_id':cid,'metric':metric,'scope':scope,'anchor':deepcopy(anchor),'cells':deepcopy(cells),
    'primary_cause':reason,'secondary_causes':[],'certainty':certainty,'reason':note or '工具已定位损失；需结合独立证据判断原因',
    'nodes':([scope] if metric=='Acc' else [cid+':'+s for s in (('gap-recommend','exception-evaluation') if metric in {'selection_omission','human_adoption'} else ('concern-match','existing-concerns','test-concerns','concern-evaluation') if metric in {'missing_exception_miss_rate','generation_validity'} else ('gap-recommend','test-ground-truth','GT_G','exception-evaluation'))]),
    'evidence':list({fingerprint(r):r for values in cells.values() for v in values for r in v.get('source_refs',[])}.values()),'reviewed_by':'tool' if certainty=='已核实' else None})
 def card(cid,key,value,scope='current',unit=None):
  name,direction,formula=METRICS.get(key,(key,'','使用已保存评测公式'))
  if scope=='baseline':formula=formula.replace('Q','M');name='推荐前 '+name
  n,d=value.get('numerator'),value.get('denominator')
  cards.append({'id':f'{cid}:{scope}:{key}','case_id':cid,'metric':key,'scope':scope,'label':name,'direction':direction,'formula':formula,
   'value':value.get('value'),'numerator':n,'denominator':d,'status':value.get('status','未评测'),'unit':unit or value.get('unit'),
   'expected_loss_count':(n if direction=='↓' else max(0,d-n)) if isinstance(n,(int,float)) and isinstance(d,(int,float)) else None})
 for case in snap['cases']:
  cid=case['id'];ev=selected_evaluation(snap,cid);co=ev.get('concern_level') or snap['outputs'].get(cid+':concern-evaluation',{})
  if snap['versions']['test_set']=='original':co=co.get('original_evaluation',co)
  excluded[cid]=co.get('excluded',{})
  if co and 'GT_c' in co:
   sets={k:{x['binding_id']:x for x in co.get(k+'_c',[]) if x.get('scenario_type','exception')=='exception'} for k in ('G','E','GT','M')}
   for key in ('missing_exception_miss_rate','generation_validity'):card(cid,key,co.get('metrics',{}).get(key,{}),unit='关注点绑定')
   for bid in (sets['GT'].keys()-sets['E'].keys())-sets['M'].keys():
    cells={k:[v[bid]] if bid in v else [] for k,v in sets.items() if k!='M'}
    loss(cid,'missing_exception_miss_rate',sets['GT'][bid],cells)
   for bid in sets['G'].keys()-sets['GT'].keys():
    loss(cid,'generation_validity',sets['G'][bid],{k:[v[bid]] if bid in v else [] for k,v in sets.items() if k!='M'},'unverified','已核实','当前冻结GT没有完整对应绑定；不能据此认定生成错误')
  else:
   for key in ('missing_exception_miss_rate','generation_validity'):card(cid,key,{'status':'版本不一致，待重算' if ev else '未评测'},unit='关注点绑定')
  # Scene hits are the persisted one-to-one decisions, never fresh fuzzy matching.
  channels={k:{s['id']:s for s in ev.get(k,[]) if s.get('scenario_type','exception')=='exception'} for k in ('G','E','GT','M')}
  rec=snap['outputs'].get(cid+':gap-recommend',{})
  channels['Q']={s['id']:s for s in rec.get('Q',[]) if s.get('scenario_type','exception')=='exception'}
  if not ev:continue
  pairs=ev.get('full_matches',{});matched_g={p['generated_scenario_id'] for p in pairs.get('GT_G',[])}
  matched_q={p['generated_scenario_id'] for p in pairs.get('GT_Q',[])}
  from .recommendation import comparison_for_view
  comp=comparison_for_view(ev,rec) or {}
  for scope,channel in [('baseline','M'),('recommended','Q')]:
   values=comp.get(scope,{})
   for key in ('recommendation_adoption','recommendation_false_positive'):
    card(cid,key,values.get('metrics',{}).get(key,{'status':values.get('status','未评测')}),scope,'独立异常场景')
   hits=matched_g if channel=='M' else matched_q
   for sid in channels[channel].keys()-hits:
    anchor=channels[channel][sid];cells={'G':[anchor],'E':[],'GT':[]}
    for key in ('recommendation_adoption','recommendation_false_positive'):
     loss(cid,key,anchor,cells,'unverified','已核实','未被当前GT完整验证；需核对生成依据、测试覆盖及已保存匹配',scope)
  qids=set(channels['Q']);mids=set(channels['M'])
  for pair in pairs.get('GT_G',[]):
   gid=pair['generated_scenario_id'];tid=pair['checker_scenario_id']
   if gid in mids-qids and gid in channels['G']:
    loss(cid,'selection_omission',channels['G'][gid],{'G':[channels['G'][gid]],'E':[],'GT':[channels['GT'][tid]] if tid in channels['GT'] else []},'ranking','已核实','M中已验证项未进入Q；需结合冻结排名、K与关键项保底规则核查')
  if 'critical_missing_recall' in ev.get('metrics',{}):
   card(cid,'critical_missing_recall',ev['metrics']['critical_missing_recall'],unit='关键独立异常场景')
   covered={p['checker_scenario_id'] for p in pairs.get('GT_E',[])};qtruth={p['checker_scenario_id'] for p in pairs.get('GT_Q',[])}
   for tid,s in channels['GT'].items():
    if s.get('risk',{}).get('level')=='critical' and tid not in covered|qtruth:loss(cid,'critical_missing_recall',s,{'GT':[s],'E':[],'G':[]})
  # Frozen actual human review counts, never automatic GT approval.
  from .pattern_settings import adoption
  human=adoption(project,rec)
  card(cid,'human_adoption',human,unit='人工审核推荐项')
  from .pattern_settings import history
  latest={}
  for row in history(project)['feedback']:
   if row.get('run_id')==rec.get('run_id') and row.get('scenario_id') in channels['Q']:latest[row['scenario_id']]=row
  for sid,row in latest.items():
   if row.get('decision')=='not_needed':loss(cid,'human_adoption',channels['Q'][sid],{'G':[channels['Q'][sid]],'E':[],'GT':[]},'ranking','疑似','人工明确无需纳入；具体原因需结合审核说明：'+str(row.get('note','')))

 for key,payload in snap['outputs'].items():
  if 'Acc' in payload:
   cid=snap.get('nodes',{}).get(key,{}).get('case') or (key.split(':')[0] if ':' in key else 'shared')
   card(cid,'Acc',{'value':payload['Acc'],'numerator':payload.get('H'),'denominator':payload.get('N'),'status':payload.get('status','已评测')},key,payload.get('minimum_unit'))
   # Extraction loss IDs require saved unit adjudications, never infer IDs from H/N.
   if 'unmatched_truth_ids' in payload:
    truth={u['id']:u for u in payload.get('truth_units',[])}
    for uid in payload['unmatched_truth_ids']:
     loss(cid,'Acc',truth.get(uid,{'id':uid}),{'GT':[truth.get(uid,{'id':uid})],'G':[],'E':[]},scope=key)
   elif payload.get('N') and payload.get('H',0)<payload['N']:integrity.append({'metric':'Acc','node':key,'status':'待查明','reason':'保存了H/N；需展开该节点人工GT及单元对应记录，未伪造未命中单元'})
 for cardrow in cards:
  rows=[l for l in losses if l['case_id']==cardrow['case_id'] and l['metric']==cardrow['metric'] and l['scope']==cardrow['scope']]
  cardrow['loss_count']=len(rows)
  if cardrow['expected_loss_count'] is not None and cardrow['expected_loss_count']!=len(rows):
   integrity.append({'metric':cardrow['id'],'status':'待查明','reason':'正式计数与可展开清单不一致；可能缺少对应记录或版本不同','saved_loss_count':cardrow['expected_loss_count'],'enumerated':len(rows)})
 value={'id':did,'version':VERSION,'snapshot_hash':snap['hash'],'versions':snap['versions'],'created_at':time.time(),'status':'queued','automatic':automatic,
  'case_id':snap['scope'],'test_set':snap['versions']['test_set'],'scope_complete':snap['summary'].get('complete',False),'summary':snap['summary'],'usage_before':snap['usage'],
  'cards':cards,'losses':losses,'excluded':excluded,'integrity':integrity,'proposals':[],'batches':{},'coverage':{},'token_limit':100000}
 refresh(value);write_json(store(project)/did/'snapshot.json',snap);save(project,value);return value

def refresh(value):
 losses=value['losses'];verified=sum(l['certainty']=='已核实' and l['primary_cause']!='unverified' for l in losses)
 value['coverage']={'enumerated':len(losses),'evidence_reviewed':sum(l.get('reviewed_by')=='model' for l in losses),'verified_causes':verified,'gt_unverified':sum(l['primary_cause']=='unverified' for l in losses),'unresolved':sum(l['certainty'] in {'待确认','待查明'} for l in losses)}
 for c in value['cards']:
  rows=[l for l in losses if l['case_id']==c['case_id'] and l['metric']==c['metric'] and l['scope']==c['scope']]
  c['causes']={k:sum(l['primary_cause']==k for l in rows) for k in CAUSES if any(l['primary_cause']==k for l in rows)}

def markdown(value):
 lines=['# 指标诊断 '+value['id'],'','状态：'+value['status'],'测试来源：'+value['test_set'],'快照：'+value['snapshot_hash'],'','诊断不改变正式计分；GT未验证不表示生成错误。','', '|用例|指标|方向|分子/分母|值|状态|','|---|---|---|---|---|---|']
 for c in value['cards']:lines.append(f"|{c['case_id']}|{c['scope']} {c['label']}|{c['direction']}|{c['numerator']}/{c['denominator']}|{c['value']}|{c['status']}|")
 for l in value['losses']:lines+=['', '## '+l['id']+' / '+l['case_id'],l['metric']+'：'+CAUSES[l['primary_cause']]+'（'+l['certainty']+'）',l['reason'], '定位：'+str(l['anchor'])]
 for p in value['proposals']:lines+=['','## 建议 '+p['id'],str(p)]
 return '\n'.join(lines)


def usage_snapshot(project):
    """Saved request usage only. Unknown charge stays unknown, never inferred as 0."""
    import sqlite3,json
    p=Path(project)/'run/execution_events.sqlite3'
    if not p.exists():return {'status':'未记录','reported_tokens':None,'request_seconds':None}
    total=0;seconds=0.;unknown=0;starts={};count=0
    with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as db:
        for raw, in db.execute("SELECT payload FROM events WHERE kind IN ('request_started','request_finished','request_failed') ORDER BY id"):
            e=json.loads(raw);d=e.get('data',{});key=d.get('model_call_id') or d.get('task_key')
            if str(d.get('task_key','')).startswith('__quality__'):continue
            if e['kind']=='request_started':starts[key]=e.get('at',0);continue
            count+=1;usage=d.get('usage') or {};t=usage.get('total_tokens')
            if isinstance(t,int):total+=t
            else:unknown+=1
            if key in starts:seconds+=max(0,e.get('at',0)-starts.pop(key))
    return {'status':'已保存请求统计','reported_tokens':total,'unknown_usage_requests':unknown,'requests':count,'request_seconds':seconds,'actual_cost':None,'cost_status':'未知；未配置实际扣费接口','basis':'历史累计，请求耗时非并行墙钟时间'}


def compact_report(value,case_id=None,metric=None,offset=0,limit=100):
    if offset<0 or not 1<=limit<=200:raise ValueError('分页范围无效')
    result=deepcopy({k:v for k,v in value.items() if k not in {'losses','excluded','versions','summary','batches','after_comparison'}})
    result['versions']={k:v for k,v in value['versions'].items() if k not in {'source_hashes','output_hashes'}}
    result['summary']={k:v for k,v in value['summary'].items() if k in {'metrics','complete','test_set','truth_source'}}
    scoped=[l for l in value['losses'] if not case_id or l['case_id']==case_id]
    ids={l['id'] for l in scoped}
    filtered=[l for l in scoped if not metric or f"{l['case_id']}:{l['scope']}:{l['metric']}"==metric]
    result['cards']=[c for c in value['cards'] if not case_id or c['case_id'] in {case_id,'shared'}]
    result['proposals']=[p for p in value['proposals'] if not case_id or ids&set(p.get('loss_ids',[]))]
    result['excluded']={k:v for k,v in value['excluded'].items() if not case_id or k==case_id}
    result['losses']=deepcopy(filtered[offset:offset+limit])
    fields={'id','binding_id','interaction_id','direction','target','object','field','concern_key','cause','basis','concrete_rule','status'}
    for loss in result['losses']:
        loss['anchor']={k:v for k,v in loss['anchor'].items() if k in fields}
        loss['cells']={k:[{a:b for a,b in s.items() if a in fields} for s in values] for k,values in loss['cells'].items()}
    result['pagination']={'offset':offset,'limit':limit,'total':len(filtered)}
    return result
