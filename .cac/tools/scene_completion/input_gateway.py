"""Server-owned folder discovery and project-scoped colleague import APIs."""
from pathlib import Path
from threading import Event,Thread,RLock
import time,json,os
from .storage import read_json,write_json,fingerprint
from . import artifact_imports as artifacts

LOCK=RLock()
EXCLUDED={'node_modules','.git','.env','python','__pycache__','model_cache','data','.workbench','imports','run'}


def watch_settings(project,body=None):
 p=Path(project)/'input-watch.json';value=read_json(p) if p.exists() else {'directory':None,'watch':False,'observed':{},'last_scan':None,'revision':0}
 if body is None:return {k:v for k,v in value.items() if k!='observed'}
 if body.get('expected_revision') is not None and body['expected_revision']!=value['revision']:raise ValueError('扫描设置已变化')
 directory=Path(body.get('directory') or value.get('directory') or '').expanduser().resolve()
 if not directory.is_dir():raise ValueError('input目录不存在，请填写服务所在电脑的本地目录')
 if directory==Path(directory.anchor):raise ValueError('不能将整个磁盘登记为input目录')
 if (directory/'serve.py').exists() or (directory/'.git').exists() or (directory/'python.exe').exists():raise ValueError('请登记专用材料目录，不扫描程序或凭证目录')
 row={**value,'directory':str(directory),'watch':body.get('watch',value['watch']),'revision':value['revision']+1}
 if type(row['watch']) is not bool:raise ValueError('watch必须为布尔值')
 if str(directory)!=value.get('directory'):row['observed']={}
 if body.get('dry_run'):return {'saved':False,**{k:v for k,v in row.items() if k!='observed'}}
 write_json(p,row);return watch_settings(project)


def scan(project):
 project=Path(project);cfg=project/'input-watch.json'
 with LOCK:
  if not cfg.exists():return {'received':[],'waiting':0}
  setting=read_json(cfg);root=Path(setting['directory']).resolve();received=[];waiting=0;seen={}
  if not root.is_dir():return {'error':'input目录当前不可访问','received':[]}
  def paths():
   for directory,dirs,files in os.walk(root,followlinks=False):
    dirs[:]=[d for d in dirs if not d.startswith('.') and d not in EXCLUDED and not (Path(directory)/d).is_symlink()]
    for name in files:yield Path(directory)/name
  for n,path in enumerate(paths()):
   if n>10000:raise ValueError('input目录文件过多，请登记专用材料目录')
   relative=path.relative_to(root)
   if any(p.startswith('.') or p in EXCLUDED for p in relative.parts):continue
   if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):continue
   if path.suffix.lower() not in {'.md','.markdown','.json','.xlsx'} or any(x in path.name.lower() for x in ('.local.','api-key','api_key','credential','token-budget','ledger')):continue
   stat=path.stat()
   if stat.st_size>20*1024*1024:continue
   identity=[stat.st_size,stat.st_mtime_ns];old=setting['observed'].get(str(relative),{})
   count=old.get('stable',0)+1 if old.get('stat')==identity else 1
   record={'stat':identity,'stable':count,'hash':old.get('hash')}
   seen[str(relative)]=record
   if count<2:waiting+=1;continue
   data=path.read_bytes()
   if [path.stat().st_size,path.stat().st_mtime_ns]!=identity:waiting+=1;continue
   digest=fingerprint(data.hex())
   if digest==old.get('hash'):continue
   import base64
   received+=artifacts.receive(project,[{'name':path.name,'content_base64':base64.b64encode(data).decode()}])['received']
   record['hash']=digest
  setting.update(observed=seen,last_scan=time.time());write_json(cfg,setting)
  return {'received':received,'waiting':waiting,'scanned_at':setting['last_scan']}


class InputWatcher:
 def __init__(self,service):
  self.service=service;self.stop_event=Event();self.converting=set();self.guard=RLock()
  self.thread=Thread(target=self.loop,name='scene-input-watch',daemon=True);self.thread.start()
 def close(self):self.stop_event.set()
 def loop(self):
  while not self.stop_event.wait(5):
   for p in self.service.root.glob('*/project.json'):
    try:
     setting=watch_settings(p.parent)
     if setting.get('watch') or setting.get('directory') and setting.get('last_scan') is None:scan(p.parent)
     self.convert_pending(p.parent)
    except Exception as e:
     write_json(p.parent/'imports/watch-error.json',{'error':type(e).__name__,'message':str(e),'at':time.time()})
 def convert_pending(self,project):
  for row in artifacts.view(project)['items']:
   if row['status']!='needs_conversion':continue
   key=(project.name,row['id'])
   with self.guard:
    if key in self.converting:continue
    self.converting.add(key)
   self.service.pool.submit(self.convert,project,row['id'])
 def convert(self,project,iid):
  try:
   from .cli import client_for
   from .scheduler import CallGate
   config=self.service.model_config(project.name);config['run_root']=str(project/'run')
   client=self.service.client_factory(config,project/'run') if self.service.client_factory else client_for(config,project/'run')
   if hasattr(client,'post'):
    gate=self.service.gates.setdefault(project.name,CallGate(min(3,config.get('max_concurrency',2))))
    client.shared_call_gate=gate
    original=client.post;client.post=lambda *a,**kw:gate.call(original,*a,**kw)
   artifacts.convert(project,iid,client)
  except Exception as e:
   # One failure is visible, not requeued every five seconds indefinitely.
   with artifacts.LOCK:
    index=artifacts.load(project)
    if iid in index['items']:
     row=read_json(project/index['items'][iid]['record']);row.update(status='conversion_failed',error=str(e),revision=row['revision']+1)
     write_json(project/index['items'][iid]['record'],row);index['items'][iid]['status']='conversion_failed';artifacts.save(project,index)
  finally:
   with self.guard:self.converting.discard((project.name,iid))


