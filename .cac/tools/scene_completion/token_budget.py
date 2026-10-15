"""Durable admission control for a bounded semantic-API token allowance."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
import time
import uuid

_LOCK = threading.RLock()


class TokenBudgetBlocked(RuntimeError):
    def __init__(self, reason, *, remaining=0, required=0):
        super().__init__('semantic token budget_exhausted or usage unresolved; inspect the token ledger')
        self.response_diagnostic = {'failure_category': 'budget_exhausted', 'budget_kind': 'tokens',
            'budget_reason': reason, 'remaining_tokens': remaining, 'required_reservation': required}


@contextmanager
def _locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.with_suffix(path.suffix + '.lock').open('a+b') as handle:
        if not handle.tell():
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class TokenBudget:
    def __init__(self, config):
        self.limit = config['token_budget_limit']
        if type(self.limit) is not int or self.limit < 1:
            raise ValueError('token_budget_limit must be a positive integer')
        if not config.get('token_budget_ledger'):
            raise ValueError('token_budget_ledger is required with token_budget_limit')
        self.path = Path(config['token_budget_ledger'])
        self.reasoning_reserve = config.get('token_budget_reasoning_reserve', 0)
        if type(self.reasoning_reserve) is not int or self.reasoning_reserve < 0:
            raise ValueError('token_budget_reasoning_reserve must be a nonnegative integer')

    def _read(self):
        data = json.loads(self.path.read_text(encoding='utf8')) if self.path.exists() else {
            'schema': 'semantic-token-budget-v1', 'limit': self.limit, 'requests': {}}
        if data.get('schema') != 'semantic-token-budget-v1' or data.get('limit') != self.limit:
            raise ValueError('token budget ledger identity/limit changed; do not reset a spent allowance')
        return data

    def _write(self, data):
        from .semantic_backend import write_json
        data['committed_tokens'] = sum(r.get('charged_tokens', 0) for r in data['requests'].values())
        data['reserved_tokens'] = sum(r['reservation'] for r in data['requests'].values() if r['status'] == 'reserved')
        data['remaining_tokens'] = self.limit - data['committed_tokens'] - data['reserved_tokens']
        write_json(self.path, data)

    def reserve(self, body):
        # UTF-8 bytes bound tokenization conservatively; never truncate evidence.
        reservation = sum(len(json.dumps(m, ensure_ascii=False).encode('utf8')) + 256
                          for m in body.get('messages', []))
        reservation += int(body['max_tokens']) + int(body.get('thinking_budget', 0))
        if body.get('enable_thinking') or body.get('thinking'):
            reservation += self.reasoning_reserve
        with _locked(self.path):
            data = self._read()
            rows = list(data['requests'].values())
            if any(r['status'] == 'usage_unknown' for r in rows):
                raise TokenBudgetBlocked('unresolved_previous_request')
            used = sum(r.get('charged_tokens', 0) + (r['reservation'] if r['status'] == 'reserved' else 0) for r in rows)
            if used + reservation > self.limit:
                raise TokenBudgetBlocked('insufficient_remaining_allowance', remaining=self.limit-used, required=reservation)
            request_id = uuid.uuid4().hex
            data['requests'][request_id] = {'model': body.get('model'), 'status': 'reserved',
                'reservation': reservation, 'started_unix': time.time()}
            self._write(data)
        return request_id

    def settle(self, request_id, *, usage=None, refused=False):
        with _locked(self.path):
            data = self._read(); row = data['requests'][request_id]
            if row['status'] != 'reserved':
                raise ValueError('token reservation was already settled')
            total = usage.get('total_tokens') if isinstance(usage, dict) else None
            if total is None and isinstance(usage, dict):
                p, c = usage.get('prompt_tokens'), usage.get('completion_tokens')
                if type(p) is int and type(c) is int and p >= 0 and c >= 0:
                    total = p + c
            if refused:
                row.update(status='refused', charged_tokens=0)
            elif type(total) is int and total > 0:
                row.update(status='complete', charged_tokens=total, reported_total_tokens=total)
            else:
                row.update(status='usage_unknown', charged_tokens=row['reservation'])
            row['finished_unix'] = time.time()
            self._write(data)
