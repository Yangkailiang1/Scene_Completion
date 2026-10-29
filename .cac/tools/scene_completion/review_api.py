"""Review workflow APIs shared by browser and Code Agent CLI."""
from pathlib import Path
import json, zipfile, io
from .storage import read_json


def register(app, service, project_root):
    from fastapi.responses import Response
    from . import review_handoff as handoff
    from . import review_questions as questions

    def idle(rid):
        p=service.run_dir(rid)
        job=read_json(p/'job.json') if (p/'job.json').exists() else {}
        if rid in service.active or job.get('status')=='running' and job.get('worker_heartbeat',0)>__import__('time').time()-30:raise ValueError('请等待当前执行结束后交接或重算')
        return p

    @app.get('/api/projects/{rid}/sources')
    def source_list(rid:str):return handoff.sources(service.run_dir(rid))

    @app.get('/api/projects/{rid}/sources/{source_id}')
    def source_read(rid:str,source_id:str,start:int=1,end:int|None=None,context:int=40,quote:str='',view:str='window'):
        return handoff.source_view(service.run_dir(rid),source_id,start,end,context,quote,view)

    @app.get('/api/projects/{rid}/pending/{item_id}/history')
    def answer_history(rid:str,item_id:str):
        saved=questions.load(service.run_dir(rid),'pending_decisions.json',{'history':[]})
        return {'items':[r for r in saved['history'] if r['item_id']==item_id]}

    @app.get('/api/projects/{rid}/impact')
    def impact(rid:str):return questions.impact(service.run_dir(rid))

    @app.post('/api/projects/{rid}/rerun-affected')
    def rerun(rid:str,body:dict):
        p=idle(rid);plan=questions.impact(p)
        if body.get('plan_id')!=plan['plan_id']:raise ValueError('影响范围已变化，请重新预览')
        if body.get('dry_run'):return {**plan,'saved':False}
        if not plan['roots']:return {**plan,'started':False,'reason':'没有尚未应用的有效业务回答'}
        if plan['conflicts']:raise ValueError('请先处理反馈冲突')
        # Resolve configuration before consuming answers. No call is made here.
        config=service.model_config(rid)
        if not service.client_factory and (not config.get('api_key') or not config.get('base_url')):raise ValueError('研发端需要先配置可用模型连接')
        with service.lock:questions.apply_answers(p,plan['plan_id'])
        return {**service.start(rid),'impact':plan}

    @app.get('/api/projects/{rid}/business-truth/{case_id}')
    def truth(rid:str,case_id:str):
        from .business_truth import snapshot
        return snapshot(service.run_dir(rid),case_id)

    @app.get('/api/projects/{rid}/handoff')
    def handoff_status(rid:str):
        p=service.run_dir(rid)
        return {'review_only':service.review_only,'snapshots':[{'id':v.stem,**{k:x for k,x in read_json(v).items() if k in {'created_at','project_id','manifest_hash','source_hash'}}} for v in sorted((p/'handoffs').glob('*.json'),reverse=True)][:20],
                'feedback_available':(p/'review_snapshot.json').exists()}

    @app.post('/api/projects/{rid}/handoff/export')
    def handoff_export(rid:str,body:dict):
        p=idle(rid);kind=body.get('format','windows')
        if kind not in {'windows','project'}:raise ValueError('format须为windows或project')
        if body.get('dry_run'):return {'valid':True,'saved':False,'project':rid,'format':kind,'source_hash':handoff.source_hash(p)}
        from .scheduler import run_lock
        with service.lock,run_lock(p/'run'):
            if kind=='project':data,snap=handoff.project_archive(p)
            else:
                base=Path(project_root)/'dist/scene-completion-windows-x64.zip'
                installed=Path(project_root).parent
                if (installed/'python/python.exe').exists():
                    stream=io.BytesIO()
                    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
                        for f in installed.rglob('*'):
                            if f.is_file() and f.relative_to(installed).parts[0] in {'python','app'}:z.write(f,'scene-completion-windows-x64/'+f.relative_to(installed).as_posix())
                        for name in ('launcher.py','start.cmd','check.cmd','scene.cmd','VERSION.json','SHA256SUMS.json'):
                            if (installed/name).is_file():z.write(installed/name,'scene-completion-windows-x64/'+name)
                    base=io.BytesIO(stream.getvalue())
                elif not base.exists():raise ValueError('未找到Windows程序包，请先构建离线包')
                with zipfile.ZipFile(base) as z:
                    name='scene-completion-windows-x64/app/.cac/tools/scene_completion/review_api.py'
                    if name not in z.namelist() or z.read(name)!=Path(__file__).read_bytes():raise ValueError('基础Windows包不是当前审核版本，请先更新程序包')
                data,snap=handoff.windows_package(p,base)
        return Response(data,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="business-review-{snap["snapshot_id"][:12]}.zip"'})

    @app.get('/api/projects/{rid}/feedback/export')
    def feedback_export(rid:str):
        p=idle(rid)
        with service.lock:document=handoff.export_feedback(p)
        return Response(json.dumps(document,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="business-feedback.json"'})

    @app.post('/api/projects/{rid}/feedback/import')
    def feedback_import(rid:str,body:dict):
        p=idle(rid)
        with service.lock:return handoff.import_feedback(p,body['feedback'],dry_run=body.get('dry_run',True),allow_partial=body.get('allow_partial',False))
