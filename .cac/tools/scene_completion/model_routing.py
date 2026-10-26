"""Explicit task/role model selection, with separate per-model usage ledgers."""
from copy import deepcopy
from .model_configuration import model_name

PROFILE_KEYS={'max_context_tokens','extra_body','stage_extra_body','max_tokens','stage_max_tokens','token_budget_ledger',
              'token_budget_limit','stream_total_timeout_seconds','stream_idle_timeout_seconds'}

def routed_config(config,task,role):
    if not any(k in config for k in ('task_models','role_models','model_profiles')):return None
    tasks,roles,profiles=(config.get(k,{}) for k in ('task_models','role_models','model_profiles'))
    if any(not isinstance(v,dict) for v in (tasks,roles,profiles)):raise ValueError('model routing settings must be mappings')
    selected=model_name(tasks.get(task) or roles.get(role) or config['agent_model'])
    if config.get('allowed_models') and selected not in config['allowed_models']:raise ValueError('selected model is not allowed for this API key')
    profile=profiles.get(selected,{})
    if not isinstance(profile,dict) or set(profile)-PROFILE_KEYS:raise ValueError('model profile contains unsupported configuration')
    if config.get('token_budget_limit') and selected!=config['agent_model'] and not profile.get('token_budget_ledger'):
        raise ValueError('each routed model requires an explicit independent token ledger')
    result={k:deepcopy(v) for k,v in config.items() if k not in ('task_models','role_models','model_profiles')}
    result.update(deepcopy(profile));result['agent_model']=selected
    return result
