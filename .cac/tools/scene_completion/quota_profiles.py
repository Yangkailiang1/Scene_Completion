"""Configured quota-only model succession; semantic failures never change model."""
import threading
import time
import copy
from pathlib import Path

from .case_dag import TaskBlocked
from .sources import fingerprint
from .semantic_backend import read_json, write_json, run_agent_packets


def configured_clients(args, root, primary):
    from .role_cli import _client
    paths = primary.config.get('batch_fallback_configs', [])
    if not isinstance(paths, list) or any(not isinstance(p, str) or not p for p in paths):
        raise ValueError('batch_fallback_configs must be an ordered list of configuration paths')
    clients = [primary]
    for number, value in enumerate(paths, 1):
        path = Path(value)
        if not path.is_absolute() and not path.exists():
            path = Path(args.config).resolve().parent / path
        selected = copy.copy(args)
        selected.config = str(path)
        selected.agent_model = selected.agent_runtime = None
        client = _client(selected, Path(root) / ('batch-profile-' + str(number)))
        client.profiler = getattr(primary, 'profiler', None)
        clients.append(client)
    return clients


def identity(client):
    from .model_configuration import request_effort
    return {'model': client.model('agent'), 'endpoint_hash': fingerprint(getattr(client, 'base_url', 'native')),
        'thinking': bool(client.config.get('thinking')), 'reasoning_effort': request_effort(client.config),
        'thinking_budget': client.config.get('thinking_budget')}


def quota_reason(value):
    """Classify only provider/admission quota, never source-validation text."""
    if not isinstance(value, dict):
        return None
    for child in ('response_diagnostic', 'transport_failure'):
        if isinstance(value.get(child), dict):
            found = quota_reason(value[child])
            if found:
                return found
    if value.get('budget_reason') == 'unresolved_previous_request':
        return 'usage_unresolved'
    if value.get('failure_category') in {'quota_exhausted', 'budget_exhausted', 'insufficient_quota'}:
        return value.get('budget_reason') or value['failure_category']
    for row in value.get('batches', []):
        found = quota_reason(row)
        if found:
            return found
    return None


class BatchProfiles:
    def __init__(self, root, clients, gate):
        if not clients:
            raise ValueError('batch profiles require a primary client')
        self.clients = clients
        for client in clients:
            client.config.update(max_concurrency=1, semantic_max_attempts=1)
        self.gates = [gate.budget_scope() for _ in clients]
        self.path = Path(root) / 'batch_model_state.json'
        self.lock = threading.RLock()
        profiles = [identity(c) for c in clients]
        self.chain_hash = fingerprint(profiles)
        self.state = read_json(self.path) if self.path.exists() else {
            'chain_hash': self.chain_hash, 'profiles': profiles, 'active_index': 0, 'transitions': []}
        if self.state.get('chain_hash') != self.chain_hash:
            raise ValueError('configured model chain changed; preserve its existing routing history before changing profiles')
        if type(self.state.get('active_index')) is not int or not 0 <= self.state['active_index'] < len(clients):
            raise ValueError('invalid persistent batch model index')
        write_json(self.path, self.state)

    def current(self):
        with self.lock:
            index = self.state['active_index']
            return index, self.clients[index], self.gates[index]

    def guard_usage(self):
        # A profile switch cannot conceal a request whose actual usage was
        # lost. In-flight reservations are not unknown settled requests.
        for client in self.clients:
            budget = getattr(client, 'token_budget', None)
            if budget and budget.path.exists():
                data = read_json(budget.path)
                if any(r['status'] == 'usage_unknown' for r in data.get('requests', {}).values()):
                    raise TaskBlocked('budget_exhausted', {'failure_category': 'budget_exhausted',
                        'budget_reason': 'unresolved_previous_request', 'model': client.model('agent')})

    def advance(self, failed_index, reason):
        with self.lock:
            if reason == 'usage_unresolved':
                raise TaskBlocked('budget_exhausted', {'failure_category': 'budget_exhausted',
                    'budget_reason': 'unresolved_previous_request', 'model': self.clients[failed_index].model('agent')})
            if self.state['active_index'] != failed_index:
                return
            if failed_index + 1 >= len(self.clients):
                raise TaskBlocked('budget_exhausted', {'failure_category': 'quota_exhausted',
                    'all_configured_profiles_exhausted': True, 'model': self.clients[failed_index].model('agent')})
            self.state['active_index'] += 1
            self.state['transitions'].append({'at_unix': time.time(), 'from_index': failed_index,
                'to_index': self.state['active_index'], 'reason': reason})
            write_json(self.path, self.state)

    def run_batch(self, folder, validator, batch_id):
        from .model_access import preflight
        while True:
            self.guard_usage()
            index, client, gate = self.current()
            try:
                gate.call(preflight, client)
                result = gate.call(run_agent_packets, folder, client, validator, batch_ids=[batch_id])
            except TaskBlocked as exc:
                reason = quota_reason(exc.details) or quota_reason(getattr(exc, 'response_diagnostic', {}))
                if (exc.status == 'awaiting_configuration' and isinstance(exc.details, dict)
                        and exc.details.get('failure_category') in ('model_unavailable', 'access_denied')):
                    # A configured fallback can be listed in a catalog while
                    # this credential cannot invoke it. Preserve the probe
                    # rejection and try the next explicitly configured model.
                    self.advance(index, 'configured_profile_' + exc.details['failure_category'])
                    continue
                if exc.status != 'budget_exhausted' or not reason:
                    raise
                self.advance(index, reason)
                continue
            reason = quota_reason(result)
            if not reason:
                return result
            self.advance(index, reason)
