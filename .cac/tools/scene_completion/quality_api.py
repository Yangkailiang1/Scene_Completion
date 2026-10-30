"""Quality jobs are distinct from node transport/schema diagnostics."""
from fastapi.responses import Response
from . import quality_diagnostics as q
from .quality_runtime import enqueue
from .quality_actions import impact,apply

def register(app,service):
 base='/api/projects/{rid}/quality-diagnostics'
 def writable():
  if service.review_only:raise ValueError('业务审核模式只查看已保存诊断')
 @app.get(base)
 def index(rid:str):return {'items':q.listing(service.run_dir(rid)),'review_only':service.review_only,'causes':q.CAUSES}
 @app.post(base)
 def create(rid:str,body:dict):
  writable();value=enqueue(service.run_dir(rid),body.get('test_set'),body.get('case_id'),tool_only=bool(body.get('tool_only')))
  return value
 @app.get(base+'/{did}')
 def get(rid:str,did:str,format:str='json',view:str='full',case_id:str|None=None,metric:str|None=None,offset:int=0,limit:int=100):
  value=q.report(service.run_dir(rid),did)
  if format=='md':return Response(q.markdown(value),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':'attachment; filename="quality-'+did+'.md"'})
  if format!='json':raise ValueError('仅支持json/md')
  if view=='compact':return q.compact_report(value,case_id,metric,offset,limit)
  if view!='full':raise ValueError('未知报告视图')
  return value
 @app.post(base+'/{did}/resume')
 def resume(rid:str,did:str):
  writable();value=q.report(service.run_dir(rid),did)
  if value['status']!='partial':raise ValueError('仅恢复部分完成诊断')
  from .quality_runtime import load_budget
  budget=load_budget(q.store(service.run_dir(rid))/did/'budget.local.json')
  if budget['unknown']:raise ValueError('有未知用量/在途记录，需核查后恢复；不会清空预算')
  value.update(status='queued',error=None);q.save(service.run_dir(rid),value);return value
 @app.post(base+'/{did}/impact')
 def preview(rid:str,did:str,body:dict):
  writable();plan=impact(service.run_dir(rid),did,body);return {k:v for k,v in plan.items() if k not in {'registry','settings'}}
 @app.post(base+'/{did}/apply')
 def save(rid:str,did:str,body:dict):writable();return apply(service,rid,did,body)
 @app.get(base+'/{did}/comparison')
 def comparison(rid:str,did:str):
  from .quality_actions import compare_saved
  return compare_saved(service.run_dir(rid),did)
