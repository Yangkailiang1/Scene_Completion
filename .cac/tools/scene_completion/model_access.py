"""Endpoint, credential and configuration bound access circuit breaker."""
from __future__ import annotations
import json,time,threading
from pathlib import Path
from .storage import fingerprint
_LOCK=threading.RLock()
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
            self.client.config.get('native_transport'), self.client.config.get('reasoning_effort'), self.client.config.get('thinking'),
            self.client.config.get('thinking_api','legacy'),self.client.config.get('stream',False), self.client.config.get('include_usage',False),
            self.client.config.get('send_reasoning_effort', True), self.client.config.get('thinking_budget')])

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
        from .storage import write_json
        with _LOCK:
            if self.path and self.path.exists():
                self.records = json.loads(self.path.read_text(encoding='utf8'))
            now = time.time()
            row = {'scope': self.scope(), 'kind': kind, 'model': model, 'status': 'available' if available else 'unavailable',
                'failure_category': category, 'checked_at': now, 'expires_at': now + int(self.client.config.get('availability_ttl_seconds', 900 if available else 300)),
                'execution_hash': fingerprint(proof) if proof else None}
            if isinstance(proof, dict):
                row.update(returned_model=proof.get('provider_model'),
                    thinking_control_sent=proof.get('thinking_control_sent'))
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
