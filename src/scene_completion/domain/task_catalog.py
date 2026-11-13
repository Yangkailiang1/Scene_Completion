"""Semantic task roles shared by runtimes, routing, events and usage views."""

CHECKER_TASKS = {
    "ssd-resolve",
    "ssd-semantic-compare",
    "test-additional-concerns",
    "existing-concerns",
    "test-concerns",
    "concern-compare",
    "concern-evaluation",
    "existing-branches",
    "existing-bind",
    "existing-extract",
    "gap-compare",
    "semantic-compare",
    "test-ground-truth",
    "test-supplement",
    "test-additional-truth",
    "test-additional-dedup",
    "test-expanded",
    "missing-report",
    "exception-evaluation",
    "extraction-evaluation",
    "global-existing-concerns",
    "global-existing-scenarios",
    "global-test-concerns",
    "global-test-scenarios",
    "global-scenario-match",
    "exception-scope",
    "existing-locations",
}


def role_for(task):
    if task in {"test-inventory", "test-case-align"}:
        return "checker"
    if task in {"gap-recommend", "global-recommend"}:
        return "recommender"
    return "checker" if task in CHECKER_TASKS else "modeler"
