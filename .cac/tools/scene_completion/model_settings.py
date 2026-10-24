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
            if not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):continue
            if len(value)>1 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
            values[key]=value
    return values

def resolve(overrides,env_path):
    env={**read_env(env_path),**os.environ};config=dict(overrides)
    def expand(v):
        m=re.fullmatch(r'\$\{([A-Z][A-Z0-9_]*)\}',str(v or ''))
        return env.get(m[1],'') if m else v
    config['base_url']=expand(config.get('base_url')) or env.get('SCENE_API_BASE_URL') or env.get('ECNU_BASE_URL') or env.get('ECNU_MAX_BASE_URL') or ''
    config['api_key']=config.get('api_key') or env.get(config.get('api_key_env','')) or env.get('SCENE_API_KEY') or env.get('ECNU_API_KEY') or env.get('ECNU_MAX_API_KEY') or ''
    config['agent_model']=expand(config.get('agent_model')) or env.get('SCENE_AGENT_MODEL') or 'ecnu-plus'
    config.setdefault('agent_runtime','deepagents');config.setdefault('structured_output','json_object');config.setdefault('stream',True)
    config.setdefault('max_retries',0)
    return config

def public_settings(config):
    return {**{k:config[k] for k in ('base_url','agent_model','max_concurrency','max_tokens','timeout_seconds','stream') if k in config},
      'credential_configured':bool(config.get('api_key'))}
