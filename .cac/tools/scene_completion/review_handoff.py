"""Portable source lookup, immutable handoff snapshots and auditable feedback.

The business package has no execution credentials or model caches. Importing
feedback only saves decisions; applying them and starting models is separate.
"""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import io, json, zipfile, sqlite3, tempfile, hashlib, time
from .storage import read_json, write_json, fingerprint
from .review_questions import load, bindings, VERSION


def source_documents(project):
    project=Path(project);pinned=project/'review_sources.json'
    if pinned.exists():return read_json(pinned)['documents']
    from .source_documents import read_project_documents
    meta=read_json(project/'project.json');out=[]
    from .result_views import ResultView
    old=ResultView(project).payload('source-index').get('documents',[])
    for role,entries in meta['sources'].items():
        for entry in entries:
            path=(project/entry['path']).resolve()
            if not path.is_relative_to(project.resolve()):raise ValueError('来源文档超出项目目录')
            for doc in read_project_documents(project,[entry],'test' if role=='test' else 'existing'):
                candidates=[o for o in old if o['name']==doc['name']]
                ids={doc['source_id']}|{o['source_id'] for o in candidates}
                for sid in ids:out.append({**doc,'source_id':sid,'role':role,'path':entry['path'],'file_hash':hashlib.sha256(path.read_bytes()).hexdigest()})
    # Imported citations remain available across file edits and installation paths.
    from .artifact_imports import snapshot
    versions=list(project.glob('imports/versions/*/*.json'))
    imported=snapshot(project)+[read_json(f) for f in versions]
    for item in imported:
        original=project/item['original']
        if not original.is_file():continue
        if original.suffix.lower()!='.xlsx':
            raw={'source_id':'import-raw-'+item['id'],'name':item['name'],'channel':'normal','role':item['role'],'path':item['original'],'file_hash':hashlib.sha256(original.read_bytes()).hexdigest(),'lines':[{'number':n,'text':v} for n,v in enumerate(original.read_text(encoding='utf-8-sig').splitlines(),1)]}
            if not any(d['source_id']==raw['source_id'] for d in out):out.append(raw)
        for artifact in item['artifacts']:
            doc=artifact['document']
            if not any(d['source_id']==doc['source_id'] for d in out):out.append({**doc,'role':'colleague_artifact','derived_from':'import-raw-'+item['id'],'original_path':item['original'],'conversion_source_refs':artifact.get('conversion_source_refs',[])})
    from .review_questions import materials
    applied=load(project,'pending_decisions.json',{'items':{}})['items']
    for node in {k for r in applied.values() for k in r.get('origins',[])}:
        for doc in materials(project,node):
            if not any(d['source_id']==doc['source_id'] for d in out):out.append(doc)
    return out


def sources(project):
    return {'documents':[{k:v for k,v in d.items() if k!='lines'}|{'line_count':len(d['lines'])} for d in source_documents(project)]}


def source_view(project,sid,start=1,end=None,context=40,quote='',view='window'):
    if view not in {'window','document'}:raise ValueError('原文视图仅支持window或document')
    docs=source_documents(project);doc=next((d for d in docs if d['source_id']==sid),None)
    if doc is None and quote:
        # Legacy absolute-path IDs can be recovered only by a unique exact
        # quotation at the same original coordinates, not by guessed filenames.
        candidates=[d for d in docs if '\n'.join(r['text'] for r in d['lines'] if start<=r['number']<=(end or start)).strip()==quote.strip()]
        unique={fingerprint(d['lines']):d for d in candidates}
        if len(unique)==1:doc=next(iter(unique.values()))
    if doc is None:raise ValueError('来源ID无法定位；请核对快照，不根据模型文字猜测文档')
    if not 1<=start<=max(1,len(doc['lines'])) or not start<=(end or start) or (end or start)-start>1000 or not 0<=context<=200:raise ValueError('无效原文行范围')
    if doc.get('path'):
        p=(Path(project)/doc['path']).resolve()
        if not p.is_relative_to(Path(project).resolve()) or not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=doc['file_hash']:raise ValueError('来源文档与审核快照不一致')
    if view=='document' and sum(len(r['text'].encode('utf-8'))+1 for r in doc['lines'])>2_000_000:
        raise ValueError('文档超过2MB，请切换源码按行查看；阅读视图不会静默截断原文')
    lo=1 if view=='document' else max(1,start-context)
    hi=len(doc['lines']) if view=='document' else min(len(doc['lines']),(end or start)+context)
    headings=[r for r in doc['lines'] if r['number']<=start and r['text'].lstrip().startswith('#')]
    return {k:v for k,v in doc.items() if k!='lines'}|{'lines':[r for r in doc['lines'] if lo<=r['number']<=hi], 'highlight_start':start,'highlight_end':end or start,'line_count':len(doc['lines']),'section':headings[-1]['text'] if headings else doc['name'],'view':view,'document_format':'markdown' if Path(doc['name']).suffix.lower() in {'.md','.markdown'} else 'text'}