def register(app,service):
 def idle(project):
  from .worker_runtime import read_job
  if project.name in service.active or read_job(project).get('status')=='running':raise ValueError('当前执行中，请等本轮结束后确认替换；新文件可先转换为候选')
 @app.get('/api/projects/{rid}/imports')
 def imports(rid:str,item:str|None=None):return artifacts.view(service.run_dir(rid),item)
 @app.post('/api/projects/{rid}/imports')
 def upload(rid:str,body:dict):
  p=service.run_dir(rid);result=artifacts.receive(p,body.get('files',[]))
  if service.input_watcher:service.input_watcher.convert_pending(p)
  return result
 @app.put('/api/projects/{rid}/imports/{iid}')
 def decide(rid:str,iid:str,body:dict):
  p=service.run_dir(rid);idle(p)
  if body.get('action')=='retry_conversion':
   with artifacts.LOCK:
    index=artifacts.load(p);row=artifacts.view(p,iid)
    if body.get('expected_revision')!=row['revision']:raise ValueError('版本已变化')
    if body.get('dry_run'):return {'saved':False,'valid':True}
    row.update(status='needs_conversion',revision=row['revision']+1);write_json(p/index['items'][iid]['record'],row);index['items'][iid]['status']='needs_conversion';artifacts.save(p,index)
   if service.input_watcher:service.input_watcher.convert_pending(p)
   return {'saved':True}
  if body.get('action')=='accept_source':return accept_source(service,p,artifacts.view(p,iid),body)
  return artifacts.decide(p,iid,body)
 @app.post('/api/projects/{rid}/input-scan')
 def input_scan(rid:str,body:dict):
  p=service.run_dir(rid);setting=watch_settings(p,body)
  if body.get('dry_run'):return setting
  result=scan(p)
  # The second stable sample is performed by the server, even without watch.
  def second():
   time.sleep(5)
   scan(p)
   if service.input_watcher:service.input_watcher.convert_pending(p)
  service.pool.submit(second)
  return {**result,'settings':setting}
 @app.get('/api/projects/{rid}/input-scan')
 def input_settings(rid:str):return watch_settings(service.run_dir(rid))
 @app.get('/api/projects/{rid}/recovery')
 def recovery(rid:str):
  from .node_recovery import settings,records
  p=service.run_dir(rid);return {**settings(p),'ledger':records(p)}
 @app.put('/api/projects/{rid}/recovery')
 def recovery_update(rid:str,body:dict):
  from .node_recovery import settings
  p=service.run_dir(rid);idle(p);return settings(p,body)


def deepcopy_json(value):return json.loads(json.dumps(value))

def accept_source(service,p,row,body):
 iid=row['id']
 if body.get('expected_revision')!=row['revision']:raise ValueError('版本已变化')
 role=body.get('role',row['role'])
 if role not in {'RR','SR','test'}:raise ValueError('请选择来源用途')
 raw=(p/row['original']).read_bytes()
 from .test_sources import decode_source
 import base64
 decode_source({'name':row['name'],'content_base64':base64.b64encode(raw).decode()},role)
 if role=='test':
  from .test_sources import preview_sources
  import base64
  if not preview_sources([{'name':row['name'],'content_base64':base64.b64encode(raw).decode()}])['valid']:raise ValueError('测试文件未通过导入预览')
 meta=read_json(p/'project.json');old=deepcopy_json(meta)
 same=[f for f in meta['sources'][role] if f['name']==row['name']]
 if same and not body.get('replace'):raise ValueError('已有同名来源，请确认替换或选择其他用途')
 if body.get('dry_run'):return {'saved':False,'valid':True,'role':role}
 write_json(p/'source_versions'/(fingerprint(old)+'.json'),old)
 meta['sources'][role]=[f for f in meta['sources'][role] if not (body.get('replace') and f['name']==row['name'])]+[{'name':row['name'],'path':row['original'],'source_id':'input-source-'+row['id']}]
 if role=='test':
  version=fingerprint([(f['name'],fingerprint((p/f['path']).read_bytes().hex())) for f in meta['sources'][role]])[:20]
  history=p/'test_source_versions.json';versions=read_json(history) if history.exists() else [{'id':old.get('test_source_version',fingerprint(old['sources']['test'])[:20]),'sources':old['sources']['test'],'created_at':old['created_at']}]
  versions.append({'id':version,'sources':meta['sources'][role],'created_at':time.time()});write_json(history,versions);meta['test_source_version']=version
 write_json(p/'project.json',meta)
 with artifacts.LOCK:
  index=artifacts.load(p);row.update(status='source_active',role=role,revision=row['revision']+1);write_json(p/index['items'][iid]['record'],row);index['items'][iid]['status']='source_active';artifacts.save(p,index)
 return {'saved':True,'next':'显式run后仅重算受来源影响的节点'}
