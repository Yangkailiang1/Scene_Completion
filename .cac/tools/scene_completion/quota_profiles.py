"""Audited configured profile selection and transport/quota succession."""
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


def _provider_scope(client):
    """Return a non-secret account identity for fail-closed profile checks."""
    config = getattr(client, 'config', {})
    credential = config.get('api_key_env')
    if isinstance(credential, str) and credential.strip():
        return ('credential-env', credential.strip())
    return ('endpoint', fingerprint(getattr(client, 'base_url', 'native')))


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
        budget_path = Path(root) / 'batch_budget_bindings.json'
        bindings = [{'model': c.model('agent'), 'ledger': str(c.token_budget.path.resolve()),
            'limit': c.token_budget.limit} if getattr(c, 'token_budget', None) else {'model': c.model('agent'), 'ledger': None}
            for c in clients]
        # Continuing after unknown usage is safe only when every request for
        # this provider is covered by one shared, locked allowance. In
        # particular, a preferred-profile jump must not strand an earlier
        # profile's unknown reservation outside the aggregate ledger set.
        for client in clients:
            budget = getattr(client, 'token_budget', None)
            if not budget or budget.unknown_policy != 'reserve_and_continue':
                continue
            config = client.config
            if (budget.provider_limit is None or not budget.peers
                    or not config.get('provider_token_budget_lock')):
                raise ValueError('reserve_and_continue requires a shared provider token limit, peer ledgers, and provider lock')
            same_provider = [other for other in clients if _provider_scope(other) == _provider_scope(client)]
            if any(not getattr(other, 'token_budget', None) for other in same_provider):
                raise ValueError('reserve_and_continue cannot cover a same-provider profile without a token ledger')
            same_provider_ledgers = {other.token_budget.path.resolve() for other in same_provider}
            configured_peers = {path.resolve() for path in budget.peers}
            if not same_provider_ledgers <= configured_peers:
                raise ValueError('reserve_and_continue peer ledgers must include every configured profile for this provider')
        if budget_path.exists():
            prior_bindings = read_json(budget_path)
            if bindings[:len(prior_bindings)] != prior_bindings:
                raise ValueError('model budget ledger identity changed; do not reset an allowance by changing its path')
        write_json(budget_path, bindings)
        self.chain_hash = fingerprint(profiles)
        self.state = read_json(self.path) if self.path.exists() else {
            'chain_hash': self.chain_hash, 'profiles': profiles, 'active_index': 0, 'transitions': []}
        if self.state.get('chain_hash') != self.chain_hash:
            prior = self.state.get('profiles', [])
            if profiles[:len(prior)] != prior or len(profiles) <= len(prior):
                raise ValueError('configured model chain changed; only append-only configured fallbacks preserve routing history')
            self.state.setdefault('chain_extensions', []).append({'at_unix': time.time(),
                'previous_hash': self.state['chain_hash'], 'new_hash': self.chain_hash})
            self.state.update(profiles=profiles, chain_hash=self.chain_hash)
        if type(self.state.get('active_index')) is not int or not 0 <= self.state['active_index'] < len(clients):
            raise ValueError('invalid persistent batch model index')
        preferred = clients[0].config.get('batch_preferred_profile_index')
        if preferred is not None:
            if type(preferred) is not int or not 0 <= preferred < len(clients):
                raise ValueError('batch_preferred_profile_index must name a configured profile')
            if preferred > self.state['active_index']:
                reason = clients[0].config.get('batch_profile_selection_reason')
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError('explicit profile selection requires batch_profile_selection_reason')
                self.state['transitions'].append({'at_unix': time.time(),
                    'from_index': self.state['active_index'], 'to_index': preferred,
                    'reason': 'configured_profile_selection', 'basis': reason})
                self.state['active_index'] = preferred
        write_json(self.path, self.state)

    def current(self):
        with self.lock:
            index = self.state['active_index']
            return index, self.clients[index], self.gates[index]

    def guard_usage(self):
        # A profile switch cannot conceal a request whose actual usage was
        # lost. Check all configured ledgers for this account, including
        # profiles skipped by an explicit preferred-index selection. A
        # reserve_and_continue profile is allowed only after __init__ proves
        # its shared provider cap covers these ledgers.
        active = self.current()[1]
        active_budget = getattr(active, 'token_budget', None)
        if active_budget and active_budget.unknown_policy == 'reserve_and_continue':
            return
        scope = _provider_scope(active)
        for client in self.clients:
            budget = getattr(client, 'token_budget', None)
            if not budget or _provider_scope(client) != scope or not budget.path.exists():
                continue
            data = read_json(budget.path)
            if any(r.get('status') == 'usage_unknown' for r in data.get('requests', {}).values()):
                raise TaskBlocked('budget_exhausted', {'failure_category': 'budget_exhausted',
                    'budget_reason': 'unresolved_previous_request', 'model': active.model('agent'),
                    'unresolved_model': client.model('agent')})

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
            index, client, gate = self.current()
            budget = getattr(client, 'token_budget', None)
            if budget and budget.path.exists() and client.config.get('timeout_handoff'):
                data = read_json(budget.path)
                if any(r['status'] == 'usage_unknown' for r in data.get('requests', {}).values()):
                    self.advance(index, 'timeout_handoff_unknown_usage_retained')
                    continue
            self.guard_usage()
            try:
                gate.call(preflight, client)
                result = gate.call(run_agent_packets, folder, client, validator, batch_ids=[batch_id])
            except TaskBlocked as exc:
                reason = quota_reason(exc.details) or quota_reason(getattr(exc, 'response_diagnostic', {}))
                if (client.config.get('timeout_handoff') and isinstance(exc.details, dict)
                        and exc.details.get('cause_category') in ('transport_timeout', 'connection_failed', 'stream_incomplete')):
                    self.advance(index, 'preflight_transport_handoff')
                    continue
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
            if client.config.get('timeout_handoff') and any(r.get('failure_category') in ('transport_timeout', 'connection_error', 'connection_failed', 'stream_incomplete') for r in result.get('batches', [])):
                self.advance(index, 'transport_timeout_handoff')
                continue
            if not reason:
                return result
            self.advance(index, reason)
