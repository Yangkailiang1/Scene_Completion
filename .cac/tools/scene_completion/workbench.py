"""Local review application: Markdown sources, persisted artifacts and two run modes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import uuid4
import io,json,zipfile,time
from .storage import read_json,write_json,fingerprint
from .worker_runtime import read_job
from .contracts import PROTOCOL,registry
from .project_review import project_scoped

PROJECT=Path(__file__).resolve().parents[3]
WEB=PROJECT/'web'

class Workbench:
    def __init__(self,root,client_factory=None,env_file=None,worker=False):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.env_file=Path(env_file or PROJECT/'.env')
        self.review_only=(self.root/'.review-mode.json').exists()
        self.pool=ThreadPoolExecutor(max_workers=2);self.active=set();self.lock=Lock();self.client_factory=client_factory;self.gates={};self.dialogue_active=set()
        self.worker=worker;self.input_watcher=None;self.guardian=None;self.manager_host=None;self.local_url=__import__("os").environ.get("SCENE_WORKBENCH_URL","http://127.0.0.1:8765")
    def run_dir(self,run_id):
        if len(run_id)!=32 or any(c not in '0123456789abcdef' for c in run_id):raise ValueError('invalid project id')
        p=self.root/run_id
        if not (p/'project.json').is_file():raise ValueError('unknown project')
        return p.resolve()
    def create(self,body):
        name=body.get('name','').strip()
        if not name:raise ValueError('请填写项目名称')
        if body.get('review_mode','manual') not in {'manual','auto'}:raise ValueError('invalid review mode')
        sources=body.get('sources',{});saved={}
        if not sources.get('RR') or not sources.get('SR'):raise ValueError('请提供RR和SR Markdown文档')
        from .test_sources import preview_sources,ImportValidationError
        imported=preview_sources(sources.get('test',[]))
        if not imported['valid']:raise ImportValidationError(imported)
        case_ids=body.get('case_ids',[])
        if not isinstance(case_ids,list) or any(not isinstance(x,str) or not x.strip() for x in case_ids):raise ValueError('invalid use-case scope')
        rid=uuid4().hex;p=self.root/rid;p.mkdir()
        for role in ('RR','SR','test'):
            saved[role]=[]
            for idx,d in enumerate(sources.get(role,[])):
                from .test_sources import decode_source
                content,suffix=decode_source(d,role)
                filename=f'sources/{role}-{idx}{suffix}';target=p/filename;target.parent.mkdir(exist_ok=True);target.write_bytes(content)
                saved[role].append({'path':filename,'name':Path(d['name']).name})
        from .normal_rules import RULESET_VERSION
        meta={'case_ids':case_ids,'id':rid,'name':name,'review_mode':body.get('review_mode','manual'),'created_at':time.time(),'sources':saved,'protocol':PROTOCOL,'ruleset_version':RULESET_VERSION}
        write_json(p/'project.json',meta)
        from .project_review import project_registry
        project_registry(p)
        return meta
    def test_sources(self,rid,body=None):
        from .source_documents import read_documents,read_project_documents
        from .test_sources import preview,decode_source
        p=self.run_dir(rid);meta=read_json(p/'project.json');history=p/'test_source_versions.json'
        versions=read_json(history) if history.exists() else [{'id':fingerprint(meta['sources']['test'])[:20],'sources':meta['sources']['test'],'created_at':meta['created_at']}]
        current=meta.get('test_source_version',versions[-1]['id'])
        if body is not None:
            if rid in self.active or read_job(p).get('status')=='running':raise ValueError('运行期间不能切换测试集')
            if body.get('expected_version')!=current:raise ValueError('测试集已变化，请刷新')
            if body.get('dry_run'):
                from .test_sources import preview_sources
                if body.get('version') and not any(v['id']==body['version'] for v in versions):raise ValueError('未知测试集版本')
                checked=preview_sources(body.get('sources',[])) if not body.get('version') else {'valid':True}
                if not checked['valid']:raise ValueError('测试来源校验失败：'+json.dumps(checked,ensure_ascii=False))
                return {'valid':True,'saved':False,'preview':checked,'expected_version':current}
            if body.get('version'):
                selected=next((x for x in versions if x['id']==body['version']),None)
                if selected is None:raise ValueError('未知测试集版本')
                sources=selected['sources'];current=selected['id']
            else:
                raw=body.get('sources',[])
                if not raw:raise ValueError('请上传测试文件')
                decoded=[(d,decode_source(d,'test')) for d in raw];current=fingerprint([(d['name'],fingerprint(data.hex())) for d,(data,suffix) in decoded])[:20]
                sources=[]
                for idx,(d,(data,suffix)) in enumerate(decoded):
                    filename=f'sources/tests-{current}/test-{idx}{suffix}';target=p/filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                    sources.append({'path':filename,'name':Path(d['name']).name})
                checked=preview(read_project_documents(p,sources,'test'))
                if not checked['valid']:
                    from .test_sources import ImportValidationError
                    raise ImportValidationError(checked)
                if not any(x['id']==current for x in versions):versions.append({'id':current,'sources':sources,'created_at':time.time()})
            import shutil
            archive=p/'run/report_versions'/('test-source-'+str(time.time_ns()))
            for name in ('missing_report.json','missing_report.md','run_manifest.json','workflow_tasks.json','workflow_graph.json'):
                f=p/'run'/name
                if f.exists():archive.mkdir(parents=True,exist_ok=True);shutil.copy2(f,archive/name)
            meta['sources']['test']=sources;meta['test_source_version']=current;write_json(p/'project.json',meta);write_json(history,versions)
        from .result_views import ResultView
        results=ResultView(p)
        return {'version':current,'versions':versions,'preview':preview(read_project_documents(p,meta['sources']['test'],'test')),'sources':meta['sources']['test'],'catalogue':results.payload('test-inventory'),'alignment':results.payload('test-case-align'),'alignment_stale':results.test_source_changed,'requirement_cases':results.cases()}
    def list(self):return sorted([read_json(p) for p in self.root.glob('*/project.json')],key=lambda x:x['created_at'],reverse=True)
    def model_config(self,rid):
        from .model_settings import resolve
        p=self.run_dir(rid)
        value=resolve(read_json(p/'model.local.json') if (p/'model.local.json').exists() else {},self.env_file,self.root)
        value.update(_live_project=str(p),_live_accounts_root=str(self.root),_live_env_file=str(self.env_file));return value
    def model_accounts(self,body=None):
        from .model_accounts import public_accounts,save_account
        if body is not None:
            aid=body.get('id')
            for m in self.list():
                p=self.run_dir(m['id']);c=read_json(p/'model.local.json') if (p/'model.local.json').exists() else {};j=read_job(p)
                if aid and c.get('model_account_id')==aid and (m['id'] in self.active or j.get('status')=='running' and j.get('worker_heartbeat',0)>time.time()-30):raise ValueError('此连接正在执行项目，请结束本轮后修改')
            return save_account(self.root,body,self.env_file)
        return public_accounts(self.root,self.env_file)
    def configure(self,rid,body):
        p=self.run_dir(rid)
        job=read_job(p)
        # Provider settings are read at each future model call. Existing requests keep their own snapshot.
        from .runtime_settings import KEYS,validate_options,PRESETS
        allowed=KEYS|{'model_account_id','base_url','agent_model','api_key','preset'}
        if set(body)-allowed:raise ValueError('不支持的配置键：'+','.join(sorted(set(body)-allowed)))
        previous=read_json(p/'model.local.json') if (p/'model.local.json').exists() else {}
        config=dict(previous)
        if 'model_account_id' in body and body['model_account_id']!=previous.get('model_account_id'):
            # Switching credentials must not inherit routing, provider options or quota files.
            for k in KEYS|{'api_key','api_key_env','base_url','token_budget_ledger','token_budget_limit','provider_token_budget_limit','provider_token_budget_ledgers','provider_token_budget_lock','token_budget_reasoning_reserve'}:config.pop(k,None)
        if 'preset' in body:
            if body['preset'] not in PRESETS:raise ValueError('未知兼容预设')
            config.update(PRESETS[body['preset']])
        if 'model_profiles' in body:
            safe_profile_keys=KEYS-{'model_profiles','task_models','role_models','thinking_override'}
            if not isinstance(body['model_profiles'],dict) or any(not isinstance(v,dict) or set(v)-safe_profile_keys for v in body['model_profiles'].values()):raise ValueError('模型配置只接受公开运行参数，不能修改凭证或配额账本')
            body={**body,'model_profiles':{m:{**config.get('model_profiles',{}).get(m,{}),**v} for m,v in body['model_profiles'].items()}}
        if 'thinking' in body:body={**body,'thinking_override':body['thinking']}
        config.update({k:v for k,v in body.items() if k!='preset' and not (k=='api_key' and not v)})
        if not config.get('agent_model','').strip():raise ValueError('请选择实际模型标识')
        if not config.get('model_account_id') and not (config.get('base_url') or self.model_config(rid).get('base_url','')).startswith(('http://','https://')):raise ValueError('请选择模型连接或填写API地址')
        config.update(agent_runtime='deepagents',structured_output='json_object',max_retries=0,adaptive_concurrency=True)
        config=validate_options(config,defaults=True)
        from .model_settings import resolve
        validated=resolve(config,self.env_file,self.root)
        from .model_routing import routed_config
        for task,role in [('agent','modeler'),('agent','checker'),('agent','recommender')]+[(t,'modeler') for t in config.get('task_models',{})]:routed_config(validated,task,role)
        write_json(p/'model.local.json',config)
        try:(p/'model.local.json').chmod(0o600)
        except OSError:pass
        from .model_settings import public_settings
        return public_settings(validated)
    def upgrade(self,rid):
        import shutil
        p=self.run_dir(rid);meta=read_json(p/'project.json')
        from .normal_rules import RULESET_VERSION
        manifest=read_json(p/'run/run_manifest.json') if (p/'run/run_manifest.json').exists() else {}
        if meta.get('protocol')==PROTOCOL and (meta.get('ruleset_version')==RULESET_VERSION or manifest.get('ruleset_version')==RULESET_VERSION):return rid
        from .concern_alignment import VERSION
        if meta.get('protocol')==PROTOCOL and manifest.get('protocol')==PROTOCOL and manifest.get('matching_version')==VERSION:
            # Same two-layer contract: Execution archives old reports before
            # invalidating only changed tool/input versions. Preserve verified
            # per-node responses, conversations and the request usage audit.
            return rid
        import base64
        sources={k:[{'name':d['name'],**({'content_base64':base64.b64encode((p/d['path']).read_bytes()).decode()} if d['path'].endswith('.xlsx') else {'content':(p/d['path']).read_text(encoding='utf8')})} for d in rows] for k,rows in meta['sources'].items()}
        new=self.create({'name':meta['name']+' · 规则修订版','review_mode':meta['review_mode'],'case_ids':meta.get('case_ids',[]),'sources':sources})
        if (p/'model.local.json').exists():shutil.copy2(p/'model.local.json',self.run_dir(new['id'])/'model.local.json')
        if (p/'run/registry_override.json').exists():shutil.copy2(p/'run/registry_override.json',self.run_dir(new['id'])/'run/registry_override.json')
        if (p/'concern_versions').exists():shutil.copytree(p/'concern_versions',self.run_dir(new['id'])/'concern_versions',dirs_exist_ok=True)
        for name in ('pattern-settings.json','pattern-versions','recommendation-history.json'):
            src=p/name;dst=self.run_dir(new['id'])/name
            if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True)
            elif src.exists():shutil.copy2(src,dst)
        from .positive_reuse import prepare
        prepare(p,self.run_dir(new['id']))
        target=self.run_dir(new['id']);v=read_json(target/'project.json');v['previous_project_id']=rid;write_json(target/'project.json',v)
        return new['id']
    def start(self,rid,options=None):
        if self.review_only:raise ValueError('业务审核包只保存确认记录；请交回研发后重跑')
        if (self.root/'manager-maintenance.json').exists():raise ValueError('程序正在安全重启或回退，暂不接受新执行；请查看管理Agent操作记录')
        rid=self.upgrade(rid)
        from .scheduler import run_lock
        with run_lock(self.run_dir(rid)/'dispatch'):
            return self._start(rid,options)
    def _start(self,rid,options=None):
        if self.review_only:raise ValueError('业务审核包只保存确认记录；请交回研发后重跑')
        rid=self.upgrade(rid)
        p=self.run_dir(rid)
        from .worker_runtime import read_job
        job=read_job(p)
        options=options or {}
        if set(options)-{'case_ids','priority_cases'}:raise ValueError('不支持的运行范围参数')
        for k in ('case_ids','priority_cases'):
            if k in options and (not isinstance(options[k],list) or any(not isinstance(x,str) or not x.strip() for x in options[k])):raise ValueError('用例范围必须为非空编号列表')
        from .worker_runtime import pid_alive
        if job.get('status')=='running' and (job.get('worker_heartbeat',0)>time.time()-30 or job.get('pid') and pid_alive(job['pid'])):raise ValueError('项目正在由联调工作进程执行')
        from .model_settings import resolve
        config=self.model_config(rid)
        if not self.client_factory and (not config['api_key'] or not config['base_url']):raise ValueError('请在.env或项目中配置模型地址和密钥')
        with self.lock:
            if rid in self.active:raise ValueError('项目正在运行')
            self.active.add(rid)
        write_json(p/'job.json',{'status':'running','started_at':time.time(),'worker_heartbeat':time.time(),'run_options':options})
        if self.client_factory or self.worker:self.pool.submit(self._execute,rid)
        else:
            from .worker_runtime import spawn,monitor
            try:process=spawn(self,rid)
            except Exception:
                with self.lock:self.active.discard(rid)
                write_json(p/'job.json',{'status':'error','message':'项目进程启动失败'});raise
            from threading import Thread
            Thread(target=monitor,args=(self,rid,process),daemon=True,name='scene-project-monitor').start()
        return {'status':'running','project_id':rid}
    @project_scoped
    def _execute(self,rid):
        p=self.run_dir(rid)
        try:
            from .workflow import Execution,build_pipeline
            from .source_documents import read_documents,read_project_documents
            from .cli import client_for
            from .scheduler import run_lock
            project=read_json(p/'project.json')
            from .model_settings import resolve
            config=self.model_config(rid)
            config.setdefault('supplement_tests',False)
            config.setdefault('scenario_patterns',True)
            from .pattern_settings import settings,history
            write_json(p/'run/pattern_settings_used.json',settings(p)['settings'])
            write_json(p/'run/recommendation_history_used.json',history(p)['items'])
            config['review_mode']=project['review_mode'];config['run_root']=str(p/'run')
            with run_lock(p/'run'):
                client=self.client_factory(config,p/'run') if self.client_factory else client_for(config,p/'run')
                options=read_json(p/'job.json').get('run_options',{})
                config['priority_cases']=options.get('priority_cases',[])
                ex=Execution(p/'run',mode='external',client=client,config=config,case_ids=options.get('case_ids',project.get('case_ids')))
                self.gates[rid]=ex.gate
                docs={role:read_project_documents(p,project['sources'][role],'test' if role=='test' else 'existing') for role in ('RR','SR','test')}
                build_pipeline(ex,docs['RR'],docs['SR'],docs['test']);manifest=ex.finish()
                write_json(p/'job.json',{'status':'complete' if manifest['complete'] else 'complete_with_questions' if manifest.get('execution_complete') else 'waiting','finished_at':time.time()})
        except Exception as e:
            # Preserve actual diagnostics server-side without returning credentials.
            write_json(p/'job.json',{'status':'error','error_type':type(e).__name__,'message':'执行未完成，请查看任务状态与运行日志','finished_at':time.time()})
            import traceback
            (p/'error.log').write_text(traceback.format_exc(),encoding='utf8')
        finally:
            with self.lock:self.active.discard(rid)
    def execution_status(self,rid):
        p=self.run_dir(rid);r=p/'run';project=read_json(p/'project.json')
        graph=read_json(r/'workflow_graph.json') if (r/'workflow_graph.json').exists() else {'nodes':[]};nodes={n['id']:n for n in graph['nodes']}
        records=read_json(r/'workflow_tasks.json').get('tasks',{}) if (r/'workflow_tasks.json').exists() else {};active={k:v for k,v in records.items() if k in nodes}
        from .worker_runtime import read_job
        job=read_job(p)
        if job['status']=='running' and rid not in self.active and job.get('worker_heartbeat',0)<time.time()-30:job={'status':'interrupted','message':'执行进程已退出，可继续运行'}
        manifest=read_json(r/'run_manifest.json') if (r/'run_manifest.json').exists() else {}
        from .execution_events import EventStore
        from .project_review import pending_view
        review=pending_view(p,queue='all',limit=1)
        unresolved=review['counts'].get('unresolved',0)+review['counts'].get('needs_info',0)
        return {'project':rid,'name':project['name'],'job':job,'complete':bool(manifest.get('complete')),'execution_complete':bool(manifest.get('execution_complete',manifest.get('complete'))),'review_complete':not unresolved,'unresolved_questions':unresolved,'review_only':self.review_only,'completed':sum(v['status']=='passed' for v in active.values()),'total':len(nodes),'event_cursor':EventStore(r).latest_id(),'pending_nodes':[{'id':k,'stage':v['stage'],'status':v['status'],'failure':v.get('failure'),'expected_files':nodes[k].get('expected_files',[])} for k,v in active.items() if v['status']!='passed']}
    def snapshot(self,rid):
        p=self.run_dir(rid);run=p/'run'
        from .reviews import Reviews
        reviews=[]
        for f in (run/'reviews').glob('*.json'):
            v=read_json(f);reviews.append({k:x for k,x in v.items() if k not in {'inputs','payload'}})
        artifacts=[{'path':str(f.relative_to(p)).replace('\\','/'),'name':f.name,'bytes':f.stat().st_size} for folder in (run/'artifacts',run/'reviews/previews',run/'report_versions') for f in folder.rglob('*') if f.is_file()]
        records=read_json(run/'workflow_tasks.json')['tasks'] if (run/'workflow_tasks.json').exists() else {}
        prefixes={}
        for key,record in records.items():
            case=record.get('case','shared');stem=(key if case=='shared' else key[len(case)+1:]).replace(':','--')
            prefixes['run/artifacts/'+('shared' if case=='shared' else fingerprint(case)[:12])+'/'+stem]=key
            preview_stem=record['stage'] if ':' in key else key
            prefixes['run/reviews/previews/'+fingerprint(key)+'/'+preview_stem]=key
        for artifact in artifacts:
            artifact['task_key']=next((key for prefix,key in prefixes.items() if artifact['path'].startswith(prefix+'.')),None)
        artifacts=[a for a in artifacts if '/reviews/previews/' not in a['path'] or records.get(a.get('task_key'),{}).get('status') in {'passed','awaiting_review'}]
        for name in ('missing_report.json','missing_report.md'):
            if (run/name).exists():artifacts.append({'path':'run/'+name,'name':name,'bytes':(run/name).stat().st_size})
        from .worker_runtime import read_job
        job=read_job(p)
        if job['status']=='running' and rid not in self.active and job.get('worker_heartbeat',0)<time.time()-30:job={'status':'interrupted','message':'上次进程已退出，可继续运行并复用成功结果'}
        from .model_settings import resolve,public_settings
        try:config=public_settings(self.model_config(rid))
        except ValueError as e:
            raw=read_json(p/'model.local.json') if (p/'model.local.json').exists() else {}
            config={k:raw[k] for k in ('model_account_id','agent_model','max_concurrency','max_tokens') if k in raw}
            config.update(credential_configured=False,configuration_error=str(e))
        from .project_review import pending_view
        questions=pending_view(p,queue='all',limit=1)
        return {'project':read_json(p/'project.json'),'job':job,'manifest':read_json(run/'run_manifest.json') if (run/'run_manifest.json').exists() else None,
          'tasks':read_json(run/'workflow_tasks.json') if (run/'workflow_tasks.json').exists() else {'tasks':{},'events':[]},'reviews':reviews,'artifacts':artifacts,
          'config':config,'review_only':self.review_only,'review_summary':{'unresolved':questions['counts'].get('unresolved',0)+questions['counts'].get('needs_info',0),'counts':questions['counts']}}
    def conversation(self,rid,key):
        from .node_conversations import Conversations
        p=self.run_dir(rid)
        graph=read_json(p/'run/workflow_graph.json') if (p/'run/workflow_graph.json').exists() else {'nodes':[]}
        tasks=read_json(p/'run/workflow_tasks.json').get('tasks',{}) if (p/'run/workflow_tasks.json').exists() else {}
        if key not in tasks and key not in {n['id'] for n in graph['nodes']}:raise ValueError('请选择已创建的实际节点')
        store=Conversations(p/'run');return store
    def guide(self,rid,key,text):
        store=self.conversation(rid,key);row=store.append(key,'guidance',text)
        tasks=read_json(self.run_dir(rid)/'run/workflow_tasks.json').get('tasks',{})
        if tasks.get(key,{}).get('status') not in {'running','awaiting_answer'}:
            store.invalidate(key)
            self.pool.submit(self._dialogue,rid,key)
        return row
    @project_scoped
    def _dialogue(self,rid,key):
        with self.lock:
            if (rid,key) in self.dialogue_active:return
            self.dialogue_active.add((rid,key))
        from .model_settings import resolve
        from .cli import client_for
        from .execution_events import EventStore,bind,emit
        p=self.run_dir(rid);store=self.conversation(rid,key)
        try:
            packets=[]
            for f in (p/'run/packets').glob('*.json'):
                value=read_json(f)
                if value.get('node_key')==key:packets.append((f.stat().st_mtime,value))
            task_packet=max(packets,key=lambda a:a[0])[1] if packets else None
            if not task_packet:
                store.append(key,'assistant','指导已保存，将在该节点下一次模型调用时生效。');return
            config=self.model_config(rid)
            from .model_routing import routed_config
            from .deepagents_client import role_for
            config=routed_config(config,task_packet['task'],role_for(task_packet['task'])) or config
            client=client_for(config,p/'run')
            from .indexed_context import EvidenceContext
            from .deepagents_client import compact_input
            context_packet=EvidenceContext(task_packet).packet if config.get('indexed_context',False) else task_packet
            messages=[{'role':'system','content':'你是该节点的业务对话助手。只根据允许任务包回答指导和疑问。不得读取其他任务、E、GT或比较答案，不修改或伪造正式产物；需要重做时说明点击重新执行本节点。'},
              {'role':'user','content':'允许任务上下文：'+json.dumps({'task':context_packet['task'],'input':compact_input(context_packet['input'])},ensure_ascii=False,separators=(',',':'))}]
            messages += [{'role':'assistant' if m['kind']=='assistant' else 'user','content':m['text']} for m in store.list(key)[-20:] if m['kind'] in {'assistant','guidance','answer'}]
            with bind(EventStore(p/'run'),task_key=key,role='dialogue',case='node',attempt=0,model_call_id='dialogue-'+uuid4().hex):
                body={'model':client.model('agent'),'messages':messages,'max_tokens':client.output_limit('dialogue'),'stream':config.get('stream',True)}
                if body['stream'] and config.get('stream_usage',True):body['stream_options']={'include_usage':True}
                from .runtime_settings import request_options
                body=request_options(body,config,'dialogue')
                emit('request_started',requested_model=body['model'],purpose='dialogue',input_bytes=len(json.dumps(body,ensure_ascii=False).encode()))
                from .scheduler import CallGate
                gate=self.gates.setdefault(rid,CallGate(config.get('max_concurrency',1)))
                try:response=gate.call(client.post,'/chat/completions',body)
                except Exception as e:
                    emit('request_failed',requested_model=body['model'],diagnostic=getattr(e,'response_diagnostic',getattr(e,'details',{})))
                    raise
                emit('request_finished',requested_model=body['model'],provider_model=response.get('model'),usage=response.get('usage'))
                store.append(key,'assistant',response['choices'][0]['message'].get('content') or '回复为空；指导仍已保存。')
        except Exception as e:
            store.append(key,'system','对话未完成：'+type(e).__name__+'；指导已保存，可稍后重试。')
        finally:
            with self.lock:self.dialogue_active.discard((rid,key))
    def _resume(self,rid):
        while rid in self.active:time.sleep(.2)
        try:self.start(rid)
        except ValueError:pass
    def export(self,rid):
        from .api_catalog import saved_catalog,save_catalog
        with self.lock:save_catalog(self.run_dir(rid)/'run',saved_catalog(self.run_dir(rid)/'run'))
        p=self.run_dir(rid);stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            for f in p.rglob('*'):
                if not f.is_file() or f.name.endswith(('.local.json','.lock')) or f.name=='error.log' or 'manager' in f.relative_to(p).parts or 'execution_events.sqlite3' in f.name or any(s in f.parts for s in ('model_cache','native')):continue
                z.write(f,str(f.relative_to(p)))
            if (p/'run/execution_events.sqlite3').exists():
                from .execution_events import EventStore
                z.writestr('run/execution_events.jsonl',''.join(EventStore(p/'run').dump_jsonl()))
                from .node_conversations import Conversations
                tasks=read_json(p/'run/workflow_graph.json').get('nodes',[]) if (p/'run/workflow_graph.json').exists() else []
                z.writestr('run/node_conversations.json',json.dumps({n['id']:Conversations(p/'run').list(n['id']) for n in tasks},ensure_ascii=False))
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
        if service.review_only and request.method not in {'GET','HEAD','OPTIONS'}:
            import re
            allowed=re.fullmatch(r'/api/projects/[a-f0-9]{32}/(?:pending/[a-f0-9]+|recommendations/feedback)',request.url.path)
            if not allowed and request.url.path!='/api/runtime/control':return Response(json.dumps({'detail':'业务审核模式禁止模型执行和配置变更；请导出反馈交回研发'},ensure_ascii=False),status_code=403,media_type='application/json')
        # Local UI writes are same-origin; cross-site forms must not start model jobs.
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return Response('Origin mismatch',status_code=403)
        try:
            import re
            from contextlib import nullcontext
            from .concern_registry import registry_scope
            from .project_review import project_registry
            match=re.match(r'/api/projects/([a-f0-9]{32})(?:/|$)',request.url.path)
            scope=registry_scope(project_registry(service.run_dir(match[1]))) if match else nullcontext()
            with scope:return await call_next(request)
        except ValueError as e:return Response(json.dumps({'detail':str(e),**({'import_preview':e.import_preview} if hasattr(e,'import_preview') else {})},ensure_ascii=False),status_code=400,media_type='application/json')
    @app.get('/')
    def index():return FileResponse(WEB/'index.html')
    if (WEB/'assets').exists():app.mount('/assets',StaticFiles(directory=WEB/'assets'),name='assets')
    app.mount('/static',StaticFiles(directory=WEB),name='static')
    @app.get('/api/projects')
    def projects():return service.list()
    @app.get('/api/capabilities')
    def capabilities():
        from .workbench_cli import capabilities
        return {**capabilities(),'review_only':service.review_only}
    @app.post('/api/projects')
    def create(body:dict):return service.create(body)
    @app.post('/api/test-sources/preview')
    def preview_tests(body:dict):
        from .test_sources import preview_sources
        return preview_sources(body.get('sources',[]))
    @app.get('/api/test-sources/template')
    def test_template():
        path=PROJECT/'examples/tests/mall-exception-tests.xlsx'
        if not path.exists():raise HTTPException(404,'测试示例尚未安装')
        return FileResponse(path,filename='mall-exception-tests.xlsx')
    @app.get('/api/projects/{rid}/test-sources')
    def get_test_sources(rid:str):return service.test_sources(rid)
    @app.get('/api/projects/{rid}/test-sources/supplement')
    def get_test_supplement(rid:str,case:str|None=None):
        from .result_views import ResultView
        v=ResultView(service.run_dir(rid));cases=v.cases()
        if case and case not in {c['id'] for c in cases}:raise ValueError('未知用例')
        return {'cases':cases,'case':case,'status':v.state.get((case or '')+':test-supplement',{}).get('status','not_ready'),'tests':v.payload(case+':test-supplement').get('tests',[]) if case else [],'pending':v.payload(case+':test-supplement').get('pending',[]) if case else [],'source':'独立正向材料补全，自动GT；未读取G/E'}
    @app.put('/api/projects/{rid}/test-sources')
    def put_test_sources(rid:str,body:dict):return service.test_sources(rid,body)
    @app.get('/api/registry')
    def definitions():return registry()
    @app.get('/api/projects/{rid}')
    def snapshot(rid:str):return service.snapshot(rid)
    @app.get('/api/projects/{rid}/registry')
    def project_definitions(rid:str,version:str|None=None):
        from .project_review import registry_view
        return registry_view(service.run_dir(rid),version)
    @app.get('/api/projects/{rid}/patterns')
    def pattern_settings(rid:str,version:str|None=None):
        from .pattern_settings import settings
        return settings(service.run_dir(rid),version)
    @app.put('/api/projects/{rid}/patterns')
    def edit_pattern_settings(rid:str,body:dict):
        from .pattern_settings import save_settings
        p=service.run_dir(rid)
        job=read_job(p)
        if rid in service.active or job.get('status')=='running' and job.get('worker_heartbeat',0)>time.time()-30:raise ValueError('运行中请等待本轮结束后修改模式设置')
        with service.lock:return save_settings(p,body)
    @app.get('/api/projects/{rid}/recommendation-history')
    def recommendation_history(rid:str):
        from .pattern_settings import history
        return history(service.run_dir(rid))
    @app.post('/api/projects/{rid}/recommendation-history')
    def import_recommendation_history(rid:str,body:dict):
        from .pattern_settings import import_history
        with service.lock:return import_history(service.run_dir(rid),body)
    @app.get('/api/projects/{rid}/recommendations')
    def recommendations(rid:str,case:str|None=None,test_set:str='expanded'):
        from .pattern_settings import settings,adoption,history
        from .result_views import ResultView
        p=service.run_dir(rid);v=ResultView(p)
        if case and case not in {c['id'] for c in v.cases()}:raise ValueError('未知用例')
        result=v.payload(case+':gap-recommend') if case else {}
        matrix=v.payload(case+':pattern-applicability') if case else {}
        if test_set not in {'original','expanded','business'}:raise ValueError('未知测试集')
        evaluation=v.payload(case+':exception-evaluation') if case else {}
        if test_set=='original':evaluation=evaluation.get('original_evaluation',evaluation)
        business=None
        if case and test_set=='business':
            from .business_truth import snapshot
            business=snapshot(p,case);evaluation=business['evaluation']
        from .recommendation import comparison_for_view
        comparison=comparison_for_view(evaluation,result)
        from .business_truth import candidates
        return {'cases':v.cases(),'case':case,'result':result,'matrix':matrix,'comparison':comparison,'evaluation_metrics':evaluation.get('metrics',{}),'test_set':test_set,'current_settings_hash':settings(p)['version'],'human_adoption':adoption(p,result),'business_truth':business,
                'feedback':history(p)['feedback'],'feedback_revision':history(p)['revision'],
                'duplicate_candidates':{s['id']:[{'id':t['id'],'conditions':t.get('conditions',[])} for t in candidates(s,evaluation.get('GT',[]))] for s in result.get('Q',[])}}
    @app.post('/api/projects/{rid}/recommendations/feedback')
    def recommendation_feedback(rid:str,body:dict):
        from .pattern_settings import feedback
        from .result_views import ResultView
        p=service.run_dir(rid);result=ResultView(p).payload(str(body.get('case_id',''))+':gap-recommend')
        if not result.get('enabled'):raise ValueError('本用例尚未形成推荐')
        if body.get('choice')=='adopt' and 'reviewer' in body and not str(body['reviewer']).strip():raise ValueError('请填写审核人')
        with service.lock:
            value=feedback(p,body,result,dry_run=body.get('dry_run',False))
            if not body.get('dry_run'):
                from .business_truth import snapshot
                value={**value,'business_truth':snapshot(p,body['case_id'])}
            return value
    @app.post('/api/projects/{rid}/patterns/review')
    def pattern_review(rid:str,body:dict):
        from .pattern_settings import review_candidate
        from .result_views import ResultView
        p=service.run_dir(rid)
        job=read_job(p)
        if rid in service.active or job.get('status')=='running' and job.get('worker_heartbeat',0)>time.time()-30:raise ValueError('请等待本轮结束后审核模式前提')
        matrix=ResultView(p).payload(str(body.get('case_id',''))+':pattern-applicability')
        if not matrix:raise ValueError('本用例尚未形成模式适用性产物')
        with service.lock:return review_candidate(p,body,matrix)
    @app.get('/api/projects/{rid}/results')
    def results_index(rid:str):
        from .result_views import ResultView
        return ResultView(service.run_dir(rid)).index()
    @app.get('/api/projects/{rid}/results/metrics')
    def results_metrics(rid:str,test_set:str='expanded'):
        from .result_views import ResultView
        return ResultView(service.run_dir(rid)).metrics(test_set)
    @app.get('/api/projects/{rid}/results/{case_id}')
    def results_case(rid:str,case_id:str,test_set:str='expanded'):
        from .result_views import ResultView
        return ResultView(service.run_dir(rid)).detail(case_id,test_set)
    @app.get('/api/projects/{rid}/results/{case_id}/scenarios/{channel}/{scenario_id}')
    def result_scenario(rid:str,case_id:str,channel:str,scenario_id:str,test_set:str='expanded'):
        from .result_views import ResultView
        return ResultView(service.run_dir(rid)).scenario(case_id,channel,scenario_id,test_set)
    @app.put('/api/projects/{rid}/registry')
    def edit_project_definitions(rid:str,body:dict):
        from .project_review import save_registry
        p=service.run_dir(rid);job=read_job(p)
        if rid in service.active or job.get('status')=='running' and job.get('worker_heartbeat',0)>time.time()-30:raise ValueError('请等待当前执行轮完成再发布关注点版本')
        with service.lock:return save_registry(p,body)
    @app.get('/api/projects/{rid}/pending')
    def pending_review_items(rid:str,status:str='unresolved',case:str|None=None,offset:int=0,limit:int=50,search:str='',channel:str|None=None,queue:str='business'):
        from .project_review import pending_view
        with service.lock:return pending_view(service.run_dir(rid),status,case,offset,limit,search,channel,queue)
    @app.post('/api/projects/{rid}/pending/{item_id}')
    def review_pending_item(rid:str,item_id:str,body:dict):
        from .project_review import decide_pending,pending_items
        with service.lock:
            if 'reviewer' not in body:return decide_pending(service.run_dir(rid),item_id,body)
            from .review_questions import answer
            item=next((i for i in pending_items(service.run_dir(rid)) if i['id']==item_id),None)
            if item is None:raise ValueError('问题已变化，请刷新')
            return answer(service.run_dir(rid),item,body,dry_run=body.get('dry_run',False))
    @app.get('/api/model-accounts')
    def model_accounts():return service.model_accounts()
    @app.put('/api/model-accounts')
    def save_model_account(body:dict):
        with service.lock:return service.model_accounts(body)
    @app.get('/api/projects/{rid}/node-repair')
    def repair_context(rid:str,task_key:str):
        from .node_repair import export_repair
        return export_repair(service.run_dir(rid),task_key)
    @app.post('/api/projects/{rid}/node-repair')
    def repair_submit(rid:str,body:dict):
        from .node_repair import submit_repair
        from .scheduler import run_lock
        p=service.run_dir(rid)
        if rid in service.active:raise ValueError('请等待本轮执行结束再提交修复，导出和校验不会调用模型')
        with service.lock,run_lock(p/'run'):return submit_repair(p,body['task_key'],body['repair'],validate_only=body.get('validate_only',False))
    @app.get('/api/projects/{rid}/config')
    def effective_config(rid:str,task:str='agent',task_key:str|None=None):
        from .model_diagnostics import effective
        if task_key:
            p=service.run_dir(rid)/'run/workflow_tasks.json'
            record=read_json(p).get('tasks',{}).get(task_key) if p.exists() else None
            if not record:raise ValueError('未知执行节点')
            task=record['stage']
        return effective(service.model_config(rid),task)
    @app.get('/api/projects/{rid}/diagnostics')
    def diagnostics(rid:str,task_key:str|None=None,limit:int=20):
        from .model_diagnostics import node_diagnostics
        if not 1<=limit<=100:raise ValueError('limit范围1至100')
        return node_diagnostics(service.run_dir(rid),service.model_config(rid),task_key,limit)
    @app.put('/api/projects/{rid}/config')
    def configure(rid:str,body:dict):return service.configure(rid,body)
    @app.put('/api/projects/{rid}/mode')
    def mode(rid:str,body:dict):
        if rid in service.active:raise ValueError('运行期间不能切换模式')
        if body.get('review_mode') not in {'manual','auto'}:raise ValueError('invalid review mode')
        p=service.run_dir(rid);v=read_json(p/'project.json');v['review_mode']=body['review_mode'];write_json(p/'project.json',v);return v
    @app.post('/api/projects/{rid}/run')
    def start(rid:str,body:dict|None=None):return service.start(rid,body)
    @app.get('/api/projects/{rid}/execution-status')
    def execution_status(rid:str):return service.execution_status(rid)
    @app.get('/api/projects/{rid}/graph')
    def graph(rid:str):
        from .execution_graph import graph_snapshot
        return graph_snapshot(service.run_dir(rid)/'run')
    @app.get('/api/projects/{rid}/context')
    def model_context(rid:str,task_key:str):
        root=service.run_dir(rid)/'run';chosen=None
        pointer=root/'context_index'/(fingerprint(task_key)+'.json')
        if pointer.exists():
            relative=read_json(pointer).get('path','');target=(root/relative).resolve()
            if target.is_relative_to(root.resolve()) and target.is_file():chosen=read_json(target)
        if chosen is None:
            for f in sorted((root/'model_contexts').glob('*.json'),key=lambda f:f.stat().st_mtime,reverse=True):
                v=read_json(f)
                if v.get('node_key')==task_key:
                    chosen=v;write_json(pointer,{'path':str(f.relative_to(root))});break
        if chosen is None:return Response(json.dumps({'status':'未准备模型上下文','task_key':task_key},ensure_ascii=False),media_type='application/json')
        return Response(json.dumps(chosen,ensure_ascii=False,indent=2),media_type='application/json')
    @app.get('/api/projects/{rid}/usage')
    def usage(rid:str,format:str='json',view:str='summary',task_key:str|None=None,role:str|None=None,model:str|None=None,case:str|None=None,search:str='',offset:int=0,limit:int=50,after:float|None=None,session_id:str|None=None,account:str|None=None,sort:str='tokens'):
        from .usage_index import indexed_usage,usage_csv
        project=service.run_dir(rid);prices=read_json(project/'usage_prices.json') if (project/'usage_prices.json').exists() else {}
        report=indexed_usage(project/'run',view='export' if format in {'csv','download'} else view,
            task_key=task_key,role=role,model=model,case=case,search=search,offset=offset,limit=limit,after=after,prices=prices,session_id=session_id,account=account,sort=sort)
        if format=='csv':return Response(usage_csv(report),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="task-usage.csv"'})
        if format not in {'json','download'}:raise ValueError('usage format must be json, download or csv; use the embedded workbench view')
        return Response(json.dumps(report,ensure_ascii=False),media_type='application/json')
    @app.put('/api/projects/{rid}/usage/prices')
    def usage_prices(rid:str,body:dict):
        import math
        project=service.run_dir(rid);prices={}
        for model,price in body.items():
            if not isinstance(model,str) or not model.strip() or not isinstance(price,dict) or set(price)-{'input','cached_input','output'} or not {'input','output'}<=set(price):raise ValueError('按模型填写每百万Token输入/输出单价，币种为人民币')
            if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in price.values()):raise ValueError('单价必须是非负有限数值')
            prices[model]=price
        write_json(project/'usage_prices.json',prices)
        return {'prices':prices,'currency':'CNY','unit':'每百万Token','status':'仅用于估算，不是实际账单'}
    @app.get('/api/projects/{rid}/events/history')
    def history(rid:str,after:int=0,task_key:str|None=None,limit:int=500):
        from .execution_events import EventStore
        return {'events':EventStore(service.run_dir(rid)/'run').read(after,task_key=task_key,limit=limit)}
    @app.get('/api/projects/{rid}/events')
    async def events(rid:str,request:Request,after:int=0,tail:bool=False):
        from .execution_events import EventStore
        from fastapi.responses import StreamingResponse
        import asyncio
        store=EventStore(service.run_dir(rid)/'run')
        try:cursor=max(after,int(request.headers.get('Last-Event-ID','0')))
        except ValueError:raise HTTPException(400,'invalid event cursor')
        fresh_tail=tail and cursor==0
        if fresh_tail:cursor=store.latest_id()
        async def stream():
            nonlocal cursor
            if fresh_tail:
                # Establish a resume cursor without replaying all model deltas.
                # Node history is loaded separately when a node is selected.
                yield 'id: '+str(cursor)+'\nevent: cursor\ndata: '+json.dumps({'id':cursor})+'\n\n'
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
    @app.get('/api/projects/{rid}/conversation')
    def conversation(rid:str,task_key:str):
        store=service.conversation(rid,task_key)
        return {'messages':store.list(task_key),'question':store.pending(task_key),'revision':store.revision(task_key)}
    @app.post('/api/projects/{rid}/conversation')
    def guidance(rid:str,body:dict):
        if body.get('dry_run'):
            service.conversation(rid,body['task_key'])
            if not isinstance(body.get('text'),str) or not body['text'].strip() or len(body['text'])>30000:raise ValueError('消息不能为空或超过30000字符')
            return {'valid':True,'saved':False}
        return service.guide(rid,body['task_key'],body['text'])
    @app.post('/api/projects/{rid}/answer')
    def answer(rid:str,body:dict):
        store=service.conversation(rid,body['task_key'])
        if body.get('dry_run'):
            q=store.pending(body['task_key'])
            if not q or q['detail']['question_id']!=body['question_id']:raise ValueError('问题已变化，请刷新')
            if not isinstance(body.get('text'),str) or not body['text'].strip() or len(body['text'])>30000:raise ValueError('回答不能为空或超过30000字符')
            return {'valid':True,'saved':False}
        value=store.answer(body['task_key'],body['question_id'],body['text'])
        return value
    @app.post('/api/projects/{rid}/rerun-node')
    def rerun(rid:str,body:dict):
        if rid in service.active:raise ValueError('请等待当前执行轮结束；运行中指导会在下一次模型调用生效')
        store=service.conversation(rid,body['task_key'])
        if store.pending(body['task_key']):raise ValueError('请先回答当前问题')
        store.append(body['task_key'],'guidance',body.get('text') or '根据本节点最新指导重新执行并生成审核稿。')
        store.invalidate(body['task_key'])
        return service.start(rid)
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
          expected_input_hash=body['input_hash'],value=body.get('payload'),comment=body.get('comment',''),dry_run=body.get('dry_run',False))
    @app.get('/api/projects/{rid}/api-catalog')
    def api_catalog(rid:str,format:str='view'):
        from .api_catalog import saved_catalog,save_catalog,markdown
        if format not in {'view','json','md'}:raise HTTPException(400,'unsupported format')
        with service.lock:
            catalog=saved_catalog(service.run_dir(rid)/'run');save_catalog(service.run_dir(rid)/'run',catalog)
        if format=='view':return catalog
        return Response(markdown(catalog) if format=='md' else json.dumps(catalog,ensure_ascii=False,indent=2),
          media_type='text/markdown' if format=='md' else 'application/json',
          headers={'Content-Disposition':f'attachment; filename="api-catalog.{format}"'})
    @app.get('/api/projects/{rid}/file')
    def file(rid:str,path:str):
        p=service.run_dir(rid);f=(p/path).resolve()
        if not f.is_relative_to(p) or not f.is_file() or f.name.endswith(('.local.json','.lock')):raise HTTPException(404,'file unavailable')
        if not (path.startswith('run/artifacts/') or path.startswith('run/reviews/previews/') or path.startswith('run/report_versions/') or path.startswith('sources/') or path.startswith('imports/files/') and ('/original/' in path or not f.name.endswith('record.json')) or path in {'run/missing_report.json','run/missing_report.md'}):raise HTTPException(404,'file unavailable')
        return FileResponse(f)
    @app.get('/api/projects/{rid}/export')
    def export(rid:str):return Response(service.export(rid),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="scene-review.zip"'})
    from .manager_api import register as register_manager
    register_manager(app,service)
    from .review_api import register
    register(app,service,PROJECT)
    from .input_gateway import register as register_inputs,InputWatcher
    register_inputs(app,service)
    @app.on_event('startup')
    def start_input_watcher():
        if not service.review_only and not service.worker:
            from .worker_runtime import Guardian
            service.input_watcher=InputWatcher(service);service.guardian=Guardian(service)
            from .manager_runtime import ManagerHost
            service.manager_host=ManagerHost(service)
    @app.on_event('shutdown')
    def stop_input_watcher():
        if service.input_watcher:service.input_watcher.close()
        if service.guardian:service.guardian.close()
        if service.manager_host:service.manager_host.close()
    return app
