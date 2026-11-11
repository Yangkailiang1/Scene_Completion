"""Shared worker admission and adaptive cooldown."""

import threading
import time
from contextlib import contextmanager
from pathlib import Path


def concurrency_limit(value=1):
    if isinstance(value, str):
        if not value.isdecimal():
            raise ValueError("max_concurrency must be a positive integer")
        value = int(value)
    if type(value) is not int or value < 1:
        raise ValueError("max_concurrency must be a positive integer")
    return value


class AdmissionGate:
    def __init__(self, concurrency=1, *, adaptive=True, on_change=None, pause_file=None):
        self.limit = concurrency_limit(concurrency)
        self.effective_limit = self.limit
        self.adaptive = adaptive
        self.on_change = on_change
        self.pause_file = Path(pause_file) if pause_file else None
        self.condition = threading.Condition()
        self.active = 0
        self.retry_not_before = 0.0

    @contextmanager
    def slot(self):
        with self.condition:
            while self.active >= self.effective_limit or time.monotonic() < self.retry_not_before:
                self.condition.wait(timeout=max(0.05, self.retry_not_before - time.monotonic()))
            self.active += 1
        try:
            yield
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()

    def cooldown(self, seconds):
        with self.condition:
            if self.adaptive:
                self.effective_limit = max(1, self.effective_limit // 2)
            self.retry_not_before = max(
                self.retry_not_before,
                time.monotonic() + max(1.0, min(300.0, seconds)),
            )
            self.condition.notify_all()
        if self.on_change:
            self.on_change(
                {
                    "configured_max": self.limit,
                    "effective_max": self.effective_limit,
                    "not_before_unix": time.time()
                    + max(0, self.retry_not_before - time.monotonic()),
                }
            )
