"""Detached activation monitor. Stop only the authenticated local service, then rollback on startup failure."""
from pathlib import Path
import argparse,json,time,subprocess,sys,os,urllib.request,socket

def stop_child(proc):
 if proc.poll() is not None:return
 proc.terminate()
 try:proc.wait(timeout=10)
 except subprocess.TimeoutExpired:
  proc.kill();proc.wait(timeout=10)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--program',required=True);parser.add_argument('--patch',required=True);parser.add_argument('--env-file',required=True);parser.add_argument('--rollback',action='store_true');a=parser.parse_args()
 p=Path(a.project);program=Path(a.program);sys.path.insert(0,str(program/'.cac/tools'))
 from scene_completion.manager_store import Journal
 from scene_completion.storage import read_json
 j=Journal(p);control=p.parent/'runtime-control.json';record=read_json(control);port=int(record['port']);url=f'http://127.0.0.1:{port}'
 req=urllib.request.Request(url+'/api/runtime/control',data=b'{"action":"stop"}',headers={'Authorization':'Bearer '+record['token'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=10) as r:
  result=json.load(r)
  if result['pid']!=record['pid']:raise ValueError('服务身份不一致，未重启其他进程')
 for _ in range(100):
  with socket.socket() as sock:
   if sock.connect_ex(('127.0.0.1',port))!=0:break
  time.sleep(.2)
 else:raise ValueError('原服务尚未释放端口，保留已测补丁和诊断')
 def start():
  kwargs={'creationflags':subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
  with (p.parent/'server.log').open('ab') as log:proc=subprocess.Popen([sys.executable,'-B',str(program/'serve.py'),'--port',str(port),'--data-dir',str(p.parent),'--env-file',a.env_file,'--control-file',str(control)],stdout=log,stderr=log,stdin=subprocess.DEVNULL,**kwargs)
  for _ in range(150):
   if proc.poll() is not None:return False
   try:
    with urllib.request.urlopen(url+'/api/projects',timeout=.5) as response:
     if response.status==200 and read_json(control).get('pid')==proc.pid:return True
   except OSError:time.sleep(.2)
  stop_child(proc)
  return False
 if start():
  (p.parent/'manager-maintenance.json').unlink(missing_ok=True)
  j.put('activation',{'patch_id':a.patch,'status':'completed','at':time.time()},a.patch)
  j.append('system','安全重启及健康检查完成，后续任务使用新进程。',{'patch_id':a.patch})
  from scene_completion.manager_store import settings
  if settings(p)['settings']['mode']=='auto':
   j.append('user','补丁激活已完成。核查真实任务状态与未决写操作后，恢复受影响的未完成节点。')
  return
 from scene_completion.manager_patches import apply
 # Failed startup cannot have dispatched model tasks. Retain the failed server log.
 try:

  if not a.rollback:apply(p,program,a.patch,[],confirmed=True,rollback=True)
  ok=start()
  if ok:(p.parent/'manager-maintenance.json').unlink(missing_ok=True)
  j.put('activation',{'patch_id':a.patch,'status':'rolled_back' if ok else 'restart_failed','at':time.time()},a.patch)
  j.append('system','新服务启动失败，已回退补丁并恢复旧程序。' if ok else '补丁已回退；旧服务启动仍需核查server.log。',{'patch_id':a.patch})
 except Exception as e:j.append('system','自动回退需要核查：'+str(e),{'patch_id':a.patch})
if __name__=='__main__':main()
