"""Apply provider transport diagnostics to the shared admission gate."""

import threading
import time

from scene_completion.workflow_core import TaskBlocked
from scene_completion.workflow_core.admission import AdmissionGate


class CallGate(AdmissionGate):
    def __init__(self, concurrency=1, *, adaptive=True, on_change=None, pause_file=None):
        super().__init__(concurrency, adaptive=adaptive, on_change=on_change, pause_file=pause_file)
        self.quota = threading.Event()

    def observe(self, diagnostic):
        if not isinstance(diagnostic, dict) or diagnostic.get("failure_category") != "rate_limited":
            return
        self.cooldown(float(diagnostic.get("retry_after_seconds") or 30))

    def call(self, function, *args, **kwargs):
        from scene_completion.infrastructure.execution_events import emit, phase

        body = next(
            (v for v in args if isinstance(v, dict) and v.get("model")), kwargs.get("body", {})
        )
        model = body.get("model") if isinstance(body, dict) else None
        for retry in range(4):
            with self.slot():
                if self.pause_file and self.pause_file.exists():
                    raise TaskBlocked("pending", {"admission_paused": True})
                if self.quota.is_set():
                    raise TaskBlocked("budget_exhausted", {"quota": True})
                try:
                    return function(*args, **kwargs)
                except Exception as e:
                    d = getattr(e, "response_diagnostic", None)
                    if not d or not d.get("failure_category"):
                        raise
                    if d["failure_category"] == "rate_limited":
                        delay = float(d.get("retry_after_seconds") or (2 ** (retry + 1)))
                        delay = max(0.0, min(300.0, delay))
                        self.observe({**d, "retry_after_seconds": delay})
                        if retry == 3:
                            raise TaskBlocked(
                                "rate_limited",
                                {"transport_failure": d, "retry_count": retry, "recoverable": True},
                            ) from e
                        at = time.time() + max(delay, self.retry_not_before - time.monotonic())
                        phase("rate_limit_wait", retry_at=at, retry_count=retry + 1, retry_limit=3)
                        emit(
                            "rate_limit_wait",
                            retry_at=at,
                            retry_count=retry + 1,
                            retry_limit=3,
                            diagnostic=d,
                        )
                        continue
                    if d["failure_category"] in {"quota_exhausted", "budget_exhausted"}:
                        if (
                            model
                            and d.get("budget_kind") == "tokens"
                            and d.get("budget_reason") != "insufficient_provider_allowance"
                        ):
                            # Admission is request-specific: another model, a
                            # smaller request, or released in-flight reserves
                            # may still fit. Never latch a global quota flag.
                            raise TaskBlocked(
                                "budget_exhausted", {**d, "model": model, "model_scope": True}
                            ) from e
                        else:
                            self.quota.set()
                        raise TaskBlocked("budget_exhausted", d) from e
                    if d.get("configuration_required"):
                        raise TaskBlocked("awaiting_configuration", d) from e
                    raise TaskBlocked("pending", {"transport_failure": d}) from e
        raise AssertionError("bounded retry exhausted")
