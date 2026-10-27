"""Validated OpenAI-compatible runtime options shared by CLI, API and routing."""
from copy import deepcopy
import json

INTS={'max_concurrency':(2,1,8),'max_tokens':(12000,256,2000000),'max_context_tokens':(200000,1024,2000000),
 'timeout_seconds':(120,10,1800),'stream_idle_timeout_seconds':(300,10,3600),'stream_total_timeout_seconds':(900,30,7200),
 'agent_max_model_calls':(5,1,20)}
BOOLS={'stream','stream_usage','send_reasoning_effort','supports_tool_choice','supports_parallel_tool_calls','reasoning_replay','json_response_format'}
ENUMS={'thinking_api':{'legacy','enable_thinking','omit'},'submission_mode':{'tool_calls','json_text'},'component_submission_mode':{'tool_calls','json_text'},'max_tokens_parameter':{'max_tokens','max_completion_tokens'}}
MAPS={'stage_max_tokens','extra_body','stage_extra_body','model_profiles','task_models','role_models'}
KEYS=set(INTS)|BOOLS|set(ENUMS)|MAPS|{'thinking','reasoning_effort','thinking_budget'}
PRESETS={'deepseek-thinking':{'thinking':True,'thinking_api':'legacy','send_reasoning_effort':False,'reasoning_replay':True,
 'supports_tool_choice':False,'supports_parallel_tool_calls':False,'max_tokens':32768,'max_context_tokens':200000,'stream':True,'stream_idle_timeout_seconds':300,'stream_total_timeout_seconds':1800}}
FORBIDDEN={'model','messages','tools','tool_choice','parallel_tool_calls','stream','stream_options','max_tokens','max_completion_tokens','api_key','api_key_env','base_url','headers','authorization'}

def validate_extra(value):
    if not isinstance(value,dict) or {k.lower() for k in value}&FORBIDDEN:raise ValueError('extra_body只接受供应商扩展参数，不能覆盖模型、消息、凭证、工具或输出上限')
    def visit(v):
        if isinstance(v,dict):
            if not all(isinstance(k,str) for k in v):raise ValueError('扩展参数键须为文本')
            if any(any(word in k.lower() for word in ('api_key','secret','password','authorization','headers')) for k in v):raise ValueError('扩展参数不能包含凭证或请求头')
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value)
    if len(json.dumps(value,allow_nan=False).encode())>32768:raise ValueError('扩展参数过大')

def validate_options(config,*,defaults=False,profile=False):
    out=deepcopy(config)
    for k,(default,lo,hi) in INTS.items():
        if k not in out and not defaults:continue
        v=out.get(k,default)
        if type(v) is not int or not lo<=v<=hi:raise ValueError(f'{k}必须是{lo}至{hi}的整数')
        out[k]=v
    for k in BOOLS:
        if k in out and type(out[k]) is not bool:raise ValueError(k+'必须是布尔值')
    for k,allowed in ENUMS.items():
        if k in out and out[k] not in allowed:raise ValueError(k+'不在支持值中')
    if out.get('thinking') not in (None,True,False) or ('thinking' in out and out['thinking'] is not None and type(out['thinking']) is not bool):raise ValueError('thinking必须为true、false或null（跟随网关）')
    if 'reasoning_effort' in out and (not isinstance(out['reasoning_effort'],str) or not 1<=len(out['reasoning_effort'])<=64 or any(c in out['reasoning_effort'] for c in '\r\n\x00')):raise ValueError('reasoning_effort必须是网关支持的标识')
    if out.get('thinking_budget') is not None and (type(out['thinking_budget']) is not int or out['thinking_budget']<1 or out.get('send_reasoning_effort',True)):raise ValueError('thinking_budget必须为正整数且send_reasoning_effort=false')
    for k in MAPS:
        if k in out and not isinstance(out[k],dict):raise ValueError(k+'必须是对象')
    if 'extra_body' in out:validate_extra(out['extra_body'])
    for stage,v in out.get('stage_extra_body',{}).items():
        if not isinstance(stage,str) or not stage:raise ValueError('任务参数名称无效')
        validate_extra(v)
    for stage,n in out.get('stage_max_tokens',{}).items():
        if not isinstance(stage,str) or not stage or type(n) is not int or not 256<=n<=2000000:raise ValueError('stage_max_tokens必须为任务名称到输出上限的映射')
    for key in ('role_models','task_models'):
        if any(not isinstance(k,str) or not k or not isinstance(v,str) or not v.strip() for k,v in out.get(key,{}).items()):raise ValueError(key+'必须映射到非空模型名')
    if not profile:
        for model,p in out.get('model_profiles',{}).items():
            from .model_routing import PROFILE_KEYS
            if not isinstance(p,dict) or set(p)-PROFILE_KEYS:raise ValueError('模型参数包含不支持的配置')
            validate_options({**{k:v for k,v in out.items() if k not in MAPS},**p},profile=True)
    window=out.get('max_context_tokens',200000)
    if out.get('max_tokens',12000)>=window or any(n>=window for n in out.get('stage_max_tokens',{}).values()):raise ValueError('输出预留必须小于上下文总上限，真实输入及工具Schema还会逐请求校验')
    if out.get('stream_total_timeout_seconds',900)<out.get('stream_idle_timeout_seconds',300):raise ValueError('流式总时限不能小于无数据等待时限')
    return out

