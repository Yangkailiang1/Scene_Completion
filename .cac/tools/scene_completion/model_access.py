"""Cheap capability probes and endpoint/credential-bound access circuit breakers."""
from __future__ import annotations
import json
import time
import threading
from pathlib import Path
from .sources import fingerprint
from .model_configuration import concurrency_limit, model_name, configured_model, config_overrides, referenced_env_keys

_LOCK = threading.RLock()
_PROBE_LOCK = threading.RLock()


class ModelUnavailable(RuntimeError):
    def __init__(self, category, model):
        super().__init__('configured model is not accessible; inspect model_access.json and select an available configuration')
        self.response_diagnostic = {'failure_category': category, 'model': model, 'configuration_required': True}


class AccessRegistry:
    def __init__(self, client):
        self.client = client
        cache = client.config.get('availability_cache') or (str(Path(client.config['cache_dir']) / 'model_access.json') if client.config.get('cache_dir') else None)
        self.path = Path(cache) if cache else None
        self.records = {}

    def scope(self):
        return fingerprint([getattr(self.client, 'base_url', self.client.config.get('agent_runtime', 'native')),
            fingerprint(getattr(self.client, 'api_key', 'local-cli-auth')),
            self.client.config.get('native_transport'), self.client.config.get('reasoning_effort'), self.client.config.get('thinking'),self.client.config.get('stream',False)])

    def key(self, kind, model):
        return fingerprint([self.scope(), kind, model])

    def current(self, kind, model):
        with _LOCK:
            if self.path and self.path.exists():
                self.records = json.loads(self.path.read_text(encoding='utf8'))
            row = self.records.get(self.key(kind, model))
            return row if row and row['expires_at'] > time.time() else None

    def guard(self, kind, model):
        row = self.current('endpoint', '*') or self.current(kind, model)
        if row and row['status'] == 'unavailable':
            raise ModelUnavailable(row['failure_category'], model)

    def record(self, kind, model, *, available, category=None, proof=None):
        from .semantic_backend import write_json
        with _LOCK:
            if self.path and self.path.exists():
                self.records = json.loads(self.path.read_text(encoding='utf8'))
            now = time.time()
            row = {'scope': self.scope(), 'kind': kind, 'model': model, 'status': 'available' if available else 'unavailable',
                'failure_category': category, 'checked_at': now, 'expires_at': now + int(self.client.config.get('availability_ttl_seconds', 900 if available else 300)),
                'execution_hash': fingerprint(proof) if proof else None}
            self.records[self.key(kind, model)] = row
            if self.path:
                write_json(self.path, self.records)
            return row


def registry(client):
    if not hasattr(client, '_model_access'):
        client._model_access = AccessRegistry(client)
    return client._model_access


def access_category(exc):
    diagnostic = getattr(exc, 'response_diagnostic', {}) or {}
    category = diagnostic.get('failure_category')
    if category in ('model_unavailable', 'authentication_failed', 'access_denied'):
        return category
    status = diagnostic.get('http_status')
    return {401: 'authentication_failed', 403: 'access_denied', 404: 'model_unavailable'}.get(status)


def probe(client, kind='agent', *, force=False):
    with _PROBE_LOCK:
        from .performance import span
        with span(getattr(client,'profiler',None),'probe',stage='model-availability',request_kind=kind):
            return _probe(client, kind, force=force)


