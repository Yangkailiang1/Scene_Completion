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
    if kind == 'review':
        return model_name(config.get('review_model') or os.environ.get('SCENE_REVIEW_MODEL') or configured_model(config, 'agent'))
    legacy = {'agent': 'ECNU_MAX_MODEL', 'embedding': 'ECNU_EMBEDDING_TEXT', 'rerank': 'ECNU_RERANK'}[kind]
    value = config.get(kind+'_model')
    if value is None:
        value = os.environ.get('SCENE_'+kind.upper()+'_MODEL') or os.environ.get(legacy) or default
    return model_name(value)


def config_overrides(config, args):
    result = dict(config)
    for kind in ('agent', 'embedding', 'review'):
        value = getattr(args, kind+'_model', None)
        if value is not None:
            result[kind+'_model'] = value
    value = getattr(args, 'max_concurrency', None)
    if value is not None:
        result['max_concurrency'] = concurrency_limit(value)
    return result


def concurrency_limit(value=1):
    if isinstance(value, str):
        if not value.isdecimal():
            raise ValueError('max_concurrency must be a positive integer')
        value = int(value)
    if type(value) is not int or value < 1:
        raise ValueError('max_concurrency must be a positive integer')
    return value


def review_policy(config):
    selected = config.get('review_model') or os.environ.get('SCENE_REVIEW_MODEL') or configured_model(config, 'agent')
    return {'model': model_name(selected), 'runtime': config.get('review_runtime', config.get('agent_runtime', 'openai-compatible')),
        'reasoning_effort': config.get('review_reasoning_effort', request_effort(config))}


def request_effort(config):
    """Some thinking APIs accept a token budget but no effort parameter."""
    return config.get('reasoning_effort', 'high') if config.get('thinking') and config.get('send_reasoning_effort', True) else None


def matches_review_policy(root, review):
    from pathlib import Path
    import json
    path = Path(root)/'run_manifest.json'
    run = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
    policy = run.get('review_policy')
    if policy is None:
        # Historical evidence retains its original, explicit reviewer identity.
        policy = {'model': 'gpt-6-luna', 'reasoning_effort': 'max'}
    return (review.get('model') == policy['model']
        and review.get('reasoning_effort') == policy['reasoning_effort']
        and ('runtime' not in policy or review.get('runtime') == policy['runtime']))


def review_policy_at(directory):
    from pathlib import Path
    import json
    for parent in [Path(directory), *Path(directory).parents]:
        path = parent/'run_manifest.json'
        if path.exists():
            run = json.loads(path.read_text(encoding='utf8'))
            if 'review_policy' in run:
                return run['review_policy']
    return {'model': 'gpt-6-luna', 'reasoning_effort': 'max'}  # historical compatibility only


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
