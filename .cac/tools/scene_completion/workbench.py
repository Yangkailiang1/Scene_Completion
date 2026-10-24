"""Local review application: Markdown sources, persisted artifacts and two run modes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import uuid4
import io,json,zipfile,time
from .storage import read_json,write_json,fingerprint
from .contracts import PROTOCOL,registry

PROJECT=Path(__file__).resolve().parents[3]
WEB=PROJECT/'web'

class Workbench:
    def __init__(self,root,client_factory=None,env_file=None):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.env_file=Path(env_file or PROJECT/'.env')
        self.pool=ThreadPoolExecutor(max_workers=2);self.active=set();self.lock=Lock();self.client_factory=client_factory
    def run_dir(self,run_id):
        if len(run_id)!=32 or any(c not in '0123456789abcdef' for c in run_id):raise ValueError('invalid project id')
        p=self.root/run_id
        if not (p/'project.json').is_file():raise ValueError('unknown project')
        return p
    def create(self,body):
        name=body.get('name','').strip()
        if not name:raise ValueError('请填写项目名称')
        if body.get('review_mode','manual') not in {'manual','auto'}:raise ValueError('invalid review mode')
        sources=body.get('sources',{});saved={}
        if not sources.get('RR') or not sources.get('SR'):raise ValueError('请提供RR和SR Markdown文档')
        rid=uuid4().hex;p=self.root/rid;p.mkdir()
        for role in ('RR','SR','test'):
            saved[role]=[]
            for idx,d in enumerate(sources.get(role,[])):
                if Path(d.get('name','')).suffix.lower() not in {'.md','.markdown'}:raise ValueError('仅支持Markdown')
                content=d.get('content','')
                if not isinstance(content,str) or len(content.encode('utf8'))>5_000_000:raise ValueError('文档为空或超过5MB')
                filename=f'sources/{role}-{idx}.md';target=p/filename;target.parent.mkdir(exist_ok=True);target.write_text(content,encoding='utf8')
                saved[role].append({'path':filename,'name':Path(d['name']).name})
        case_ids=body.get('case_ids',[])
        if not isinstance(case_ids,list) or any(not isinstance(x,str) or not x.strip() for x in case_ids):raise ValueError('invalid use-case scope')
        meta={'case_ids':case_ids,'id':rid,'name':name,'review_mode':body.get('review_mode','manual'),'created_at':time.time(),'sources':saved,'protocol':PROTOCOL}
        write_json(p/'project.json',meta);return meta
    def list(self):return sorted([read_json(p) for p in self.root.glob('*/project.json')],key=lambda x:x['created_at'],reverse=True)
    def configure(self,rid,body):
        p=self.run_dir(rid)
        if rid in self.active:raise ValueError('运行期间不能修改模型配置')
        if not body.get('base_url','').startswith(('http://','https://')) or not body.get('agent_model','').strip():raise ValueError('请填写内网API地址和实际模型标识')
        config={k:body[k] for k in ('base_url','agent_model','api_key','max_concurrency','max_tokens','timeout_seconds') if k in body}
        if not config.get('api_key') and (p/'model.local.json').exists():config['api_key']=read_json(p/'model.local.json').get('api_key','')
        config.update(agent_runtime='deepagents',structured_output='json_object',max_retries=0,adaptive_concurrency=True)
        for k,default,lo,hi in [('max_concurrency',2,1,8),('max_tokens',12000,256,64000),('timeout_seconds',120,10,1800)]:
            v=config.get(k,default)
            if type(v) is not int or not lo<=v<=hi:raise ValueError('invalid '+k)
            config[k]=v
        write_json(p/'model.local.json',config)
        return {k:v for k,v in config.items() if k!='api_key'}
    def start(self,rid):
        p=self.run_dir(rid)
        from .model_settings import resolve
        config=resolve(read_json(p/'model.local.json') if (p/'model.local.json').exists() else {},self.env_file)
        if not self.client_factory and (not config['api_key'] or not config['base_url']):raise ValueError('请在.env或项目中配置模型地址和密钥')
        with self.lock:
            if rid in self.active:raise ValueError('项目正在运行')
            self.active.add(rid)
        write_json(p/'job.json',{'status':'running','started_at':time.time()})
        self.pool.submit(self._execute,rid)
        return {'status':'running'}
    def _execute(self,rid):
        p=self.run_dir(rid)
        try:
            from .workflow import Execution,build_pipeline
            from .source_documents import read_documents
            from .cli import client_for
            from .scheduler import run_lock
            project=read_json(p/'project.json')
            from .model_settings import resolve
            config=resolve(read_json(p/'model.local.json') if (p/'model.local.json').exists() else {},self.env_file)
            config['review_mode']=project['review_mode'];config['run_root']=str(p/'run')
            with run_lock(p/'run'):
                client=self.client_factory(config,p/'run') if self.client_factory else client_for(config,p/'run')
                ex=Execution(p/'run',mode='external',client=client,config=config,case_ids=project.get('case_ids'))
                docs={role:read_documents([p/d['path'] for d in project['sources'][role]],'test' if role=='test' else 'existing') for role in ('RR','SR','test')}
                build_pipeline(ex,docs['RR'],docs['SR'],docs['test']);manifest=ex.finish()
                write_json(p/'job.json',{'status':'complete' if manifest['complete'] else 'waiting','finished_at':time.time()})
        except Exception as e:
            # Preserve actual diagnostics server-side without returning credentials.
            write_json(p/'job.json',{'status':'error','error_type':type(e).__name__,'message':'执行未完成，请查看任务状态与运行日志','finished_at':time.time()})
            import traceback
            (p/'error.log').write_text(traceback.format_exc(),encoding='utf8')
        finally:
            with self.lock:self.active.discard(rid)
    def snapshot(self,rid):
        p=self.run_dir(rid);run=p/'run'
        from .reviews import Reviews
        reviews=[]
        for f in (run/'reviews').glob('*.json'):
            v=read_json(f);reviews.append({k:x for k,x in v.items() if k not in {'inputs','payload'}})
        artifacts=[{'path':str(f.relative_to(p)).replace('\\','/'),'name':f.name,'bytes':f.stat().st_size} for folder in (run/'artifacts',run/'reviews/previews') for f in folder.rglob('*') if f.is_file()]
        records=read_json(run/'workflow_tasks.json')['tasks'] if (run/'workflow_tasks.json').exists() else {}
        prefixes={}
        for key,record in records.items():
            case=record.get('case','shared');stem=(key if case=='shared' else key[len(case)+1:]).replace(':','--')
            prefixes['run/artifacts/'+('shared' if case=='shared' else fingerprint(case)[:12])+'/'+stem]=key
            preview_stem=record['stage'] if ':' in key else key
            prefixes['run/reviews/previews/'+fingerprint(key)+'/'+preview_stem]=key
        for artifact in artifacts:
            artifact['task_key']=next((key for prefix,key in prefixes.items() if artifact['path'].startswith(prefix+'.')),None)
        for name in ('missing_report.json','missing_report.md'):
            if (run/name).exists():artifacts.append({'path':'run/'+name,'name':name,'bytes':(run/name).stat().st_size})
        job=read_json(p/'job.json') if (p/'job.json').exists() else {'status':'ready'}
        if job['status']=='running' and rid not in self.active:job={'status':'interrupted','message':'上次进程已退出，可继续运行并复用成功结果'}
        from .model_settings import resolve,public_settings
        config=resolve(read_json(p/'model.local.json') if (p/'model.local.json').exists() else {},self.env_file)
        return {'project':read_json(p/'project.json'),'job':job,'manifest':read_json(run/'run_manifest.json') if (run/'run_manifest.json').exists() else None,
          'tasks':read_json(run/'workflow_tasks.json') if (run/'workflow_tasks.json').exists() else {'tasks':{},'events':[]},'reviews':reviews,'artifacts':artifacts,
          'config':public_settings(config)}
    def export(self,rid):
        p=self.run_dir(rid);stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            for f in p.rglob('*'):
                if not f.is_file() or f.name.endswith(('.local.json','.lock')) or f.name=='error.log' or 'execution_events.sqlite3' in f.name or any(s in f.parts for s in ('model_cache','native')):continue
                z.write(f,str(f.relative_to(p)))
            if (p/'run/execution_events.sqlite3').exists():
                from .execution_events import EventStore
                z.writestr('run/execution_events.jsonl',''.join(EventStore(p/'run').dump_jsonl()))
        return stream.getvalue()

def create_app(root=None,client_factory=None,env_file=None):
    from fastapi import FastAPI,HTTPException,Request
    from fastapi.responses import FileResponse,Response
    from fastapi.staticfiles import StaticFiles
    from .reviews import Reviews
    service=Workbench(root or PROJECT/'.workbench',client_factory,env_file)
    app=FastAPI(title='场景完整性审核');app.state.workbench=service
    @app.middleware('http')
    async def local_write(request:Request,call_next):
        # Local UI writes are same-origin; cross-site forms must not start model jobs.
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return Response('Origin mismatch',status_code=403)
        try:return await call_next(request)
        except ValueError as e:return Response(json.dumps({'detail':str(e)},ensure_ascii=False),status_code=400,media_type='application/json')
    @app.get('/')
    def index():return FileResponse(WEB/'index.html')
    if (WEB/'assets').exists():app.mount('/assets',StaticFiles(directory=WEB/'assets'),name='assets')
    app.mount('/static',StaticFiles(directory=WEB),name='static')
    @app.get('/api/projects')
    def projects():return service.list()
    @app.post('/api/projects')
    def create(body:dict):return service.create(body)
    @app.get('/api/registry')
    def definitions():return registry()
    @app.get('/api/projects/{rid}')
    def snapshot(rid:str):return service.snapshot(rid)
    @app.put('/api/projects/{rid}/config')
    def configure(rid:str,body:dict):return service.configure(rid,body)
    @app.put('/api/projects/{rid}/mode')
    def mode(rid:str,body:dict):
        if rid in service.active:raise ValueError('运行期间不能切换模式')
        if body.get('review_mode') not in {'manual','auto'}:raise ValueError('invalid review mode')
        p=service.run_dir(rid);v=read_json(p/'project.json');v['review_mode']=body['review_mode'];write_json(p/'project.json',v);return v
    @app.post('/api/projects/{rid}/run')
    def start(rid:str):return service.start(rid)
    @app.get('/api/projects/{rid}/graph')
    def graph(rid:str):
        from .execution_graph import graph_snapshot
        return graph_snapshot(service.run_dir(rid)/'run')
    @app.get('/api/projects/{rid}/events/history')
    def history(rid:str,after:int=0,task_key:str|None=None,limit:int=500):
        from .execution_events import EventStore
        return {'events':EventStore(service.run_dir(rid)/'run').read(after,task_key=task_key,limit=limit)}
    @app.get('/api/projects/{rid}/events')
    async def events(rid:str,request:Request,after:int=0):
        from .execution_events import EventStore
        from fastapi.responses import StreamingResponse
        import asyncio
        store=EventStore(service.run_dir(rid)/'run')
        try:cursor=max(after,int(request.headers.get('Last-Event-ID','0')))
        except ValueError:raise HTTPException(400,'invalid event cursor')
        async def stream():
            nonlocal cursor
            heartbeat=time.monotonic()
            while not await request.is_disconnected():
                rows=store.read(cursor)
                for row in rows:
                    cursor=row['id']
                    yield 'id: '+str(cursor)+'\nevent: execution\ndata: '+json.dumps(row,ensure_ascii=False)+'\n\n'
                if time.monotonic()-heartbeat>10:
                    yield ': heartbeat\n\n';heartbeat=time.monotonic()
                await asyncio.sleep(.2)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    @app.get('/api/projects/{rid}/review-history')
    def review_history(rid:str,task_key:str):
        root=service.run_dir(rid)/'run/reviews/versions';rows=[]
        for f in root.glob('*.json'):
            value=read_json(f)
            if value.get('key')==task_key:rows.append({k:v for k,v in value.items() if k not in {'inputs'}})
        return {'versions':sorted(rows,key=lambda v:v.get('updated_at',''),reverse=True)[:30]}
    @app.get('/api/projects/{rid}/reviews/{key:path}')
    def review(rid:str,key:str):
        v=Reviews(service.run_dir(rid)/'run').read(key)
        if not v:raise HTTPException(404,'unknown review')
        return v
    @app.post('/api/projects/{rid}/decision')
    def decide(rid:str,body:dict):
        if rid in service.active:raise ValueError('请等待当前任务结束再提交审核')
        return Reviews(service.run_dir(rid)/'run').decide(body['key'],body['action'],expected_revision=body['revision'],
          expected_input_hash=body['input_hash'],value=body.get('payload'),comment=body.get('comment',''))
    @app.get('/api/projects/{rid}/file')
    def file(rid:str,path:str):
        p=service.run_dir(rid);f=(p/path).resolve()
        if not f.is_relative_to(p) or not f.is_file() or f.name.endswith(('.local.json','.lock')):raise HTTPException(404,'file unavailable')
        if not (path.startswith('run/artifacts/') or path.startswith('run/reviews/previews/') or path.startswith('sources/') or path in {'run/missing_report.json','run/missing_report.md'}):raise HTTPException(404,'file unavailable')
        return FileResponse(f)
    @app.get('/api/projects/{rid}/export')
    def export(rid:str):return Response(service.export(rid),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="scene-review.zip"'})
    return app
