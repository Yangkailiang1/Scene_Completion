"""Explicit candidate routing, fresh runtime settings and bounded failover."""
from copy import deepcopy
from pathlib import Path
import json,time
from .storage import read_json,write_json,fingerprint

DEFAULT={'enabled':False,'candidates':[],'min_tokens_per_second':2,'window_seconds':30,'grace_seconds':60,'low_windows':2,'no_output_seconds':120,'max_switches':2,'cooldown_seconds':300,'switch_on_rejection':True}


def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULT):raise ValueError('无效自动切换配置')
    p={**deepcopy(DEFAULT),**value}
    for k in ('enabled','switch_on_rejection'):
        if type(p[k]) is not bool:raise ValueError(k+'必须为布尔值')
    for k,lo,hi in [('min_tokens_per_second',0,10000),('window_seconds',5,600),('grace_seconds',0,3600),('low_windows',1,10),('no_output_seconds',10,3600),('max_switches',0,5),('cooldown_seconds',0,3600)]:
        if type(p[k]) not in (int,float) or not lo<=p[k]<=hi or k not in {'min_tokens_per_second'} and type(p[k]) is not int:raise ValueError(k+'超出允许范围')
    if not isinstance(p['candidates'],list) or len(p['candidates'])>20:raise ValueError('候选模型必须为最多20项的列表')
    for c in p['candidates']:
        if not isinstance(c,dict) or set(c)-{'model','account_id'} or not isinstance(c.get('model'),str) or not c['model'].strip():raise ValueError('每个候选需要model，可选account_id')
        if c.get('account_id') is not None and (not isinstance(c['account_id'],str) or not c['account_id']):raise ValueError('account_id无效')
    return p


def fresh(config):
    p=config.get('_live_project')
    if not p:return deepcopy(config)
    from .model_settings import resolve
    file=Path(p)/'model.local.json'
    current=resolve(read_json(file) if file.exists() else {},config.get('_live_env_file'),config.get('_live_accounts_root'))
    # Execution owns its evidence/run location; a live provider update cannot change it.
    for k in ('run_root','cache_dir','_live_project','_live_env_file','_live_accounts_root'):
        if k in config:current[k]=config[k]
    return current


def policy(config):return validate(fresh(config).get('resilience',{}))


def select(config,candidate):
    from .model_accounts import apply_account
    from .model_routing import routed_config
    from .runtime_settings import validate_options
    value=deepcopy(config)
    if candidate.get('account_id') and candidate['account_id']!=value.get('model_account_id'):
        profile=deepcopy(value.get('model_profiles',{}).get(candidate['account_id']+'::'+candidate['model'],{}))
        if value.get('token_budget_limit') and not (profile.get('token_budget_ledger') and profile.get('token_budget_limit')):
            raise ValueError('跨账号候选需要显式的独立额度配置，不继承原账号账本')
        for k in ('api_key','allowed_models','token_budget_ledger','provider_token_budget_ledgers','provider_token_budget_lock','model_profiles','token_budget_limit','provider_token_budget_limit','token_budget_reasoning_reserve','api_key_env','task_models','role_models'):
            value.pop(k,None)
        value['model_account_id']=candidate['account_id'];value['agent_model']=candidate['model']
        value['resilience']={**value.get('resilience',{}),'candidates':[]}
        value.update(profile)
        value=apply_account(value,value.get('_live_accounts_root'),value.get('_live_env_file'))
        validate_options(value)
        return value
    value.pop('task_models',None);value.pop('role_models',None)
    value.setdefault('model_profiles',{})
    value['task_models']={'_fallback':candidate['model']}
    value=routed_config(value,'_fallback','modeler')
    validate_options(value)
    return value