def _probe(client, kind='agent', *, force=False):
    model = client.model(kind)
    access = registry(client)
    if force:
        with _LOCK:
            if access.path and access.path.exists():
                access.records = json.loads(access.path.read_text(encoding='utf8'))
            access.records.pop(access.key(kind, model), None)
            access.records.pop(access.key('endpoint', '*'), None)
            if access.path:
                from .semantic_backend import write_json
                write_json(access.path, access.records)
    access.guard(kind, model) if not force else None
    cached = access.current(kind, model)
    if cached and not force:
        if cached['status'] == 'unavailable':
            raise ModelUnavailable(cached['failure_category'], model)
        return {**cached, 'cached': True}
    try:
        if kind == 'embedding':
            values = client._embed_uncached(['model availability probe'])
            if len(values) != 1 or not values[0]:
                raise ValueError('invalid embedding probe')
            proof = {'model': model, 'dimension': len(values[0])}
        else:
            packet = {'stage': 'model-availability', 'input': {}, 'instructions': ['Return {"ok":true}. Do not use tools.'],
                'output_contract': {'ok': True}, 'batch_id': 'model-availability', 'input_hash': fingerprint([access.scope(), model])}
            result = client.agent(packet)
            if result.get('ok') is not True:
                raise ValueError('model probe did not return the required structured output')
            proof = result.get('execution_model_evidence', {'model': model})
        return {**access.record(kind, model, available=True, proof=proof), 'cached': False}
    except Exception as exc:
        category = access_category(exc)
        if category:
            access.record(kind, model, available=False, category=category)
            if category == 'authentication_failed':
                access.record('endpoint', '*', available=False, category=category)
            raise ModelUnavailable(category, model) from exc
        diagnostic=getattr(exc,'response_diagnostic',{}) or {}
        if diagnostic.get('failure_category') in ('quota_exhausted','rate_limited'):
            raise
        # An invalid configuration or nonconforming probe must not be retried
        # separately by every ready use-case stage with the same settings.
        access.record(kind,model,available=False,category='preflight_failed')
        blocked=ModelUnavailable('preflight_failed',model)
        blocked.response_diagnostic.update(cause_category=diagnostic.get('failure_category','probe_format_error'),
            http_status=diagnostic.get('http_status'))
        raise blocked from exc


def preflight(client, kind='agent'):
    if client.config.get('model_preflight', 'auto') == 'off':
        return {'status': 'disabled', 'kind': kind}
    return probe(client, kind)


def with_embedding_preflight(client, texts, compute):
    cache = Path(client.config['cache_dir']) if client.config.get('cache_dir') else None
    keys = [fingerprint([client.base_url, client.model('embedding'), text]) for text in texts]
    if any(key not in client._vectors and not (cache and (cache/(key+'.json')).exists()) for key in keys):
        preflight(client, 'embedding')
    return compute(texts)


def configured_client(config, root, *, review=False):
    from .semantic_backend import SemanticClient
    if review:
        from .model_configuration import review_policy
        policy = review_policy(config)
        config = {**config, 'agent_model': policy['model'], 'agent_runtime': policy['runtime'],
            'reasoning_effort': policy['reasoning_effort'],
            'thinking': config.get('review_thinking', policy['reasoning_effort'] is not None)}
    if config.get('agent_runtime') == 'luna-subprocess':
        from .luna_subprocess import LunaSubprocessClient
        return LunaSubprocessClient({**config, 'native_run_dir': str(Path(root).resolve()/'native-probes')})
    return SemanticClient(config)


