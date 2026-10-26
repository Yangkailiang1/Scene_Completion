"""Local API-key scoped model catalog. Secrets never leave server-side storage."""
from pathlib import Path
from copy import deepcopy
from threading import RLock
import json,os,re,time
from uuid import uuid4
from .model_settings import read_env

LOCK=RLock()
FILE='model-accounts.local.json'

def _read(root):
    f=Path(root)/FILE
    return json.loads(f.read_text()) if f.exists() else {'revision':0,'accounts':[]}

def _write(root,value):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);target=root/FILE;temp=root/('.'+FILE+'.'+uuid4().hex)
    try:
        with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:
            json.dump(value,out,ensure_ascii=False,indent=2);out.flush();os.fsync(out.fileno())
        os.replace(temp,target)
        try:target.chmod(0o600)
        except OSError:pass
    finally:temp.unlink(missing_ok=True)

def credential(account,env_file):
    if account.get('api_key_env'):return {**read_env(env_file),**os.environ}.get(account['api_key_env'],'')
    return account.get('api_key','')

def public_accounts(root,env_file):
    v=_read(root)
    return {'revision':v['revision'],'accounts':[{k:a[k] for k in ('id','name','base_url','models','updated_at')} | {'credential_configured':bool(credential(a,env_file)),'credential_source':'environment' if a.get('api_key_env') else 'local'} for a in v['accounts']]}

def save_account(root,body,env_file):
    with LOCK:
        value=_read(root)
        if body.get('expected_revision')!=value['revision']:raise ValueError('连接配置已变化，请刷新')
        aid=body.get('id') or uuid4().hex
        if not isinstance(aid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',aid):raise ValueError('连接ID格式无效')
        old=next((a for a in value['accounts'] if a['id']==aid),{})
        if any(not isinstance(body.get(k,''),str) for k in ('name','base_url','api_key','api_key_env')):raise ValueError('连接名称、地址和凭证必须为文本')
        name=body.get('name','').strip();url=body.get('base_url','').strip();models=body.get('models')
        from urllib.parse import urlsplit
        parsed=urlsplit(url)
        if not name or len(name)>100 or any(c in name for c in '\r\n\x00'):raise ValueError('请填写连接名称')
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('请填写不含凭证和查询参数的OpenAI兼容Base URL')
        if not isinstance(models,list) or not 1<=len(models)<=200 or any(not isinstance(m,str) or not m.strip() or len(m)>200 or any(c in m for c in '\r\n\x00') for m in models):raise ValueError('请填写该API Key可用的模型标识列表')
        models=list(dict.fromkeys(m.strip() for m in models));a={'id':aid,'name':name,'base_url':url.rstrip('/'),'models':models,'updated_at':time.time()}
        env=body.get('api_key_env','').strip();key=body.get('api_key','').strip()
        if env:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',env):raise ValueError('环境变量名无效')
            a['api_key_env']=env
        elif key:
            if any(c in key for c in '\r\n\x00'):raise ValueError('API Key格式无效')
            a['api_key']=key
        else:a.update({k:old[k] for k in ('api_key','api_key_env') if k in old})
        if not a.get('api_key') and not a.get('api_key_env'):raise ValueError('需要API Key或服务端环境变量名')
        value['accounts']=[a if r['id']==aid else r for r in value['accounts']]
        if not old:value['accounts'].append(a)
        value['revision']+=1;_write(root,value)
        return public_accounts(root,env_file)

def apply_account(config,root,env_file):
    cfg=deepcopy(config);aid=cfg.get('model_account_id')
    if not aid:return cfg
    if root is None:raise ValueError('API Key连接配置需要工作台数据目录')
    a=next((a for a in _read(root)['accounts'] if a['id']==aid),None)
    if not a:raise ValueError('选择的模型连接不存在，请重新配置')
    chosen=cfg.get('agent_model') or a['models'][0]
    selections=[chosen]+list(cfg.get('task_models',{}).values())+list(cfg.get('role_models',{}).values())
    if any(m not in a['models'] for m in selections):raise ValueError('所选模型不在此API Key的允许模型列表中')
    cfg.update(base_url=a['base_url'],api_key=credential(a,env_file),agent_model=chosen,account_label=a['name'],model_account_name=a['name'],allowed_models=a['models'])
    cfg.pop('api_key_env',None)
    return cfg