def source_hash(project):
    meta=read_json(Path(project)/'project.json')
    return fingerprint([(role,d['path'],hashlib.sha256((Path(project)/d['path']).read_bytes()).hexdigest()) for role,rows in sorted(meta['sources'].items()) for d in rows])


def review_snapshot(project):
    from .project_review import pending_items,decisions
    from .pattern_settings import history
    from .result_views import ResultView
    p=Path(project);view=ResultView(p);questions=pending_items(p);recommendations={c['id']:view.payload(c['id']+':gap-recommend') for c in view.cases()}
    current=decisions(p);hist=history(p)
    snap={'version':VERSION,'project_id':read_json(p/'project.json')['id'],'source_hash':source_hash(p),
          'questions':{q['id']:{'origin_bindings':q['origin_bindings'],'item_hash':fingerprint({k:v for k,v in q.items() if k not in {'decision','created_at'}}),'base_revision':current['items'].get(q['id'],{}).get('revision',0)} for q in questions},
          'recommendations':{cid:{'run_id':r.get('run_id'),'settings_hash':r.get('settings_hash'),'scenario_hashes':{s['id']:fingerprint(s) for s in r.get('Q',[])}} for cid,r in recommendations.items()},
          'answer_history_count':len(current['history']),'feedback_history_count':len(hist['feedback']),
          'base_feedback_ids':[r['id'] for r in hist['feedback']], 'manifest_hash':fingerprint(view.manifest)}
    snap['snapshot_id']=fingerprint(snap);snap['created_at']=datetime.now(timezone.utc).isoformat()
    return snap


def project_archive(project):
    """An allow-list, not a credential blacklist. Rebuild a minimal review DB."""
    p=Path(project);snap=review_snapshot(p);stream=io.BytesIO()
    roots={'sources','concern_versions','pattern-versions','business_truth_versions'}
    root_files={'project.json','job.json','pending_decisions.json','business_questions.json','review_applied.json','pattern-settings.json','recommendation-history.json','test_source_versions.json'}
    run_dirs={'artifacts','task_outputs','report_versions','registry_used','reviews','test_catalogues'}
    run_files={'workflow_tasks.json','workflow_graph.json','run_manifest.json','registry_override.json','pattern_settings_used.json','missing_report.json','missing_report.md','execution_sessions.json'}
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for f in p.rglob('*'):
            if not f.is_file() or not f.resolve().is_relative_to(p.resolve()):continue
            rel=f.relative_to(p);parts=rel.parts
            if (parts[0]=='quality-diagnostics' and len(parts)==3 and parts[2]=='report.json') or parts[0] in roots or parts[0]=='imports' and len(parts)>1 and parts[1] in {'files','versions'} or (len(parts)==1 and f.name in root_files) or (parts[0]=='run' and len(parts)>1 and (parts[1] in run_dirs or len(parts)==2 and f.name in run_files)):
                if f.name.endswith(('.local.json','.lock')) or '__pycache__' in parts:continue
                z.write(f,rel.as_posix())
        z.writestr('review_snapshot.json',json.dumps(snap,ensure_ascii=False))
        z.writestr('review_sources.json',json.dumps({'documents':source_documents(p)},ensure_ascii=False))
        # SQLite backup is consistent, then only safe conversation tables are
        # retained. Raw model thought/parameters and checkpoints are not shipped.
        dbfile=p/'run/execution_events.sqlite3'
        if dbfile.exists():
            with tempfile.TemporaryDirectory() as temp:
                target=Path(temp)/'events.sqlite3'
                with sqlite3.connect(f'file:{dbfile}?mode=ro',uri=True) as src,sqlite3.connect(target) as dst:src.backup(dst)
                with sqlite3.connect(target) as db:
                    db.execute('PRAGMA journal_mode=DELETE')
                    db.execute('DELETE FROM events');db.execute('DELETE FROM checkpoints') if db.execute("SELECT 1 FROM sqlite_master WHERE name='checkpoints'").fetchone() else None
                    # Only business guidance and questions are needed to review.
                    if db.execute("SELECT 1 FROM sqlite_master WHERE name='messages'").fetchone():db.execute("DELETE FROM messages WHERE kind NOT IN ('guidance','answer','context_resolution','question','question_deferred')")
                    db.commit();db.execute('VACUUM')
                z.write(target,'run/execution_events.sqlite3')
    write_json(p/'handoffs'/(snap['snapshot_id']+'.json'),snap)
    return stream.getvalue(),snap


