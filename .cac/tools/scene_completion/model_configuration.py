"""Model identifiers are configuration, not an application allowlist."""
import os
import re
from .review import _resolve_env_reference


def model_name(value):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n\x00'):
        raise ValueError('model configuration must be a nonempty model identifier')
    resolved = _resolve_env_reference(value)
    if not resolved.strip() or '${' in resolved or any(c in resolved for c in '\r\n\x00'):
        raise ValueError('model configuration references an unset environment variable')
    return resolved.strip()


def configured_model(config, kind, default=None):
    legacy = {'agent': 'ECNU_MAX_MODEL', 'embedding': 'ECNU_EMBEDDING_TEXT', 'rerank': 'ECNU_RERANK'}[kind]
    value = config.get(kind+'_model')
    if value is None:
        value = os.environ.get('SCENE_'+kind.upper()+'_MODEL') or os.environ.get(legacy) or default
    return model_name(value)


def config_overrides(config, args):
    result = dict(config)
    for kind in ('agent', 'embedding'):
        value = getattr(args, kind+'_model', None)
        if value is not None:
            result[kind+'_model'] = value
    return result


def referenced_env_keys(config):
    keys=set()
    for name,value in config.items():
        if not isinstance(value,str):continue
        match=re.fullmatch(r'\$\{([A-Z][A-Z0-9_]*)\}',value.strip())
        if match:keys.add(match.group(1))
        if name=='api_key_env':keys.add(value)
    return keys


def native_result(result):
    evidence = result.get('execution_model_evidence', {})
    return (result.get('model') == 'gpt-6-luna' or isinstance(evidence, dict)
            and (evidence.get('provider') == 'native_subprocess' or 'native_execution' in evidence))
