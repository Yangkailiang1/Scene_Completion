"""Task-scoped durable guidance, questions and resumable model checkpoints."""
import json,time
from uuid import uuid4
from .execution_events import EventStore,emit

class Conversations:
    def __init__(self,root):
        self.events=EventStore(root)
        with self.events.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, at REAL NOT NULL, revision INTEGER NOT NULL, applied INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS checkpoints (task TEXT PRIMARY KEY, identity TEXT NOT NULL, state TEXT NOT NULL)')
    def revision(self,task):
        with self.events.connect() as db:return db.execute("SELECT COALESCE(MAX(revision),0) FROM messages WHERE task=? AND kind IN ('guidance','answer','context_resolution')",(task,)).fetchone()[0]
    def list(self,task):
        with self.events.connect() as db:rows=db.execute('SELECT id,kind,text,at,revision,applied,detail FROM messages WHERE task=? ORDER BY id',(task,)).fetchall()
        return [dict(id=r[0],kind=r[1],text=r[2],at=r[3],revision=r[4],applied=bool(r[5]),detail=json.loads(r[6])) for r in rows]
    def append(self,task,kind,text,detail=None):
        if not isinstance(text,str) or not text.strip() or len(text)>30000:raise ValueError('消息不能为空或超过30000字符')
        with self.events.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rev=db.execute("SELECT COALESCE(MAX(revision),0) FROM messages WHERE task=? AND kind IN ('guidance','answer','context_resolution')",(task,)).fetchone()[0]+(kind in {'guidance','answer','context_resolution'})
            row=db.execute('INSERT INTO messages(task,kind,text,at,revision,detail) VALUES(?,?,?,?,?,?)',(task,kind,text.strip(),time.time(),rev,json.dumps(detail or {},ensure_ascii=False)))
            mid=row.lastrowid
        self.events.append('conversation_message',task_key=task,message_id=mid,kind_name=kind,text=text,revision=rev)
        return next(r for r in self.list(task) if r['id']==mid)
    def question(self,task,text,basis,decision):
        if not basis.strip() or not decision.strip():raise ValueError('提问必须包含依据和需要用户决定的事项')
        pending=self.pending(task)
        if pending:return pending
        return self.append(task,'question',text,{'question_id':uuid4().hex,'basis':basis,'decision':decision})
    def pending(self,task):
        rows=self.list(task);answered={r['detail'].get('question_id') for r in rows if r['kind'] in {'answer','context_resolution','question_deferred'}}
        return next((r for r in reversed(rows) if r['kind']=='question' and r['detail']['question_id'] not in answered),None)
    def answer(self,task,qid,text):
        q=self.pending(task)
        if not q or q['detail']['question_id']!=qid:raise ValueError('问题已回答或已变更，请刷新')
        return self.append(task,'answer',text,{'question_id':qid})
    def resolve_from_evidence(self,task,qid,text,evidence):
        """Resolve an engine-context defect without impersonating a user decision."""
        q=self.pending(task)
        if not q or q['detail']['question_id']!=qid:raise ValueError('question already resolved or changed')
        if not evidence:raise ValueError('context resolution requires concrete repository/source evidence')
        return self.append(task,'context_resolution',text,{'question_id':qid,'evidence':evidence,'resolved_by':'repository_evidence','not_a_user_decision':True})
    def apply(self,task,message_ids=None):
        rows=[r for r in self.list(task) if r['kind'] in {'guidance','answer','context_resolution'} and not r['applied'] and (message_ids is None or r['id'] in message_ids)]
        if rows:
            with self.events.connect() as db:db.executemany('UPDATE messages SET applied=1 WHERE id=?',[(r['id'],) for r in rows])
            self.events.append('guidance_applied',task_key=task,revision=max(r['revision'] for r in rows),message_ids=[r['id'] for r in rows])
        return rows
    def checkpoint(self,task,identity,state=None):
        with self.events.connect() as db:
            if state is not None:
                db.execute('INSERT INTO checkpoints(task,identity,state) VALUES(?,?,?) ON CONFLICT(task) DO UPDATE SET identity=excluded.identity,state=excluded.state',(task,identity,json.dumps(state,ensure_ascii=False)))
                return state
            row=db.execute('SELECT identity,state FROM checkpoints WHERE task=?',(task,)).fetchone()
        return json.loads(row[1]) if row and row[0]==identity else None
    def invalidate(self,task):
        with self.events.connect() as db:db.execute('DELETE FROM checkpoints WHERE task=?',(task,))