def check_models(args):
    from .role_cli import _client
    from .semantic_backend import SemanticClient, read_json, write_json
    from .review import load_ecnu_env_file
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    agent = _client(args, root)
    candidates = getattr(args, 'candidate_model', None) or [agent.model('agent')]
    if not getattr(args, 'candidate_model', None) and agent.config.get('candidate_models'):
        candidates = agent.config['candidate_models']
    rows = []
    catalog = []
    catalog_status = 'not_requested'
    if getattr(args, 'discover', False) and hasattr(agent, 'base_url'):
        import urllib.request
        try:
            request = urllib.request.Request(agent.base_url + '/models', headers={'Authorization':'Bearer '+agent.api_key}, method='GET')
            with urllib.request.urlopen(request, timeout=min(60, float(agent.config.get('timeout_seconds', 60)))) as response:
                data = json.loads(response.read().decode('utf8'))
            catalog = sorted({r['id'] for r in data.get('data', []) if isinstance(r, dict) and isinstance(r.get('id'), str)})
            catalog_status = 'listed_not_yet_probed'
        except Exception:
            catalog_status = 'catalog_unavailable'
    for selected in dict.fromkeys(candidates):
        config = {**agent.config, 'agent_model': model_name(selected)}
        client = configured_client(config, root)
        try:
            rows.append(probe(client, force=getattr(args, 'refresh', False)))
        except Exception as exc:
            rows.append({'kind': 'agent', 'model': selected, 'scope': registry(client).scope(), 'status': 'unavailable' if access_category(exc) else 'unknown',
                'failure_category': getattr(exc, 'response_diagnostic', {}).get('failure_category', 'probe_failed')})
            if rows[-1]['failure_category'] in ('authentication_failed', 'quota_exhausted'):
                break
    if getattr(args, 'include_review', False):
        reviewer = configured_client(agent.config, root, review=True)
        try:
            rows.append({**probe(reviewer, force=getattr(args, 'refresh', False)), 'kind': 'review'})
        except Exception as exc:
            rows.append({'kind': 'review', 'model': reviewer.model('agent'), 'scope': registry(reviewer).scope(),
                'status': 'unavailable' if access_category(exc) else 'unknown',
                'failure_category': getattr(exc, 'response_diagnostic', {}).get('failure_category', 'probe_failed')})
    if getattr(args, 'include_embedding', False):
        embedding_path = getattr(args, 'embedding_config', None) or getattr(args, 'config', None)
        config = config_overrides(read_json(embedding_path) if embedding_path else {}, args)
        if getattr(args, 'env_file', None):
            load_ecnu_env_file(args.env_file, extra_keys=referenced_env_keys(config))
        config['cache_dir'] = str(root / '.embedding_cache')
        embedding = SemanticClient(config)
        try:
            rows.append(probe(embedding, 'embedding', force=getattr(args, 'refresh', False)))
        except Exception as exc:
            rows.append({'kind': 'embedding', 'model': embedding.model('embedding'), 'scope': registry(embedding).scope(),
                'status': 'unavailable' if access_category(exc) else 'unknown', 'failure_category': getattr(exc, 'response_diagnostic', {}).get('failure_category', 'probe_failed')})
    result = {'complete': True, 'models': rows, 'catalog': catalog, 'catalog_status': catalog_status,
        'configured_max_concurrency': concurrency_limit(agent.config.get('max_concurrency', 1)),
        'suggested_max_concurrency': 1, 'note': 'Probe is serial; success does not establish provider concurrency capacity.'}
    write_json(root / 'available_models.json', result)
    return result, 0 if any(r['status'] == 'available' for r in rows) else 2


def configure_models(args):
    from .semantic_backend import read_json, write_json
    report = read_json(args.checked_report)
    config = read_json(args.config) if args.config else {}
    config = config_overrides(config, args)
    from .review import load_ecnu_env_file
    if getattr(args, 'env_file', None):
        load_ecnu_env_file(args.env_file, extra_keys=referenced_env_keys(config))
    from .semantic_backend import SemanticClient
    embedding_config = None
    if getattr(args, 'embedding_config', None):
        if not getattr(args, 'output_embedding_config', None):
            raise ValueError('independent embedding configuration requires --output-embedding-config')
        embedding_config = read_json(args.embedding_config)
        if getattr(args, 'embedding_model', None):
            embedding_config['embedding_model'] = args.embedding_model
        if getattr(args, 'env_file', None):
            load_ecnu_env_file(args.env_file, extra_keys=referenced_env_keys(embedding_config))
    for kind in ('agent', 'embedding', 'review'):
        selected = getattr(args, kind + '_model', None)
        if kind == 'agent' and selected is None:
            selected = configured_model(config, 'agent')
        if selected is None:
            continue
        selected = model_name(selected)
        selected_client = (SemanticClient(embedding_config or config) if kind == 'embedding' else
            configured_client(config, Path(args.output_config).parent, review=kind == 'review'))
        peers = [r for r in report['models'] if r['kind'] in (('agent', 'review') if kind == 'review' else (kind,))
            and r['model'] == selected and r['status'] == 'available' and r.get('expires_at', 0) > time.time()]
        if not peers:
            raise ValueError('selected model has no current successful capability probe: ' + kind)
        if not any(r['scope'] == registry(selected_client).scope() for r in peers):
            raise ValueError('model probe belongs to a different endpoint, credential or execution configuration')
    config.setdefault('max_concurrency', 1)
    config['max_concurrency'] = concurrency_limit(config['max_concurrency'])
    config.setdefault('model_preflight', 'auto')
    config.setdefault('adaptive_concurrency', True)
    if embedding_config is not None:
        write_json(args.output_embedding_config, embedding_config)
    write_json(args.output_config, config)
    return {'complete': True, 'config': str(Path(args.output_config).resolve()),
        'max_concurrency': config['max_concurrency']}, 0
