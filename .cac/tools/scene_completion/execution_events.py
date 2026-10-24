"""Durable task-scoped events. SSE reads committed events and can resume by ID."""
from contextvars import ContextVar
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone
import json,sqlite3,time

_CURRENT=ContextVar('scene_execution_events',default=None)
class EventStore:
    def __init__(self,root):
        self.path=Path(root)/'execution_events.sqlite3'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, task_key TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS event_task ON events(task_key,id)')
            db.execute('CREATE INDEX IF NOT EXISTS event_kind ON events(kind,id)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            with db:yield db
        finally:db.close()
    def append(self,kind,*,task_key=None,role=None,case=None,attempt=None,**data):
        now=time.time();row={'kind':kind,'at':now,'timestamp':datetime.now(timezone.utc).isoformat(),
          'task_key':task_key,'role':role,'case':case,'attempt':attempt,'data':data}
        with self.connect() as db:
            cur=db.execute('INSERT INTO events(at,task_key,kind,payload) VALUES(?,?,?,?)',(now,task_key,kind,json.dumps(row,ensure_ascii=False)))
            row['id']=cur.lastrowid
        return row
    def read(self,after=0,*,task_key=None,limit=500):
        if after<0 or not 1<=limit<=5000:raise ValueError('invalid event cursor/limit')
        sql='SELECT id,payload FROM events WHERE id>?';args=[after]
        if task_key is not None:sql+=' AND task_key=?';args.append(task_key)
        sql+=' ORDER BY id LIMIT ?';args.append(limit)
        with self.connect() as db:rows=db.execute(sql,args).fetchall()
        return [{**json.loads(payload),'id':seq} for seq,payload in rows]
    def latest_phases(self):
        with self.connect() as db:
            rows=db.execute("SELECT e.id,e.payload FROM events e INNER JOIN (SELECT task_key,MAX(id) id FROM events WHERE kind IN ('phase','task_status','tool_started','tool_finished','request_started','stream_delta','rate_limit_wait','question_asked') GROUP BY task_key) a ON a.id=e.id").fetchall()
        return {json.loads(payload)['task_key']:{**json.loads(payload),'id':seq} for seq,payload in rows}
    def dump_jsonl(self):
        after=0
        while True:
            rows=self.read(after,limit=1000)
            if not rows:return
            for row in rows:yield json.dumps(row,ensure_ascii=False)+'\n'
            after=rows[-1]['id']

@contextmanager
def bind(store,**fields):
    previous=_CURRENT.get();merged={**(previous[1] if previous else {}),**fields}
    token=_CURRENT.set((store,merged))
    try:yield
    finally:_CURRENT.reset(token)

def emit(kind,**data):
    context=_CURRENT.get()
    if context:return context[0].append(kind,**context[1],**data)

def phase(value,**data):return emit('phase',phase=value,**data)

@contextmanager
def fields(**values):
    context=_CURRENT.get()
    if context:
        with bind(context[0],**values):yield
    else:yield

def context():
    current=_CURRENT.get()
    return (current[0],dict(current[1])) if current else (None,{})
