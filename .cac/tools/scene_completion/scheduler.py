"""Persistent per-task DAG with local failure, shared admission and bounded repair."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from contextvars import copy_context
from .storage import read_json,write_json,fingerprint
from .model_configuration import concurrency_limit
from contextlib import contextmanager
import threading,time

@contextmanager
def run_lock(root):
    import os
    path=Path(root)/'.workflow.lock';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as f:
        if not path.stat().st_size:f.write(b'0');f.flush()
        f.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as e:raise ValueError('run already active') from e
            try:yield
            finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as e:raise ValueError('run already active') from e
            try:yield
            finally:fcntl.flock(f,fcntl.LOCK_UN)

class TaskBlocked(Exception):
    def __init__(self,status,details):super().__init__(str(details));self.status=status;self.details=details
class TaskRejected(Exception):
    def __init__(self,details):super().__init__(str(details));self.details=details

@dataclass
class Task:
    key:str
    case:str
    stage:str
    deps:tuple=()
    version:object=None
    execute:object=None
    repair:object=None
    verify:object=None

class CallGate:
    def __init__(self,concurrency=1,*,adaptive=True,on_change=None,pause_file=None):
        self.limit=concurrency_limit(concurrency);self.effective_limit=self.limit
        self.adaptive=adaptive;self.on_change=on_change;self.pause_file=Path(pause_file) if pause_file else None
        self.condition=threading.Condition();self.active=0;self.retry_not_before=0.;self.quota=threading.Event()
    @contextmanager
    def slot(self):
        with self.condition:
            while self.active>=self.effective_limit or time.monotonic()<self.retry_not_before:
                self.condition.wait(timeout=max(.05,self.retry_not_before-time.monotonic()))
            self.active+=1
        try:yield
        finally:
            with self.condition:self.active-=1;self.condition.notify_all()
    def observe(self,diagnostic):
        if not isinstance(diagnostic,dict) or diagnostic.get('failure_category')!='rate_limited':return
        with self.condition:
            if self.adaptive:self.effective_limit=max(1,self.effective_limit//2)
            self.retry_not_before=max(self.retry_not_before,time.monotonic()+max(1.,min(300.,float(diagnostic.get('retry_after_seconds') or 30))))
            self.condition.notify_all()
        if self.on_change:self.on_change({'configured_max':self.limit,'effective_max':self.effective_limit,'not_before_unix':time.time()+max(0,self.retry_not_before-time.monotonic())})
    def call(self,function,*args,**kwargs):
        from .execution_events import emit,phase
        body=next((v for v in args if isinstance(v,dict) and v.get('model')),kwargs.get('body',{}))
        model=body.get('model') if isinstance(body,dict) else None
        for retry in range(4):
            with self.slot():
                if self.pause_file and self.pause_file.exists():raise TaskBlocked('pending',{'admission_paused':True})
                if self.quota.is_set():raise TaskBlocked('budget_exhausted',{'quota':True})
                try:return function(*args,**kwargs)
                except Exception as e:
                    d=getattr(e,'response_diagnostic',None)
                    if not d or not d.get('failure_category'):raise
                    if d['failure_category']=='rate_limited':
                        delay=float(d.get('retry_after_seconds') or (2**(retry+1)))
                        delay=max(0.,min(300.,delay))
                        self.observe({**d,'retry_after_seconds':delay})
                        if retry==3:raise TaskBlocked('rate_limited',{'transport_failure':d,'retry_count':retry,'recoverable':True}) from e
                        at=time.time()+max(delay,self.retry_not_before-time.monotonic())
                        phase('rate_limit_wait',retry_at=at,retry_count=retry+1,retry_limit=3)
                        emit('rate_limit_wait',retry_at=at,retry_count=retry+1,retry_limit=3,diagnostic=d)
                        continue
                    if d['failure_category'] in {'quota_exhausted','budget_exhausted'}:
                        if model and d.get('budget_kind')=='tokens' and d.get('budget_reason')!='insufficient_provider_allowance':
                            # Admission is request-specific: another model, a
                            # smaller request, or released in-flight reserves
                            # may still fit. Never latch a global quota flag.
                            raise TaskBlocked('budget_exhausted',{**d,'model':model,'model_scope':True}) from e
                        else:self.quota.set()
                        raise TaskBlocked('budget_exhausted',d) from e
                    if d.get('configuration_required'):raise TaskBlocked('awaiting_configuration',d) from e
                    raise TaskBlocked('pending',{'transport_failure':d}) from e
        raise AssertionError('bounded retry exhausted')

class Scheduler:
    def __init__(self,root,concurrency=1,auto_repair='bounded',max_rounds=2):
        if max_rounds not in (0,1,2):raise ValueError('at most two repair rounds')
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'workflow_tasks.json';self.tasks={};self.on_update=None
        self.on_result=None;self.can_recover=None;self.priority_cases=[]
        self.state=read_json(self.path) if self.path.exists() else {'tasks':{},'events':[]}
        from .execution_events import EventStore
        self.events=EventStore(root)
        self.limit=concurrency_limit(concurrency);self.rounds=max_rounds if auto_repair=='bounded' else 0
    def save(self):write_json(self.path,self.state)
    def add(self,task):
        if task.key in self.tasks:raise ValueError('duplicate task key')
        self.tasks[task.key]=task
        from .execution_graph import expected_files
        from .deepagents_client import role_for
        write_json(self.root/'workflow_graph.json',{'nodes':[{'id':t.key,'case':t.case,'stage':t.stage,'role':role_for(t.stage),'label':getattr(t,'display_label',None),'deps':list(t.deps),'expected_files':expected_files(t.key,t.case,t.stage)} for t in self.tasks.values()]})
        self.events.append('graph_updated',node_id=task.key)
    def _event(self,key,event):
        self.state['events'].append({'task':key,'event':event,'at':time.time()})
        from .deepagents_client import role_for
        t=self.tasks[key];r=self.state['tasks'].get(key,{})
        self.events.append('task_status',task_key=key,role=role_for(t.stage),case=t.case,attempt=r.get('rounds',0)+1,status=event,phase={'started':'preparing','repairing':'preparing','passed':'complete'}.get(event,event),failure=r.get('failure'))
    def run(self):
        for t in self.tasks.values():
            if any(d not in self.tasks for d in t.deps):raise ValueError('unknown dependency')
        remaining=set(self.tasks);active={};done=set();outputs={};dispatches={}
        # Historical passed flags are not proof that this execution has
        # revalidated the task's identity, dependencies and cached artifact.
        self.resolved_tasks=done
        def job(t,deps,record):
            fn=t.repair if record['rounds'] else t.execute
            from .execution_events import bind,phase
            from .deepagents_client import role_for
            with bind(self.events,task_key=t.key,role=role_for(t.stage),case=t.case,attempt=record['rounds']+1):
                v=(fn or t.execute)(deps,record)
                phase('validating')
                if t.verify:t.verify(v)
                phase('saving')
                return v
        with ThreadPoolExecutor(max_workers=self.limit) as pool:
            while remaining or active:
                if self.on_update:
                    self.on_update()
                    remaining.update(set(self.tasks)-done-set(active.values()))
                progressed=False
                roots={'components','api-map','use-case-extract','use-case-align','existing-branches','api-index'}
                order={key:n for n,key in enumerate(self.tasks)}
                # Filename sorting let api-parameters-part-* starve both use-case
                # catalogs. Unlock project roots first, then share dispatches
                # across stages so one large fan-out cannot monopolize slots.
                rank=lambda c:0 if not self.priority_cases else -1 if c=='shared' else self.priority_cases.index(c) if c in self.priority_cases else len(self.priority_cases)
                for key in sorted(remaining,key=lambda k:(0 if self.tasks[k].case=='shared' and self.tasks[k].stage in {'source-index','document-context'} else 1 if self.tasks[k].case=='shared' and self.tasks[k].stage in roots else 2,rank(self.tasks[k].case),dispatches.get(self.tasks[k].stage,0),order[k])):
                    t=self.tasks[key]
                    if not set(t.deps)<=done:continue
                    if any(self.state['tasks'][d]['status']!='passed' for d in t.deps):
                        self.state['tasks'][key]={'status':'blocked_dependency','case':t.case,'stage':t.stage,'blocked_by':[d for d in t.deps if self.state['tasks'][d]['status']!='passed']};remaining.remove(key);done.add(key);progressed=True;continue
                    if getattr(t,'deferred',False):continue
                    deps={d:outputs[d] for d in t.deps}
                    identity=fingerprint({'version':t.version,'dependencies':{d:v.get('payload',v) if isinstance(v,dict) else v for d,v in deps.items()}})
                    rec=self.state['tasks'].get(key,{})
                    if rec.get('identity')!=identity and getattr(t,'migrate_cache',None):
                        t.migrate_cache(rec,deps,identity)
                    if rec.get('identity')!=identity:
                        rec={'identity':identity,'status':'pending','rounds':rec.get('rounds',0) if rec.get('status')=='awaiting_answer' else 0,'case':t.case,'stage':t.stage};self.state['tasks'][key]=rec
                    if rec.get('status')=='passed':
                        try:
                            v=read_json(self.root/rec['output_file'])
                            if fingerprint(v)!=rec['output_hash']:raise ValueError('cache content altered')
                            if t.verify:t.verify(v)
                            outputs[key]=v;remaining.remove(key);done.add(key);progressed=True;continue
                        except (OSError,ValueError,KeyError):rec.update(status='pending',rounds=0)
                    attempt_identity=getattr(t,'attempt_identity',None)
                    if attempt_identity and rec.get('attempt_identity')!=attempt_identity and rec.get('status') in {'rejected','failed','awaiting_configuration'}:
                        # Explicit provider edits allow a fresh bounded attempt window, not lost history.
                        rec.setdefault('attempt_windows',[]).append({k:rec.get(k) for k in ('attempt_identity','rounds','failure','finished_at')})
                        rec.update(status='pending',rounds=0);rec.pop('recovery_dispatch',None);rec.pop('failure_signatures',None)
                    rec['attempt_identity']=attempt_identity
                    # Waiting for a worker slot is not a semantic repair. Do
                    # not consume rounds on every scheduler wake-up while
                    # independent requests are still occupying the pool.
                    if len(active)>=self.limit:continue
                    if rec['status'] in {'rejected','failed'}:
                        if rec['rounds']>=self.rounds:
                            if self.can_recover and self.can_recover(t,rec):
                                rec['recovery_dispatch']=True;rec['recovery_calls']=rec.get('recovery_calls',0)+1
                            else:remaining.remove(key);done.add(key);progressed=True;continue
                        else:rec['rounds']+=1
                    elif rec['status']=='awaiting_configuration' and self.can_recover and self.can_recover(t,rec):
                        rec['recovery_dispatch']=True;rec['recovery_calls']=rec.get('recovery_calls',0)+1
                    previous_failure=rec.get('failure')
                    rec['version']=t.version
                    rec.update(status='running',started_at=time.time());rec.pop('failure',None);rec.pop('finished_at',None);self._event(key,'repairing' if rec['rounds'] else 'started')
                    attempt_record=dict(rec)
                    if (rec['rounds'] or rec.get('recovery_dispatch')) and previous_failure:attempt_record['failure']=previous_failure
                    future=pool.submit(copy_context().run,job,t,deps,attempt_record);active[future]=key;remaining.remove(key);progressed=True
                    dispatches[t.stage]=dispatches.get(t.stage,0)+1
                self.save()
                if not active:
                    if remaining and not progressed:raise ValueError('dependency cycle')
                    continue
                finished,_=wait(active,return_when=FIRST_COMPLETED)
                for f in finished:
                    key=active.pop(f);rec=self.state['tasks'][key]
                    try:
                        v=f.result();
                        from .artifact_exports import export_task
                        from .execution_graph import artifact_folder
                        if isinstance(v,dict) and 'payload' in v and 'task' in v:export_task(artifact_folder(self.root,key,rec['case']),rec['stage'],v['payload'],artifact_name=(key if rec['case']=='shared' else key[len(rec['case'])+1:]).replace(':','--'))
                        file='task_outputs/'+fingerprint([key,rec['identity'],v])+'.json';write_json(self.root/file,v)
                        proof=v.get('metadata',{}).get('execution',{}) if isinstance(v,dict) else {}
                        from .artifact_imports import record_use
                        record_use(self.root.parent,key,proof)
                        origin='同事产物导入' if proof.get('provider')=='colleague_import' else '恢复后生成' if proof.get('execution_model_evidence',{}).get('recovery') else '原流程生成'
                        rec['import_sources']=[{'file_id':proof['file_id'],'name':proof.get('file_name',proof['file_id']),'revision':proof['revision']}] if proof.get('provider')=='colleague_import' else []
                        rec.update(status='passed',output_file=file,output_hash=fingerprint(v),finished_at=time.time(),provenance=origin);outputs[key]=v;done.add(key);self._event(key,'passed')
                    except TaskBlocked as e:
                        rec.update(status=e.status,failure=e.details,finished_at=time.time());self._event(key,e.status)
                        if e.status=='awaiting_configuration' and self.can_recover and self.can_recover(self.tasks[key],rec):remaining.add(key)
                        else:done.add(key)
                    except Exception as e:
                        rec.update(finished_at=time.time(),status='rejected' if isinstance(e,(TaskRejected,ValueError)) else 'failed',failure=getattr(e,'details',{'error':str(e),'type':type(e).__name__}))
                        failure=rec['failure'];sig=fingerprint({k:v for k,v in failure.items() if k not in {'rejected_output','candidate_file','path','request_id','at'}});history=rec.setdefault('failure_signatures',[]);history.append(sig)
                        if rec['status']=='failed' or len(history)>1 and history[-1]==history[-2]:rec['rounds']=self.rounds
                        self._event(key,rec['status']);remaining.add(key)
                        if rec['status']=='failed' or rec.get('recovery_dispatch'):
                            from .node_recovery import fault_package
                            fault_package(self.root,key,rec)
                    self.save()
                    if self.on_result:self.on_result()
        return {'complete':all(self.state['tasks'][k]['status']=='passed' for k in self.tasks)}
