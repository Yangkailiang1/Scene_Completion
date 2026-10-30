"""Explicit human approvals, CAS validation and conservative DAG impact."""
from copy import deepcopy
from pathlib import Path
import time
from .storage import read_json,write_json,fingerprint
from . import quality_diagnostics as q
from .scheduler import run_lock
from .configuration_lock import configuration_lock

CONCERN_FIELDS={'label','description','parents','enabled','operation_kinds','technology','group'}
PATTERN_FIELDS={'label','preconditions','trigger_template','required_evidence','selector','risk_level','enabled','concern_keys'}
RANK_FIELDS={'top_k','risk_weight','history_weight','overrides'}

def impact(project,did,body):
 value=q.report(project,did);snap=read_json(q.store(project)/did/'snapshot.json')
 if body.get('snapshot_hash')!=value['snapshot_hash']:raise ValueError('必须确认诊断快照snapshot_hash')
 if q.freeze(project,value['test_set'],value['case_id'])['hash']!=value['snapshot_hash']:raise ValueError('产物、定义、配置、测试或执行版本已变化，请重新诊断')
 approvals=body.get('approvals',[])
 if not isinstance(approvals,list) or not approvals:raise ValueError('请选择需要应用的建议')
 if len(set(approvals))!=len(approvals):raise ValueError('建议ID重复')
 if not str(body.get('reviewer','')).strip():raise ValueError('请填写确认人reviewer')
 byid={p['id']:p for p in value['proposals']}
 if any(k not in byid or not byid[k]['applicable'] for k in approvals):raise ValueError('仅可应用有独立正向/框架依据的配置建议；研发及材料问题需要另行处理')
 registry=deepcopy(snap['registry']);settings=deepcopy(snap['settings']);changes=[];kinds=set()
 for pid in approvals:
  p=byid[pid];kind=p['kind'];target=p.get('target');patch=p.get('patch')
  if not isinstance(patch,dict) or not patch:raise ValueError('建议需要非空结构化patch')
  if kind=='concern':
   if target not in registry.get('definitions',{}):
    allowed=CONCERN_FIELDS|{'key','kind','layer','guard','failure_family','required_evidence'}
    if set(patch)-allowed or patch.get('key')!=target:raise ValueError('新增关注点须提交完整稳定ID及受支持定义')
    before=None;registry['definitions'][target]=deepcopy(patch);after=registry['definitions'][target]
   else:
    if set(patch)-CONCERN_FIELDS:raise ValueError('不支持的关注点修改字段；跨层变更请新建定义并停用旧项')
    before=deepcopy(registry['definitions'][target]);registry['definitions'][target].update(patch);after=registry['definitions'][target]
  elif kind=='pattern':
   if set(patch)-PATTERN_FIELDS:raise ValueError('不支持的模式修改字段')
   row=next((x for x in settings.get('library',{}).get('patterns',[]) if x['id']==target),None)
   if row is None:raise ValueError('模式不存在')
   before=deepcopy(row);row.update(patch);after=row
  elif kind=='recommendation':
   if set(patch)-RANK_FIELDS:raise ValueError('推荐建议只允许K、排序权重及项目风险配置')
   before={k:deepcopy(settings.get(k)) for k in patch};settings.update(patch);after={k:settings[k] for k in patch}
  else:raise ValueError('该建议不能自动应用')
  if kind=='recommendation' and 'overrides' in patch:kinds.add('risk')
  changes.append({'proposal_id':pid,'kind':kind,'target':target,'before':before,'after':deepcopy(after)});kinds.add(kind)
 from .project_review import save_registry
 from .pattern_settings import save_settings
 from .concern_registry import registry_scope
 checked_registry=save_registry(project,{'expected_hash':snap['registry']['hash'],'registry':registry,'dry_run':True})['registry'] if 'concern' in kinds else registry
 if kinds&{'pattern','recommendation'}:
  from .scenario_patterns import normalize_settings
  with registry_scope(checked_registry):settings=normalize_settings(settings)
 nodes=q.load(Path(project)/'run/workflow_graph.json',{}).get('nodes',[])
 roots=set()
 for n in nodes:
  stage=n.get('stage');key=n['id']
  if 'concern' in kinds and stage in {'normal-rules','concern-match','existing-concerns','test-concerns'}:roots.add(key)
  if kinds&{'pattern','risk'} and stage in {'pattern-applicability','existing-extract','test-ground-truth','test-additional-truth'}:roots.add(key)
  if 'recommendation' in kinds and stage=='gap-recommend':roots.add(key)
 affected=set(roots)
 while True:
  extra={n['id'] for n in nodes if set(n.get('deps',[]))&affected}-affected
  if not extra:break
  affected|=extra
 cases=sorted({n.get('case') for n in nodes if n['id'] in affected and n.get('case') not in {'shared',None}})
 return {'diagnosis_id':did,'snapshot_hash':value['snapshot_hash'],'changes':changes,'roots':sorted(roots),'affected':sorted(affected),'case_ids':cases,
  'scope_note':'定义可能适用于其他交互；不能证明局部时覆盖当前DAG全部相关通道。组成、API及SSD保持校验复用。',
  'ranking_only':kinds=={'recommendation'},'registry':checked_registry,'settings':settings,'reviewer':body['reviewer'],'expected_registry':snap['registry'].get('hash'),'expected_pattern':snap['versions']['pattern']}

