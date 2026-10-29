"""Project processes and heartbeats; web process never hosts a production DAG."""
from pathlib import Path
import os,time,json,subprocess,sys,threading,secrets
from .storage import read_json,write_json


def pid_alive(pid):
 if os.name=='nt':
  import ctypes
  kernel=ctypes.WinDLL('kernel32',use_last_error=True)
  kernel.OpenProcess.restype=ctypes.c_void_p
  handle=kernel.OpenProcess(0x1000,False,pid)
  if not handle:return ctypes.get_last_error()!=87
  try:
   code=ctypes.c_ulong();ok=kernel.GetExitCodeProcess(ctypes.c_void_p(handle),ctypes.byref(code))
   return not ok or code.value==259
  finally:kernel.CloseHandle(ctypes.c_void_p(handle))
 try:os.kill(pid,0)
 except ProcessLookupError:return False
 except OSError:return True
 return True


def read_job(project):
 p=Path(project);job=read_json(p/'job.json') if (p/'job.json').exists() else {'status':'ready'}
 hb=p/'worker-heartbeat.json'
 if job.get('status')=='running' and hb.exists():
  row=read_json(hb)
  if row.get('pid')==job.get('pid') and row.get('worker_token')==job.get('worker_token'):job.update(worker_heartbeat=row['at'])
 return job


def spawn(service,rid):
 p=service.run_dir(rid);log=p/'run/worker.log';log.parent.mkdir(parents=True,exist_ok=True)
 kwargs={}
 if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
 job=read_json(p/'job.json');job.update(worker_token=secrets.token_hex(16),worker_heartbeat=time.time());write_json(p/'job.json',job)
 with log.open('ab') as out:
  process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('project_worker.py')),'--root',str(service.root),'--project',rid,'--env-file',str(service.env_file)],stdout=out,stderr=out,**kwargs)
 job=read_json(p/'job.json');job.update(pid=process.pid,worker_heartbeat=time.time());write_json(p/'job.json',job)
 return process


def unsafe_to_resume(project):
 """An unfinished HTTP call or timed-out POST cannot be blindly reissued."""
 from .execution_events import EventStore
 root=Path(project)/'run'
 if not (root/'execution_events.sqlite3').exists():return False
 store=EventStore(root)
 with store.connect() as db:
  rows=db.execute("SELECT payload FROM events WHERE kind IN ('request_started','request_finished','request_failed') ORDER BY id DESC LIMIT 200").fetchall()
 latest={}
 for (raw,) in rows:
  event=json.loads(raw);key=event['data'].get('model_call_id')
  if key:latest.setdefault(key,event)
 for e in latest.values():
  if e['kind']=='request_started':return True
  if e['kind']=='request_failed' and e['data'].get('diagnostic',{}).get('failure_category') in {'transport_timeout','stream_incomplete','connection_failed'}:return True
 return False


def monitor(service,rid,process):
 p=service.run_dir(rid);code=process.wait()
 job=read_job(p)
 if job.get('status')=='running':
  job.update(status='interrupted',exit_code=code,message='执行进程退出，现场已保存；检查不确定请求后再恢复')
  write_json(p/'job.json',job)
 with service.lock:service.active.discard(rid)
 if job.get('status')=='interrupted' and job.get('reason')!='user_stop' and not unsafe_to_resume(p):
  marker=p/'worker-restarts.json';record=read_json(marker) if marker.exists() else {'count':0}
  if record['count']<1:
   record['count']+=1;write_json(marker,record)
   try:service.start(rid,job.get('run_options',{}))
   except ValueError:pass


def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--project',required=True);parser.add_argument('--env-file',required=True);args=parser.parse_args()
 from .workbench import Workbench
 service=Workbench(args.root,env_file=args.env_file,worker=True);service.active.add(args.project)
 project=service.run_dir(args.project);stop=threading.Event();token=read_json(project/'job.json')['worker_token']
 def heartbeat():
  while not stop.wait(1):
   request=project/'worker-stop.json'
   if request.exists() and read_json(request).get('worker_token')==token:
    job=read_json(project/'job.json');job.update(status='interrupted',reason='user_stop',message='用户停止后台服务，已保留检查点；未决模型请求不会自动重发');write_json(project/'job.json',job);os._exit(0)
   write_json(project/'worker-heartbeat.json',{'pid':os.getpid(),'worker_token':token,'at':time.time()})
 thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
 try:service._execute(args.project)
 finally:stop.set();thread.join(timeout=2)


def stop_workers(service):
 from .manager_runtime import stop_managers
 stop_managers(service)
 for path in service.root.glob('*/project.json'):
  p=path.parent;job=read_job(p)
  if job.get('status')=='running' and job.get('worker_token'):
   write_json(p/'worker-stop.json',{'worker_token':job['worker_token'],'at':time.time()})


class Guardian:
 """Reattach to heartbeats after web restart without guessing HTTP outcomes."""
 def __init__(self,service):
  self.service=service;self.stop=threading.Event();self.thread=threading.Thread(target=self.loop,daemon=True,name='scene-worker-guardian');self.thread.start()
 def close(self):self.stop.set()
 def loop(self):
  while not self.stop.wait(5):
   for path in self.service.root.glob('*/project.json'):
    p=path.parent;job=read_job(p)
    if job.get('status')!='running' or p.name in self.service.active:continue
    if job.get('worker_heartbeat',job.get('started_at',0))>time.time()-30:continue
    # A live PID with an expired heartbeat is not assumed dead.
    pid=job.get('pid')
    if pid and pid_alive(pid):continue
    job.update(status='interrupted',message='进程失联，检查点已保留；仅在无未决模型请求时恢复');write_json(p/'job.json',job)
    if not unsafe_to_resume(p):
     marker=p/'worker-restarts.json';record=read_json(marker) if marker.exists() else {'count':0}
     if record['count']<1:
      record['count']+=1;write_json(marker,record)
      try:self.service.start(p.name,job.get('run_options',{}))
      except ValueError:pass
