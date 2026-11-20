"""Determine model capability and stable SSD semantic cache identity."""


def _semantic_available(ex):
    return (
        getattr(ex, "client", None) is not None
        or getattr(ex, "mode", "packets") in {"external", "responses"}
        or getattr(ex, "mocks", None) is not None
    )


def _semantic_cache_identity(ex, stage):
    """A skipped semantic stage is not a completed model analysis.

    Model/account selection remains operational and does not invalidate valid
    analyses; capability, execution provenance and task contracts do.
    """
    if stage not in {"ssd-generate", "ssd-resolve", "ssd-compare"}:
        return None
    from scene_completion.workflow.semantics import code_version

    task = "ssd-semantic-compare" if stage == "ssd-compare" else stage
    result = {
        "available": _semantic_available(ex),
        "mode": getattr(ex, "mode", "packets"),
        "mock": getattr(ex, "mocks", None) is not None,
        "artifact_identity": getattr(ex, "artifact_identity", {}),
        "semantic_task": task,
        "semantic_version": code_version(task),
        **(
            {
                "supporting_semantics": {
                    task: code_version(task)
                    for task in (
                        "ssd-bind",
                        "ssd-operation-units",
                        "ssd-entity-inference",
                        "ssd-entity-classify",
                        "ssd-command-classify",
                        "ssd-evidence-classify",
                    )
                }
            }
            if stage == "ssd-resolve"
            else {}
        ),
    }
    if stage == "ssd-compare":
        result["grounding_version"] = code_version("ssd-ground-align")
    return result