def windows_package(project,program_zip):
    data,snap=project_archive(project);stream=io.BytesIO();prefix='scene-completion-windows-x64/'
    with zipfile.ZipFile(program_zip) as program,zipfile.ZipFile(io.BytesIO(data)) as project_zip,zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as out:
        for name in program.namelist():
            if not name.startswith(prefix) or '/data/' in name or name.endswith('/.env'):continue
            out.writestr(name,program.read(name))
        for name in project_zip.namelist():out.writestr(prefix+'data/'+snap['project_id']+'/'+name,project_zip.read(name))
        out.writestr(prefix+'data/.review-mode.json',json.dumps({'review_only':True,'project_id':snap['project_id'],'snapshot_id':snap['snapshot_id']}))
        out.writestr(prefix+'业务审核说明.txt','双击start.cmd。无需API Key。业务端只保存回答、审核推荐和更新本地指标，不运行模型。完成后在审核交接页导出反馈包，交回研发。\n')
    return stream.getvalue(),snap


def export_feedback(project):
    p=Path(project);snapshot_file=p/'review_snapshot.json'
    if not snapshot_file.exists():raise ValueError('此项目不是业务审核快照；请从审核包导出反馈')
    snap=read_json(snapshot_file)
    if source_hash(p)!=snap['source_hash']:raise ValueError('原始文档已被修改，不能合并为原快照反馈')
    answers=load(p,'pending_decisions.json',{'history':[]})['history'][snap['answer_history_count']:]
    feedback=load(p,'recommendation-history.json',{'feedback':[]})['feedback'][snap['feedback_history_count']:]
    result={'version':VERSION,'snapshot_id':snap['snapshot_id'],'project_id':snap['project_id'],'source_hash':snap['source_hash'],'answers':answers,'recommendation_feedback':feedback,'exported_at':time.time()}
    result['feedback_id']=fingerprint(result)
    return result