def apply(service,rid,did,body):
 project=service.run_dir(rid)
 if service.review_only:raise ValueError('业务审核模式只能查看已保存诊断')
 from .worker_runtime import read_job
 with run_lock(project/'dispatch'),configuration_lock(project):
  if rid in service.active or read_job(project).get('status')=='running':raise ValueError('项目执行中，不能应用建议')
  value=q.report(project,did)
  if value.get('applied'):raise ValueError('诊断建议已应用；请使用保存的影响范围或新诊断，不重复修改')
  plan=impact(project,did,body)
  public={k:v for k,v in plan.items() if k not in {'registry','settings'}}
  if body.get('dry_run'):return {'saved':False,**public}
  folder=q.store(project)/did
  before={str(p.relative_to(project)):p.read_text() if p.exists() else None for p in [project/'run/registry_override.json',project/'pattern-settings.json']}
  write_json(folder/'application.json',{'status':'applying','plan':public,'before':before,'intended':{'registry':plan['registry'].get('hash'),'patterns':plan['settings'].get('hash')},'at':time.time()})
  try:
   from .project_review import save_registry
   from .pattern_settings import save_settings,settings
   kinds={c['kind'] for c in plan['changes']}
   if 'concern' in kinds:save_registry(project,{'expected_hash':plan['expected_registry'],'registry':plan['registry'],'note':'人工确认指标诊断 '+did})
   if kinds&{'pattern','recommendation'}:save_settings(project,{'expected_version':settings(project)['version'],'settings':plan['settings']})
   application={'status':'applied','plan':public,'at':time.time(),'reviewer':body['reviewer'],'rerun_requested':bool(body.get('rerun'))}
   write_json(folder/'application.json',application);value['applied']=application;q.save(project,value)
  except Exception:
   # Atomic pointers rolled back; newly appended immutable versions remain audited.
   for path,content in before.items():
    p=project/path
    if content is None:p.unlink(missing_ok=True)
    else:write_json(p,__import__('json').loads(content))
   write_json(folder/'application.json',{'status':'rolled_back','at':time.time(),'plan':public});raise
 # Launch through the standard execution API only after releasing its dispatch lock.
 if body.get('rerun'):
  if not plan['case_ids']:return {'saved':True,**public,'rerun':{'status':'无可运行影响节点'}}
  try:result=service.start(rid,{'case_ids':plan['case_ids']})
  except Exception as exc:result={'status':'未启动，修改已保存','error':str(exc)}
  return {'saved':True,**public,'rerun':result}
 return {'saved':True,**public}


def compare_saved(project,did):
    value=q.report(project,did);current=q.freeze(project,value['test_set'],value['case_id'])
    changed=[k for k in ('test_set','test_source','registry','matching','business') if value['versions'].get(k)!=current['versions'].get(k)]
    before=value['summary'];after=current['summary'];rows=[]
    for old in before.get('cases',[]):
        new=next((r for r in after.get('cases',[]) if r['id']==old['id']),{})
        for key,a in old.get('metrics',{}).items():
            b=new.get('metrics',{}).get(key,{})
            rows.append({'case_id':old['id'],'metric':key,'before':a,'after':b,'denominator_changed':a.get('denominator')!=b.get('denominator'),
                         'delta':b['value']-a['value'] if isinstance(b.get('value'),(int,float)) and isinstance(a.get('value'),(int,float)) else None})
    result={'before':before,'after':after,'changes':rows,'versions_before':value['versions'],'versions_after':current['versions'],
            'basis_change':bool(changed),'basis_changed_fields':changed,'usage_before':value.get('usage_before'),'usage_after':current.get('usage'),
            'note':'来源、分类或粒度引起的分母变化单列为口径变化，不表示模型质量提升；用量为保存的累计请求统计，诊断调用已排除。'}
    if value.get('applied') and current['versions'].get('execution')!=value['versions'].get('execution') and current['summary'].get('complete'):
        value['after_comparison']=result;q.save(project,value)
    return result


def recover_application(project,did):
    """Recover pointer transaction only if no newer configuration would be overwritten."""
    folder=q.store(project)/did;p=folder/'application.json'
    if not p.exists():return
    with run_lock(Path(project)/'dispatch'),configuration_lock(project):
        record=read_json(p)
        if record['status']!='applying':return
        intended=record.get('intended',{})
        for rel,text in record['before'].items():
            current=q.load(Path(project)/rel,{})
            old=__import__('json').loads(text) if text else {}
            expected=intended.get('registry' if 'registry_override' in rel else 'patterns')
            if current!=old and (current.get('hash') if 'registry_override' in rel else current.get('version'))!=expected:
                record.update(status='conflict',error='检测到新的配置；不覆盖，请人工核查');write_json(p,record);return
        for rel,text in record['before'].items():
            path=Path(project)/rel
            if text is None:path.unlink(missing_ok=True)
            else:write_json(path,__import__('json').loads(text))
        record.update(status='rolled_back_after_restart',at=time.time());write_json(p,record)
