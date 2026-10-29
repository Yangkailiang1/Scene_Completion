"""Project manager journal. Configuration, chat, memory and actions survive restarts."""
from pathlib import Path
from contextlib import contextmanager
import sqlite3,json,time,uuid
from copy import deepcopy
from .storage import read_json,write_json,fingerprint

DEFAULT={'enabled':False,'mode':'collaborative','poll_seconds':10,'max_calls_per_turn':8,'reconnect_seconds':30,'context_limit':200000,'compression_ratio':.6}
class Journal:
 def __init__(self,project):
  self.project=Path(project);self.root=self.project/'manager';self.root.mkdir(parents=True,exist_ok=True)
  self.path=self.root/'journal.sqlite3'
  with self.db() as db:
   db.execute('CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, session TEXT, kind TEXT, content TEXT, detail TEXT, at REAL)')
   db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, revision INTEGER, data TEXT, PRIMARY KEY(kind,id))')
 def db(self):
  connection=sqlite3.connect(self.path,timeout=30);connection.execute('PRAGMA journal_mode=WAL')
  @contextmanager
  def transaction():
   try:
    with connection:yield connection
   finally:connection.close()
  return transaction()
 def get(self,kind,key='current',default=None):
  with self.db() as db:row=db.execute('SELECT revision,data FROM objects WHERE kind=? AND id=?',(kind,key)).fetchone()
  return {'revision':row[0],**json.loads(row[1])} if row else deepcopy(default)
 def put(self,kind,data,key='current',expected=None):
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT revision FROM objects WHERE kind=? AND id=?',(kind,key)).fetchone();revision=old[0] if old else 0
   if expected is not None and expected!=revision:raise ValueError('管理Agent记录已变化，请刷新')
   clean={k:v for k,v in data.items() if k!='revision'};revision+=1
   db.execute('INSERT INTO objects VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET revision=excluded.revision,data=excluded.data',(kind,key,revision,json.dumps(clean,ensure_ascii=False)))
  return {'revision':revision,**clean}
 def objects(self,kind):
  with self.db() as db:rows=db.execute('SELECT id,revision,data FROM objects WHERE kind=? ORDER BY rowid DESC',(kind,)).fetchall()
  return [{'id':key,'revision':rev,**json.loads(raw)} for key,rev,raw in rows]
 def session(self):
  value=self.get('session')
  return value or self.put('session',{'id':uuid.uuid4().hex,'created_at':time.time()})
 def new_session(self):return self.put('session',{'id':uuid.uuid4().hex,'created_at':time.time()})
 def append(self,kind,content,detail=None,session=None):
  if not isinstance(content,str) or len(content)>100000:raise ValueError('会话内容过长')
  with self.db() as db:
   cursor=db.execute('INSERT INTO entries(session,kind,content,detail,at) VALUES(?,?,?,?,?)',(session or self.session()['id'],kind,content,json.dumps(detail or {},ensure_ascii=False),time.time()));eid=cursor.lastrowid
  from .execution_events import EventStore
  EventStore(self.project/'run').append('manager_message',task_key='__manager__',role='manager',entry_id=eid,kind_name=kind)
  return eid
 def messages(self,after=0,limit=100,session=None,before=None,ascending=False):
  query='SELECT id,kind,content,detail,at FROM entries WHERE session=? AND id>?';params=[session or self.session()['id'],after]
  if before is not None:query+=' AND id<?';params.append(before)
  query+=' ORDER BY id '+('ASC' if ascending else 'DESC')+' LIMIT ?';params.append(max(1,min(500,limit)))
  with self.db() as db:rows=db.execute(query,params).fetchall()
  if not ascending:rows=list(reversed(rows))
  return [{'id':i,'kind':k,'content':c,'detail':json.loads(d),'at':at} for i,k,c,d,at in rows]
 def history(self,after=0,session=None):
  """Read forward without silently dropping the first entries of a long session."""
  while True:
   rows=self.messages(after=after,limit=500,session=session,ascending=True)
   if not rows:return
   yield from rows;after=rows[-1]['id']
 def memory(self,body=None):
  if body is None:return self.objects('memory')
  kind=body.get('category','decision')
  if kind not in {'decision','plan','fault','assumption'}:raise ValueError('未知记忆类别')
  text=body.get('text','').strip()
  if not text or len(text)>20000:raise ValueError('请填写记忆内容（不超过20000字符）')
  key=body.get('id') or uuid.uuid4().hex;old=self.get('memory',key)
  if old:self.put('memory-history',old,key+'-'+str(old['revision']))
  return self.put('memory',{'category':kind,'text':text,'active':bool(body.get('active',True)),'source':body.get('source','user'),'scope':body.get('scope',[]),'updated_at':time.time()},key,body.get('expected_revision',0))

def settings(project,body=None):
 p=Path(project)/'manager/settings.json';old=read_json(p) if p.exists() else {'revision':0,'settings':deepcopy(DEFAULT)}
 if body is None:return old
 if body.get('expected_revision')!=old['revision']:raise ValueError('管理Agent配置已变化，请刷新')
 value={**old['settings'],**body.get('settings',{})}
 if set(value)!=set(DEFAULT) or type(value['enabled']) is not bool or value['mode'] not in {'auto','collaborative'}:raise ValueError('无效托管设置')
 for key,low,high in [('poll_seconds',5,300),('max_calls_per_turn',2,20),('reconnect_seconds',10,1800),('context_limit',4096,2000000)]:
  if type(value[key]) is not int or not low<=value[key]<=high:raise ValueError(key+'超出范围')
 if type(value['compression_ratio']) not in (int,float) or not .2<=value['compression_ratio']<=.8:raise ValueError('压缩阈值必须在20%—80%')
 result={'revision':old['revision']+1,'settings':value,'at':time.time()}
 if not body.get('dry_run'):write_json(p,result)
 return {**result,'saved':not body.get('dry_run',False)}
