"""Read verified machine baselines for reuse between SSD stages."""

from scene_completion.infrastructure import ssd_repository


def _machine_baselines(ex, cid):
    """Preparations may be published repeatedly before a failed stage resumes."""
    try:
        state = ssd_repository.state(ex.root.parent, cid)
    except ValueError:
        return
    yield state["baseline"]
    if state.get("previous_baseline"):
        yield state["previous_baseline"]
    for history in reversed(state.get("history", [])):
        snapshot = ssd_repository.revision(ex.root.parent, cid, history["revision"])["bundle"]
        # machine_g is captured before human overlays. Never reuse human G as model output.
        if snapshot.get("machine_g") or snapshot.get("semantic_comparison_identity"):
            yield snapshot
