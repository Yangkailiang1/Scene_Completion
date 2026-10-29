"""Browser and CLI share the same manager journal, config and audited tools."""
from .manager_store import Journal,settings
from .manager_agent import model_config,execute_action
from .storage import fingerprint
import time

def register(app,service):
 from fastapi.responses import Response
 def writable():
  if service.review_only:raise ValueError('业务审核包不能启用管理Agent或修改程序')
 @app.get('/api/projects/{rid}/manager')
 def status(rid:str):
  p=service.run_dir(rid);j=Journal(p)
  return {'configuration':settings(p),'session':j.session(),'runtime':j.get('runtime',default={'status':'paused'}),'messages':j.messages(),'memory':j.memory(),'plan':j.get('plan',default={'items':[]}), 'operations':j.objects('operation')[:100],'patches':j.objects('patch'),'trials':j.objects('trial'),'review_only':service.review_only}
 @app.get('/api/projects/{rid}/manager/messages')
 def history(rid:str,after:int=0,before:int|None=None,limit:int=100):
  rows=Journal(service.run_dir(rid)).messages(after=after,before=before,limit=limit)
  return {'messages':rows,'before':rows[0]['id'] if rows else None,'after':rows[-1]['id'] if rows else after}
 @app.put('/api/projects/{rid}/manager/config')
 def configure(rid:str,body:dict):
  writable();p=service.run_dir(rid);value=settings(p,body)
  if not body.get('dry_run') and not value['settings']['enabled']:
   j=Journal(p);proc=j.get('process',default={})
   latest=max((r['id'] for r in j.history() if r['kind']=='user'),default=0)
   j.put('runtime',{**j.get('runtime',default={}), 'paused_user':latest,'status':'paused'})
   if proc.get('token'):
    from .storage import write_json
    write_json(j.root/'stop.json',{'token':proc['token'],'at':time.time()})
  if not body.get('dry_run') and value['settings']['enabled']:
   (p/'manager/stop.json').unlink(missing_ok=True)
   f=p/'manager/model.local.json'
   if not f.exists():model_config(service,rid,{'expected_revision':0,'config':{}})
   from .manager_runtime import spawn
   spawn(service,rid)
  return value
 @app.get('/api/projects/{rid}/manager/model')
 def model(rid:str):return model_config(service,rid)
 @app.put('/api/projects/{rid}/manager/model')
 def save_model(rid:str,body:dict):writable();return model_config(service,rid,body)
 @app.post('/api/projects/{rid}/manager/messages')
 def message(rid:str,body:dict):
  writable();text=body.get('text','').strip()
  if not text or len(text)>30000:raise ValueError('请输入消息（最多30000字符）')
  j=Journal(service.run_dir(rid));entry=j.append('user',text)
  from .manager_runtime import spawn
  return {'entry_id':entry,**spawn(service,rid)}
 @app.post('/api/projects/{rid}/manager/run')
 def run(rid:str,body:dict|None=None):
  writable();j=Journal(service.run_dir(rid));j.put('runtime',{**j.get('runtime',default={}), 'retry_at':0})
  if (body or {}).get('new_session'):j.new_session()
  j.append('user',(body or {}).get('text') or '请检查并继续推进当前项目。')
  from .manager_runtime import spawn
  return spawn(service,rid)
 @app.put('/api/projects/{rid}/manager/memory')
 def memory(rid:str,body:dict):writable();return Journal(service.run_dir(rid)).memory(body)
 @app.post('/api/projects/{rid}/manager/actions')
 def action(rid:str,body:dict):
  writable();j=Journal(service.run_dir(rid));name=body['action'];key=body.get('request_id') or __import__('uuid').uuid4().hex
  old=j.get('operation',key)
  if old:return old
  j.put('operation',{'action':name,'status':'started','at':time.time()},key,0)
  try:value=execute_action(service,rid,name,body.get('arguments',{}),confirmed=bool(body.get('confirmed')))
  except Exception as e:
   j.put('operation',{'action':name,'status':'failed','error':str(e),'at':time.time()},key);raise
  j.put('operation',{'action':name,'status':'completed','at':time.time()},key)
  return value
 @app.get('/api/projects/{rid}/throughput')
 def throughput(rid:str,after:int=0,limit:int=2000,model:str|None=None,node:str|None=None,format:str='json'):
  from .throughput_view import series,csv_export
  value=series(service.run_dir(rid),after,limit,model,node)
  if format=='csv':return Response(csv_export(value),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="model-throughput.csv"'})
  if format!='json':raise ValueError('仅支持JSON或CSV；图形在前端导出SVG/PNG')
  return value
