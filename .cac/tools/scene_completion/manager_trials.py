"""Explicit hypothetical branch: never modifies a formal project's materials or scores."""
from pathlib import Path
import time,base64
from .storage import read_json,write_json,fingerprint
from .manager_store import Journal

def create_trial(service,rid,body):
 assumption=body.get('assumption','').strip();basis=body.get('basis','').strip()
 if not assumption or not basis:raise ValueError('试跑需要假设及推理依据')
 parent=service.run_dir(rid);meta=read_json(parent/'project.json')
 if meta.get('manager_trial'):raise ValueError('不能递归创建推理试跑')
 signature=fingerprint([body.get('node'),assumption,basis]);journal=Journal(parent);old=journal.get('trial',signature)
 if old:return old
 sources={k:[{'name':v['name'],'content_base64':base64.b64encode((parent/v['path']).read_bytes()).decode()} for v in rows] for k,rows in meta['sources'].items()}
 node=body.get('node','')
 if not node or ':' not in node:raise ValueError('试跑必须指定具体用例节点')
 if node.split(':',1)[1].split('--part-')[0] not in {'normal-rules','concern-match','exception-generate'}:raise ValueError('假设仅允许用于指定正向规则、关注点或场景节点；不能注入E/GT或共享材料')
 trial=service.create({'name':meta['name']+' · 推理试跑','sources':sources,'review_mode':'auto','case_ids':meta.get('case_ids',[])})
 target=service.run_dir(trial['id']);trial.update(manager_trial={'parent':rid,'assumption':assumption,'basis':basis,'node':body.get('node'),'at':time.time(),'formal':False,'note':'试跑指标单独展示；不能合并到正式GT或报告'})
 write_json(target/'project.json',trial)
 import shutil
 if (parent/'model.local.json').exists():shutil.copy2(parent/'model.local.json',target/'model.local.json')
 from .positive_reuse import prepare
 prepare(parent,target)
 # Guidance is scoped to the explicit positive node, never appended to RR/SR.
 # The evidence validator remains unchanged: hypotheses are not document facts.
 from .node_conversations import Conversations
 Conversations(target/'run').append(node,'guidance','仅独立试跑的推理假设，非已确认事实：'+assumption+'。依据：'+basis+'。仅可用于本节点有据推导；无可校验证据的内容保留待确认，不进入确定集合。',{'source':'manager_inference','formal':False})
 journal.memory({'category':'assumption','text':assumption,'source':'manager_inference','scope':[body.get('node','')],'expected_revision':0})
 return journal.put('trial',{'project_id':trial['id'],'formal':False,'assumption':assumption,'basis':basis},signature,0)
