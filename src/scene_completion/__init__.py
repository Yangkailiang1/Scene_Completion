"""Scene Completion: the current evidence-based analysis workflow."""

__all__ = ["PROTOCOL", "TASKS"]


def __getattr__(name):
    if name in __all__:
        from .domain import contracts

        value = getattr(contracts, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))
