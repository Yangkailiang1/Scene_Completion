"""Input-bound external repair handoff; never edits official artifacts directly."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
from .storage import fingerprint,read_json,write_json
from .validation import validate_result
from .contracts import PROTOCOL,registry


def path(root,key):return Path(root)/'external_repairs'/(fingerprint(key)+'.json')
def repair_revision(root,key):
    p=path(root,key)
    return fingerprint(read_json(p)) if p.exists() else None

def binding(packet,guidance):
    return {'protocol':PROTOCOL,'task':packet['task'],'node_key':packet['node_key'],'input_hash':fingerprint(packet['input']),
      'schema_hash':fingerprint(packet['output_schema']),'skill_hash':fingerprint(packet.get('skill_text','')),'instructions_hash':fingerprint(packet.get('instructions','')),'guidance_revision':guidance,'registry_hash':registry()['hash']}

def packet_for(root,key):
    rows=[]
    for p in (Path(root)/'packets').glob('*.json'):
        v=read_json(p)
        if v.get('node_key')==key:rows.append((p.stat().st_mtime_ns,v))
    if not rows:raise ValueError('节点尚无任务包，不能导出修复上下文')
    return max(rows,key=lambda row:row[0])[1]

def export_repair(project,key):
    root=Path(project)/'run';state=read_json(root/'workflow_tasks.json')['tasks'];r=state.get(key)
    if not r or r.get('status') in {'passed','running','awaiting_answer','blocked_dependency'}:raise ValueError('请选择失败或配置阻塞的真实节点；运行中节点和待回答问题不能通过修复绕过')
    p=packet_for(root,key)
    from .node_conversations import Conversations
    revision=Conversations(root).revision(key);candidate=None
    for f in sorted((root/'agent_rejections').glob('*.json'),key=lambda f:f.stat().st_mtime_ns,reverse=True):
        v=read_json(f)
        if v.get('node_key')==key and v.get('input_hash')==fingerprint(p['input']):candidate=v.get('payload');break
    return {'binding':binding(p,revision),'state_identity':r.get('identity'),'task_packet':p,'failure':r.get('failure'), 'payload':candidate,'note':'',
      'instructions':'仅修改payload及note。输入为本节点允许材料，不读取其他通道。提交须通过Schema、来源及语义边界校验；不会直接覆盖正式产物。'}

def submit_repair(project,key,document,*,validate_only=False):
    current=export_repair(project,key)
    if document.get('binding')!=current['binding'] or document.get('state_identity')!=current['state_identity']:raise ValueError('修复上下文已过期，请重新导出；不得提交到其他节点/版本')
    value=document.get('payload');p=current['task_packet']
    if not isinstance(value,dict):raise ValueError('payload必须是完整业务JSON对象')
    validate_result(p['task'],value,p['input'])
    if p['task']=='components' and any(p['input'].values()) and not value['components']:raise ValueError('非空需求不得用空组成跳过节点')
    if p['task'] in {'rr-ssd','sr-ssd'} and any(p['input'].values()) and not value['interactions']:raise ValueError('非空需求不得用空SSD跳过节点')
    note=document.get('note','')
    if not isinstance(note,str) or not note.strip():raise ValueError('提交修复须填写note说明修改及依据')
    if validate_only:return {'valid':True,'saved':False,'task_key':key}
    target=path(Path(project)/'run',key);old=read_json(target) if target.exists() else {}
    row={'binding':current['binding'],'payload':deepcopy(value),'note':note,'revision':old.get('revision',0)+1,'previous_failure':current['failure'],'updated_at':datetime.now(timezone.utc).isoformat()}
    write_json(target.parent/'history'/(fingerprint(row)+'.json'),row);write_json(target,row)
    from .execution_events import EventStore
    EventStore(Path(project)/'run').append('external_repair_saved',task_key=key,revision=row['revision'],note=note)
    return {'valid':True,'saved':True,'task_key':key,'revision':row['revision'],'next':'run继续原流水线，复用通过校验的修复；独立任务不受此节点阻塞影响'}

def read_repair(root,packet,guidance):
    f=path(root,packet['node_key'])
    if not f.exists():return None
    row=read_json(f)
    return row if row['binding']==binding(packet,guidance) else None