def invoke(client,packet,call):
    from .deepagents_client import DeepAgentsClient,role_for
    from .model_routing import routed_config
    from .execution_events import emit,phase
    from .scheduler import TaskRejected
    cfg=fresh(client.config)
    if not cfg.get('_live_project'):
        # Standalone adapters may receive credentials directly, without a project file.
        cfg.setdefault('api_key',getattr(client,'api_key',''));cfg.setdefault('base_url',getattr(client,'base_url',''))
    p=validate(cfg.get('resilience',{}))
    primary=routed_config(cfg,packet['task'],role_for(packet['task'])) or cfg
    used=set();last=None;switches=0;dispatches=0
    while True:
        choices=[None]+(p['candidates'] if p['enabled'] and switches<p['max_switches'] else [])
        chosen=None
        for choice in choices:
            try:config=select(cfg,choice) if choice else deepcopy(primary)
            except ValueError as e:
                emit('model_switch_skipped',model=(choice or {}).get('model'),reason=str(e));continue
            signature=(config.get('model_account_id'),config['agent_model'])
            if signature in used:continue
            if p['enabled'] and cooling(config):
                emit('model_switch_skipped',model=config['agent_model'],reason='模型处于已记录的降级冷却期');continue
            used.add(signature);chosen=(choice,config);break
        if chosen is None:break
        choice,config=chosen
        if dispatches:
            if switches>=p['max_switches']:break
            switches+=1
        dispatches+=1
        config['_resilience_active']=True
        child=DeepAgentsClient(config,transport=getattr(client,'_custom_transport',None))
        if getattr(client,'shared_call_gate',None):
            child.shared_call_gate=client.shared_call_gate;original=child.post
            child.post=lambda *a,_child=child,_post=original,**kw:_child.shared_call_gate.call(_post,*a,**kw)
        if choice or last:
            phase('switching_model');emit('model_switched',requested_model=config['agent_model'],previous_failure=getattr(last,'response_diagnostic',getattr(last,'details',{})),note='仅重做当前未完成节点；旧请求、用量及通过产物保留')
        try:return call(child)
        except Exception as exc:
            diagnostic=getattr(exc,'response_diagnostic',getattr(exc,'details',{})) or {}
            failure=diagnostic.get('transport_failure',diagnostic)
            category=failure.get('failure_category')
            cfg=fresh(client.config);p=validate(cfg.get('resilience',{}))
            if not cfg.get('_live_project'):
                cfg.setdefault('api_key',getattr(client,'api_key',''));cfg.setdefault('base_url',getattr(client,'base_url',''))
            primary=routed_config(cfg,packet['task'],role_for(packet['task'])) or cfg
            safe=category in {'slow_stream','rate_limited','endpoint_busy','model_unavailable','access_denied','output_truncated'} or p['switch_on_rejection'] and isinstance(exc,TaskRejected)
            # Unknown network POST and authentication failure require diagnosis, not blind replay.
            if not p['enabled'] or not safe:raise
            mark_degraded(config,p,category or 'validation_rejected')
            last=exc;emit('model_degraded',requested_model=config['agent_model'],failure_category=category or 'validation_rejected')
            if switches>=p['max_switches']:raise
    if last:raise last
    raise ValueError('没有可用的已配置候选模型；请检查账号模型列表、冷却状态和独立额度配置')


def health_path(config):
    root=config.get('_live_project') or config.get('run_root')
    return Path(root)/'model-health.json' if root else None

def health_key(config):
    return fingerprint([config.get('model_account_id'),config.get('base_url'),config.get('agent_model')])

def cooling(config):
    path=health_path(config)
    if not path or not path.exists():return False
    row=read_json(path).get('models',{}).get(health_key(config),{})
    return row.get('retry_at',0)>time.time()

def mark_degraded(config,p,reason):
    path=health_path(config)
    if not path:return
    from .scheduler import run_lock
    with run_lock(path.parent/'model-health-lock'):
        value=read_json(path) if path.exists() else {'models':{},'history':[]}
        row={'model':config['agent_model'],'account_id':config.get('model_account_id'),'reason':reason,'at':time.time(),'retry_at':time.time()+p['cooldown_seconds']}
        value['models'][health_key(config)]=row;value['history'].append(row)
        value['history']=value['history'][-1000:];write_json(path,value)


def live_policy(config):
    """Do not reread JSON and credentials for every SSE line."""
    cached={};until=0.
    def read():
        nonlocal cached,until
        now=time.monotonic()
        if now>=until:
            cached=policy(config);until=now+1.
        return cached
    return read
