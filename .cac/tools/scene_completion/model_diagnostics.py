"""Credential-free effective request settings and bounded node diagnostics."""
import json
from pathlib import Path
from .storage import read_json
from .runtime_settings import request_options,request_diagnostic,validate_options
from .model_settings import public_settings


def effective(config,task='agent'):
    from .deepagents_client import role_for,submission_mode
    from .model_routing import routed_config
    from .model_client import SemanticClient
    selected=routed_config(config,task,role_for(task)) or config
    validate_options(selected)
    client=SemanticClient(dict(selected));limit=client.output_limit(task)
    body=request_options({'model':client.model('agent'),'max_tokens':limit,'stream':selected.get('stream',True)},selected,task)
    safe={k:v for k,v in body.items() if k not in {'messages','tools'}}
    if selected.get('api_key'):
        safe=json.loads(json.dumps(safe).replace(selected['api_key'],'[redacted]'))
    return {'task':task,'role':role_for(task),'model':body['model'],'settings':public_settings(selected),'request_parameters':safe,
      'submission_mode':submission_mode(selected,task,body['model']),
      'notes':['输出上限由思考与正文/工具参数如何分配取决于网关；不是正文必得Token数。','实际请求另加系统提示、Skill、工具Schema及历史，逐请求检查上下文预算。','兼容预设不是对客户网关能力的探测；不支持的参数应按网关说明关闭。']}


def node_diagnostics(project,config,task_key=None,limit=20):
    root=Path(project)/'run';state=read_json(root/'workflow_tasks.json').get('tasks',{}) if (root/'workflow_tasks.json').exists() else {}
    if task_key and task_key not in state:raise ValueError('未知执行节点，请从status或执行图选取真实节点ID')
    rows=[(task_key,state[task_key])] if task_key else [(k,r) for k,r in state.items() if r.get('status') not in {'passed','ready','pending','running'} or r.get('failure')][-limit:]
    out=[]
    from .execution_events import EventStore
    store=EventStore(root)
    for key,row in rows:
        with store.connect() as db:
            history=db.execute("SELECT payload FROM events WHERE task_key=? AND kind IN ('request_started','request_finished','request_failed','response_invalid','validation_failed','artifact_io_failed','stream_progress','stream_status','agent_failed') ORDER BY id DESC LIMIT ?",(key,limit)).fetchall()
        history=[json.loads(v[0]) for v in reversed(history)]
        recent=[]
        for event in history:
            data=event['data'];recent.append({'kind':event['kind'],'timestamp':event['timestamp'],'data':{k:v for k,v in data.items() if k not in {'text','content','arguments','reasoning_content'}}})
        failures=[]
        for p in sorted((root/'agent_rejections').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            v=read_json(p)
            if v.get('node_key')==key:
                failures.append({'file':p.relative_to(project).as_posix(),'error':str(v.get('error',''))[:4000]})
                if len(failures)>=3:break
        out.append({'task_key':key,'stage':row['stage'],'status':row['status'],'failure':row.get('failure'), 'effective':effective(config,row['stage']), 'events':recent,'validation_rejections':failures})
    result={'nodes':out,'llm_called':False,'notes':['诊断只读取已有记录，不调用模型、不重置配额或修复预算。','同一节点需区分输出截断、JSON语法、业务Schema和本地文件写入失败；诊断不返回思考原文，显式开启后思考文本单列在本地节点事件。']}
    text=json.dumps(result,ensure_ascii=False)
    if config.get('api_key'):text=text.replace(config['api_key'],'[redacted]')
    return json.loads(text)
