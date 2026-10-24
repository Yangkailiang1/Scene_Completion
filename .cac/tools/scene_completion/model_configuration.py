import os,re
from .http_transport import _resolve_env_reference

def model_name(value):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n\x00'):
        raise ValueError('model configuration must be a nonempty model identifier')
    resolved = _resolve_env_reference(value)
    if not resolved.strip() or '${' in resolved or any(c in resolved for c in '\r\n\x00'):
        raise ValueError('model configuration references an unset environment variable')
    return resolved.strip()


def concurrency_limit(value=1):
    if isinstance(value, str):
        if not value.isdecimal():
            raise ValueError('max_concurrency must be a positive integer')
        value = int(value)
    if type(value) is not int or value < 1:
        raise ValueError('max_concurrency must be a positive integer')
    return value


def request_effort(config):
    """Some thinking APIs accept a token budget but no effort parameter."""
    return config.get('reasoning_effort', 'high') if config.get('thinking') and config.get('send_reasoning_effort', True) else None


def referenced_env_keys(config):
    keys=set()
    for name,value in config.items():
        if not isinstance(value,str):continue
        match=re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}',value.strip())
        if match:keys.add(match.group(1))
        if name=='api_key_env':keys.add(value)
    return keys


def configured_model(config, kind='agent', default=None):
    if kind!='agent':raise ValueError('only the workflow agent model is supported')
    return model_name(config.get('agent_model') or os.environ.get('SCENE_AGENT_MODEL') or os.environ.get('ECNU_MAX_MODEL') or default)