def request_options(body,config,stage=None):
    """Use the same request contract in Deep Agents and direct JSON clients."""
    out=deepcopy(body);thinking=config.get('thinking');api=config.get('thinking_api','legacy')
    if thinking is not None and api!='omit':out['enable_thinking' if api=='enable_thinking' else 'thinking']=bool(thinking) if api=='enable_thinking' else {'type':'enabled' if thinking else 'disabled'}
    if thinking and config.get('send_reasoning_effort',True):
        effort=config.get('reasoning_effort','high')
        if config.get('supported_reasoning_efforts') and effort not in config['supported_reasoning_efforts']:raise ValueError('reasoning_effort is not in configured supported_reasoning_efforts')
        if not isinstance(effort,str) or not 1<=len(effort)<=64 or any(c in effort for c in '\r\n\x00'):raise ValueError('reasoning_effort invalid')
        out['reasoning_effort']=effort
    if thinking and config.get('thinking_budget') is not None:out['thinking_budget']=config['thinking_budget']
    out.update(deepcopy(config.get('extra_body',{})));out.update(deepcopy(config.get('stage_extra_body',{}).get(stage,{})))
    if not config.get('supports_tool_choice',True):out.pop('tool_choice',None)
    if not config.get('supports_parallel_tool_calls',True):out.pop('parallel_tool_calls',None)
    if config.get('json_response_format') is False:out.pop('response_format',None)
    if config.get('max_tokens_parameter')=='max_completion_tokens':out['max_completion_tokens']=out.pop('max_tokens')
    return out

def output_limit(body):return body.get('max_tokens',body.get('max_completion_tokens'))

def request_diagnostic(body,response=None):
    response=response or {};choice=(response.get('choices') or [{}])[0];message=choice.get('message') or {}
    return {'requested_model':body.get('model'),'provider_model':response.get('model'),'max_output_tokens':output_limit(body),'output_parameter':'max_completion_tokens' if 'max_completion_tokens' in body else 'max_tokens',
     'finish_reason':choice.get('finish_reason'),'usage':response.get('usage'),'body_bytes':len((message.get('content') or '').encode()) if isinstance(message.get('content'),str) else 0,
     'tool_call_count':len(message.get('tool_calls') or []),'reasoning_received':bool(message.get('reasoning_content')),
     'thinking':body.get('thinking',body.get('enable_thinking','gateway_default')),'reasoning_effort':body.get('reasoning_effort'),
     'stream':body.get('stream',False),'tool_choice_sent':'tool_choice' in body, 'reasoning_bytes':response.get('_scene_completion_metrics',{}).get('reasoning_bytes',0)}
