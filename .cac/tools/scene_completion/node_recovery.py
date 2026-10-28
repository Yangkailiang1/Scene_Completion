"""Bounded model recovery; the original executor remains the only publisher."""
from pathlib import Path
from copy import deepcopy
from threading import RLock
import time,json
from .storage import read_json,write_json,fingerprint

LOCK=RLock()
DEFAULT={'enabled':True,'max_node_calls':2,'max_run_calls':20,'allowed_submission_modes':['tool_calls','json_text'],'max_output_tokens':None}


def settings(project,body=None):
 p=Path(project)/'recovery-settings.json';old=read_json(p) if p.exists() else {'revision':0,'settings':deepcopy(DEFAULT)}
 if body is None:return old
 if body.get('expected_revision')!=old['revision']:raise ValueError('恢复策略版本已变化')
 value={**old['settings'],**body.get('settings',{})}
 if set(value)!=set(DEFAULT) or type(value['enabled']) is not bool:raise ValueError('无效恢复策略')
 for k,maximum in [('max_node_calls',2),('max_run_calls',100)]:
  if type(value[k]) is not int or not 0<=value[k]<=maximum:raise ValueError(k+'超出允许范围')
 if not isinstance(value['allowed_submission_modes'],list) or set(value['allowed_submission_modes'])-{'tool_calls','json_text'}:raise ValueError('无效提交模式')
 if value['max_output_tokens'] is not None and (type(value['max_output_tokens']) is not int or not 256<=value['max_output_tokens']<=2000000):raise ValueError('输出上限必须明确且为正数')
 row={'revision':old['revision']+1,'settings':value,'updated_at':time.time()}
 if body.get('dry_run'):return {**row,'saved':False}
 write_json(p.parent/'recovery-versions'/(fingerprint(row)+'.json'),row);write_json(p,row);return row


def records(project):
 p=Path(project)/'run/recovery-ledger.json'
 return read_json(p) if p.exists() else {'epochs':{},'history':[]}


def eligible(project,stage,record,epoch):
 policy=settings(project)['settings']
 if not policy['enabled'] or record.get('recovery_calls',0)>=policy['max_node_calls']:return False
 if records(project)['epochs'].get(epoch,{}).get('calls',0)>=policy['max_run_calls']:return False
 failure=record.get('failure') or {};category=failure.get('failure_category')
 if record.get('status')=='awaiting_configuration':
  return category=='output_truncated' and policy['max_output_tokens'] is not None
 return record.get('status')=='rejected' and failure.get('type') not in {'TypeError','AttributeError','OSError'}


def reserve(project,key,epoch,input_hash):
 with LOCK:
  ledger=records(project);run=ledger['epochs'].setdefault(epoch,{'calls':0,'nodes':{}});policy=settings(project)['settings']
  node=fingerprint([key,input_hash]);calls=run['nodes'].get(node,0)
  if calls>=policy['max_node_calls'] or run['calls']>=policy['max_run_calls']:
   from .scheduler import TaskBlocked
   raise TaskBlocked('recovery_exhausted',{'reason':'恢复调用预算已耗尽，保留诊断并等待人工处理'})
  run['calls']+=1;run['nodes'][node]=calls+1
  ledger['history'].append({'node':key,'epoch':epoch,'input_hash':input_hash,'attempt':calls+1,'at':time.time()})
  write_json(Path(project)/'run/recovery-ledger.json',ledger)
  return calls+1


def generate(ex,packet,record):
 from .deepagents_client import DeepAgentsClient,role_for,submission_mode
 from .model_routing import routed_config
 from .execution_events import emit,phase
 from .model_resilience import fresh
 current=fresh(ex.config);config=routed_config(current,packet['task'],role_for(packet['task'])) or deepcopy(current)
 config.setdefault('api_key',getattr(ex.client,'api_key',''));config.setdefault('base_url',getattr(ex.client,'base_url',''))
 config['_resilience_active']=True
 policy=settings(ex.root.parent)['settings'];key=packet['node_key']
 number=reserve(ex.root.parent,key,ex.recovery_epoch,fingerprint(packet['input']))
 config['agent_max_model_calls']=1
 mode=submission_mode(config,packet['task'],config['agent_model'])
 failure=record.get('failure',{})
 # Switch transport only for known tool/JSON envelope failures. Keep model,
 # account, quota and all allowed evidence exactly as the original task.
 if number==1 and mode=='tool_calls' and 'json_text' in policy['allowed_submission_modes']:
  config['submission_mode']='json_text';config['component_submission_mode']='json_text'
 if policy['max_output_tokens'] is not None and failure.get('failure_category')=='output_truncated':
  config['max_tokens']=max(config.get('max_tokens',12000),policy['max_output_tokens'])
  config.setdefault('stage_max_tokens',{})[packet['task']]=policy['max_output_tokens']
 from .runtime_settings import validate_options
 validate_options(config)
 client=DeepAgentsClient(config,transport=getattr(ex.client,'_custom_transport',None))
 client.shared_call_gate=ex.gate
 original=client.post
 client.post=lambda *a,**kw:ex.gate.call(original,*a,**kw)
 # No subclass or fallback endpoint is installed; the same metered transport is used.
 proposal=deepcopy(packet)
 skill=Path(__file__).resolve().parents[2]/'skills/scene-node-recovery/SKILL.md'
 proposal['skill_text']+='\n\n'+skill.read_text(encoding='utf8')
 proposal['instructions']+='\n当前为有界恢复第'+str(number)+'次，保留合法事实，只修正本节点的具体错误；不得用空成功绕过失败。'
 proposal['repair']={**proposal.get('repair',{}),'failure':failure,'recovery_attempt':number}
 phase('recovering');emit('recovery_started',attempt_number=number,original_failure=failure,submission_mode=config.get('submission_mode'))
 result=client.agent(proposal)
 emit('recovery_submitted',attempt_number=number)
 result.setdefault('execution_model_evidence',{})['recovery']={'attempt':number,'epoch':ex.recovery_epoch,'policy_revision':settings(ex.root.parent)['revision']}
 return result


def fault_package(root,key,record):
 """Local engineering diagnostic, never a public release attachment."""
 row={k:record.get(k) for k in ('stage','case','status','failure','identity','rounds','recovery_calls')}
 row.update(task_key=key,created_at=time.time(),note='程序或恢复失败，需研发处理；未绕过依赖或改写成功状态')
 write_json(Path(root)/'faults'/(fingerprint([key,row])+'.json'),row)