def import_feedback(project,document,*,dry_run=True,allow_partial=False):
    from .project_review import pending_items
    from .review_questions import answer
    from .result_views import ResultView
    from .pattern_settings import history,feedback
    if not isinstance(document,dict) or len(json.dumps(document,ensure_ascii=False))>20000000:raise ValueError('反馈包必须为不超过20MB的JSON对象')
    for kind,fields in [('answers',('item_id','choice')),('recommendation_feedback',('case_id','scenario_id','decision'))]:
        rows=document.get(kind,[])
        if not isinstance(rows,list) or len(rows)>10000 or any(not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k] for k in fields) for row in rows):raise ValueError('反馈记录格式无效或数量超限')
    p=Path(project);sid=document.get('snapshot_id','')
    if len(sid)!=64 or any(c not in '0123456789abcdef' for c in sid):raise ValueError('无效审核快照')
    snapshot_file=p/'handoffs'/(sid+'.json')
    if not snapshot_file.exists():raise ValueError('找不到对应的研发交接快照')
    snap=read_json(snapshot_file)
    if document.get('version')!=VERSION or document.get('project_id')!=snap['project_id'] or document.get('source_hash')!=snap['source_hash'] or source_hash(p)!=snap['source_hash']:raise ValueError('反馈的项目或原文版本不一致')
    supplied=document.get('feedback_id');expected=fingerprint({k:v for k,v in document.items() if k!='feedback_id'})
    if supplied!=expected:raise ValueError('反馈包内容哈希不一致')
    imported=load(p,'feedback_imports.json',{'items':{},'history':[]})
    if supplied in imported['items']:return {'duplicate':True,'saved':False,'conflicts':[],'feedback_id':supplied}
    items={r['id']:r for r in pending_items(p)};existing=load(p,'pending_decisions.json',{'items':{}})['items'];conflicts=[];ready=[]
    latest={r['item_id']:r for r in document.get('answers',[])}
    for iid,row in latest.items():
        base=snap['questions'].get(iid);item=items.get(iid)
        if not base or not item or bindings(p,item['origins'])!=base['origin_bindings'] or fingerprint({k:v for k,v in item.items() if k not in {'decision','created_at'}})!=base['item_hash'] or existing.get(iid,{}).get('revision',0)!=base['base_revision']:
            conflicts.append({'kind':'answer','id':iid,'reason':'问题、来源产物或研发回答已变化'});continue
        body={'revision':existing.get(iid,{}).get('revision',0),'choice':row.get('action',row['choice']),'answer':row.get('answer',row.get('note','')),'reviewer':row.get('reviewer',''),'concern_key':row.get('concern_key'),'via':'feedback_import'}
        answer(p,item,body,dry_run=True);ready.append(('answer',iid,body))
    view=ResultView(p);h=history(p);reviewed={(r.get('case_id'),r.get('scenario_id')) for r in h['feedback'] if r['id'] not in snap['base_feedback_ids']}
    newest={(r['case_id'],r['scenario_id']):r for r in document.get('recommendation_feedback',[])}
    # Validate the final feedback history in an isolated overlay. Later business
    # decisions may link to a GT introduced by an earlier adoption in this file.
    overlay=tempfile.TemporaryDirectory()
    staged=Path(overlay.name)
    # Use a small file overlay, not symlinks (Windows customers need no admin).
    import shutil
    (staged/'run').mkdir()
    for name in ('workflow_tasks.json','workflow_graph.json','run_manifest.json'):
        if (p/'run'/name).exists():shutil.copy2(p/'run'/name,staged/'run'/name)
    records=load(p,'run/workflow_tasks.json',{'tasks':{}})['tasks']
    for record in records.values():
        if record.get('stage') not in {'exception-evaluation','concern-evaluation','gap-recommend'} or not record.get('output_file'):continue
        source=(p/'run'/record['output_file']).resolve()
        if not source.is_relative_to((p/'run').resolve()):raise ValueError('无效冻结产物路径')
        dest=staged/'run'/record['output_file'];dest.parent.mkdir(parents=True,exist_ok=True)
        if source.is_file():shutil.copy2(source,dest)
    write_json(staged/'recommendation-history.json',h)
    for (case,gid),row in sorted(newest.items(),key=lambda entry:entry[1].get('reviewed_at',0)):
        result=view.payload(case+':gap-recommend');base=snap['recommendations'].get(case,{})
        scene=next((s for s in result.get('Q',[]) if s['id']==gid),None)
        if (case,gid) in reviewed or not scene or result.get('run_id')!=base.get('run_id') or fingerprint(scene)!=base.get('scenario_hashes',{}).get(gid):
            conflicts.append({'kind':'recommendation','id':gid,'reason':'推荐版本或研发审核已变化'});continue
        body={'revision':h['revision'],'case_id':case,'scenario_id':gid,'settings_hash':result['settings_hash'],'choice':row['decision'],'reviewer':row.get('reviewer',''),'note':row.get('note',''),'truth_resolution':row.get('truth_resolution',{}),'via':'feedback_import'}
        simulated={**body,'revision':history(staged)['revision']}
        feedback(staged,simulated,result);ready.append(('recommendation',case,body))
    overlay.cleanup()
    plan={'feedback_id':supplied,'ready_count':len(ready),'conflicts':conflicts,'saved':False,'llm_called':False,'audit_history':{'answers':len(document.get('answers',[])),'recommendations':len(document.get('recommendation_feedback',[]))}}
    if dry_run:return plan
    if conflicts and not allow_partial:raise ValueError('存在冲突，请先预览；可显式仅导入无冲突项')
    for kind,key,body in ready:
        if kind=='answer':answer(p,items[key],body)
        else:
            body['revision']=history(p)['revision'];feedback(p,body,view.payload(key+':gap-recommend'))
    imported['items'][supplied]={'snapshot_id':sid,'at':time.time(),'conflicts':conflicts,'applied':len(ready)};imported['history'].append({'feedback_id':supplied,'original_feedback':document})
    write_json(p/'feedback_imports.json',imported)
    from .review_questions import impact
    return {**plan,'saved':True,'impact':impact(p)}
