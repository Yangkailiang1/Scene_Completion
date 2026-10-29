"""Durable manager process; polling is code, reasoning occurs only for new work."""
from pathlib import Path
import time,threading,subprocess,sys,os,json
from .storage import read_json,write_json,fingerprint
from .manager_store import Journal,settings

def trigger_snapshot(service,rid):
 s=service.execution_status(rid);p=service.run_dir(rid)
 # Ordinary successful progress is observed without another LLM request.
 bad=[n for n in s['pending_nodes'] if n['status'] not in {'pending','running','blocked_dependency'}]
 return {'complete':s['complete'],'job_error':s['job'].get('error_type') if s['job'].get('status')=='error' else None,'bad':bad,'imports':read_json(p/'imports/index.json').get('revision') if (p/'imports/index.json').exists() else 0,'config':fingerprint(service.model_config(rid))}

def signature(service,rid):return fingerprint(trigger_snapshot(service,rid))

def launch_restart(service,rid,patch_id,rollback=False):
 from .manager_agent import PROGRAM
 p=service.run_dir(rid);j=Journal(p)
 command=[sys.executable,'-B',str(Path(__file__).with_name('manager_restart.py')),'--project',str(p),'--program',str(PROGRAM),'--patch',patch_id,'--env-file',str(service.env_file)]
 if rollback:command.append('--rollback')
 kwargs={'creationflags':subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
 write_json(service.root/'manager-maintenance.json',{'patch_id':patch_id,'project':rid,'at':time.time()})
 try:
  with (j.root/'patches'/patch_id/'restart.log').open('ab') as log:proc=subprocess.Popen(command,stdout=log,stderr=log,stdin=subprocess.DEVNULL,**kwargs)
 except Exception:
  # Keep maintenance active: a failed launch must not dispatch jobs on mixed code.
  j.put('activation',{'status':'restart_failed','patch_id':patch_id},patch_id);raise
 j.put('activation',{'status':'restarting','patch_id':patch_id,'pid':proc.pid,'rollback':rollback},patch_id)

def reconcile_activations(service,rid):
 """No LLM: finish durable, previously authorized activation at an idle boundary."""
 p=service.run_dir(rid);j=Journal(p)
 if (j.root/'stop.json').exists():
  proc=j.get('process',default={})
  if read_json(j.root/'stop.json').get('token')==proc.get('token'):return
 if (service.root/'manager-maintenance.json').exists():return
 from .manager_agent import PROGRAM
 from .manager_patches import apply
 for row in j.objects('activation'):
  if row['status']!='waiting_safe_boundary':continue
  patch=j.get('patch',row['patch_id'])
  if patch and patch['status'] in {'applied','rolled_back'} and patch.get('requires_fresh_process'):
   launch_restart(service,rid,row['patch_id'],rollback=row.get('rollback',False));return
  value=apply(p,PROGRAM,row['patch_id'],[service.run_dir(m['id']) for m in service.list()],confirmed=row.get('confirmed',False),rollback=row.get('rollback',False))
  if value['status'] in {'applied','rolled_back'}:
   launch_restart(service,rid,row['patch_id'],rollback=row.get('rollback',False));return

def stop_managers(service):
 for meta in service.list():
  journal=Journal(service.run_dir(meta['id']));proc=journal.get('process',default={})
  if proc.get('token'):write_json(journal.root/'stop.json',{'token':proc['token'],'at':time.time()})


def spawn(service,rid):
 if (service.root/'manager-maintenance.json').exists():return {'status':'waiting_safe_boundary'}
 p=service.run_dir(rid);j=Journal(p)
 from .worker_runtime import pid_alive
 old=j.get('process',default={})
 if old.get('pid') and pid_alive(old['pid']) and old.get('heartbeat',0)>time.time()-60:return {'status':'running','pid':old['pid']}
 from .scheduler import run_lock
 with run_lock(p/'manager/dispatch'):
  old=j.get('process',default={})
  if old.get('pid') and pid_alive(old['pid']) and old.get('heartbeat',0)>time.time()-60:return {'status':'running','pid':old['pid']}
  token=__import__('secrets').token_hex(16)
  command=[sys.executable,'-B',str(Path(__file__).with_name('manager_worker.py')),'--root',str(service.root),'--project',rid,'--env-file',str(service.env_file),'--url',getattr(service,'local_url','http://127.0.0.1:8765'),'--token',token]
  kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
  with (p/'manager/worker.log').open('ab') as log:proc=subprocess.Popen(command,stdout=log,stderr=log,**kwargs)
  j.put('process',{'pid':proc.pid,'token':token,'heartbeat':time.time()})
  return {'status':'started','pid':proc.pid}

class ManagerHost:
 def __init__(self,service):
  self.service=service;self.stop=threading.Event();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
 def close(self):self.stop.set()
 def loop(self):
  while not self.stop.wait(5):
   if (self.service.root/'manager-maintenance.json').exists():continue
   for meta in self.service.list():
    if meta.get('manager_trial'):continue
    p=self.service.run_dir(meta['id']);s=settings(p)['settings']
    j=Journal(p);runtime=j.get('runtime',default={});pending=any(m['kind']=='user' for m in j.history(after=max(runtime.get('handled_user',0),runtime.get('paused_user',0))))
    try:reconcile_activations(self.service,meta['id'])
    except Exception as e:j.append('system','等待补丁续接需核查：'+str(e))
    if s['enabled'] and s['mode']=='auto' or pending:
     try:spawn(self.service,meta['id'])
     except Exception as e:Journal(p).put('runtime',{'status':'waiting','reason':type(e).__name__,'at':time.time()})

def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--project',required=True);parser.add_argument('--env-file',required=True);parser.add_argument('--url',default='http://127.0.0.1:8765');parser.add_argument('--token',required=True);args=parser.parse_args()
 from .workbench import Workbench
 from .manager_agent import run_turn
 from .scheduler import run_lock
 service=Workbench(args.root,env_file=args.env_file);service.local_url=args.url;p=service.run_dir(args.project);journal=Journal(p)
 with run_lock(p/'manager/worker-lock'):
  stop=threading.Event()
  def heartbeat():
   while not stop.wait(5):journal.put('process',{'pid':os.getpid(),'token':args.token,'heartbeat':time.time()})
  threading.Thread(target=heartbeat,daemon=True).start()
  while True:
   if (journal.root/'stop.json').exists() and read_json(journal.root/'stop.json').get('token')==args.token:return
   journal.put('process',{'pid':os.getpid(),'token':args.token,'heartbeat':time.time()})
   if (service.root/'manager-maintenance.json').exists():return
   policy=settings(p)['settings'];state=journal.get('runtime',default={});pending=[r for r in journal.history(after=max(state.get('handled_user',0),state.get('paused_user',0))) if r['kind']=='user']
   if not pending and not (policy['enabled'] and policy['mode']=='auto'):return
   if state.get('retry_at',0)>time.time():time.sleep(2);continue
   # A fresh worker loads repaired modules; rollback an applied change if the
   # next execution reports a new program error. Provider failures do not trigger rollback.
   from .worker_runtime import read_job
   job=read_job(p)
   if policy['mode']=='auto' and job.get('error_type') in {'TypeError','AttributeError','NameError','ImportError','SyntaxError'}:
    for patch in journal.objects('patch'):
     if patch['status']=='applied' and job.get('finished_at',0)>patch.get('activated_at',float('inf')):
      try:
       from .manager_patches import apply
       from .manager_agent import PROGRAM
       result=apply(p,PROGRAM,patch['id'],[service.run_dir(m['id']) for m in service.list()],rollback=True)
       if result['status']=='rolled_back':launch_restart(service,args.project,patch['id'],rollback=True)
       journal.append('system','新执行暴露程序错误，已回退最近补丁。',{'patch_id':patch['id']})
       return
      except Exception as error:journal.append('system','补丁回退需核查：'+str(error))
   sig=signature(service,args.project)
   if not pending and state.get('trigger')==sig and state.get('status')!='waiting_reconnect':time.sleep(policy['poll_seconds']);continue
   try:
    run_turn(service,args.project,'user' if pending else '执行状态变化或等待重连')
    current=journal.get('runtime',default={});journal.put('runtime',{**current,'trigger':signature(service,args.project),'retry_at':time.time()+policy['reconnect_seconds']})
   except Exception as e:
    current=journal.get('runtime',default={});failures=current.get('reconnect_failures',0)+1
    journal.put('runtime',{**current,'status':'waiting_reconnect','error':type(e).__name__,'reason':str(e)[:2000],'reconnect_failures':failures,'retry_at':time.time()+min(300,policy['reconnect_seconds']*2**min(failures-1,3)),'handled_user':max([r['id'] for r in pending],default=current.get('handled_user',0)) if policy['mode']=='collaborative' else current.get('handled_user',0),'at':time.time()})
    journal.append('system','本轮管理暂未完成，已保存现场并等待重连。',{'error_type':type(e).__name__})
   if not (policy['enabled'] and policy['mode']=='auto'):return
