"""Resolve project overrides and server-side .env without exposing credentials."""
from pathlib import Path
import os,re

def read_env(path):
    values={}
    if Path(path).exists():
        for row in Path(path).read_text(encoding='utf-8-sig').splitlines():
            line=row.strip()
            if line.startswith('export '):line=line[7:].lstrip()
            if not line or line.startswith('#') or '=' not in line:continue
            key,value=line.split('=',1);key=key.strip();value=value.strip()
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',key):continue
            if len(value)>1 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
            values[key]=value
    return values

def resolve(overrides,env_path,accounts_root=None):
    from .model_accounts import apply_account
    env={**read_env(env_path),**os.environ};config=apply_account(overrides,accounts_root,env_path)
    def expand(v):
        m=re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}',str(v or ''))
        return env.get(m[1],'') if m else v
    config['base_url']=expand(config.get('base_url')) or env.get('SCENE_API_BASE_URL') or env.get('ECNU_BASE_URL') or env.get('ECNU_MAX_BASE_URL') or ''
    if config.get('model_account_id'):pass  # Never fall back to a different key when the selected account is unconfigured.
    elif config.get('api_key'):config['api_key']=expand(config['api_key'])
    elif config.get('api_key_env'):config['api_key']=env.get(config['api_key_env'],'')
    else:config['api_key']=env.get('SCENE_API_KEY') or env.get('ECNU_API_KEY') or env.get('ECNU_MAX_API_KEY') or ''
    config['agent_model']=expand(config.get('agent_model')) or env.get('SCENE_AGENT_MODEL') or 'ecnu-plus'
    config.setdefault('agent_runtime','deepagents');config.setdefault('structured_output','json_object');config.setdefault('stream',True)
    config.setdefault('indexed_context',True);config.setdefault('max_context_tokens',200000)
    config.setdefault('supplement_tests',False)
    config.setdefault('max_retries',0)
    config.setdefault('stream_idle_timeout_seconds',300);config.setdefault('stream_total_timeout_seconds',900)
    return config

def public_settings(config):
    from .runtime_settings import KEYS
    allowed=KEYS-{'model_profiles','extra_body','stage_extra_body'}
    return {**{k:config[k] for k in allowed|set(('base_url','agent_model','max_concurrency','max_tokens','timeout_seconds','stream_idle_timeout_seconds','stream_total_timeout_seconds','stream','max_context_tokens','model_account_id','model_account_name','allowed_models')) if k in config},
      'model_profiles':{m:{k:v for k,v in p.items() if k in allowed} for m,p in config.get('model_profiles',{}).items()},'credential_configured':bool(config.get('api_key'))}
