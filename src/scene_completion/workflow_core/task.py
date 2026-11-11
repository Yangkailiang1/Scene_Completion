"""Task definitions and outcomes shared by schedulers and callers."""

from dataclasses import dataclass


class TaskBlocked(Exception):
    def __init__(self, status, details):
        super().__init__(str(details))
        self.status = status
        self.details = details


class TaskRejected(Exception):
    def __init__(self, details):
        super().__init__(str(details))
        self.details = details


@dataclass
class Task:
    key: str
    case: str
    stage: str
    deps: tuple = ()
    version: object = None
    execute: object = None
    repair: object = None
    verify: object = None
    deferred: bool = False
    display_label: str | None = None
    attempt_identity: str | None = None
    recoverable: bool = False
