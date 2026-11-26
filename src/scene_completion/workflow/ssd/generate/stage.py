"""Run and validate business scenario analysis using positive inputs."""

from copy import deepcopy

from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.workflow.ssd.shared.machine_history import _machine_baselines
from scene_completion.workflow.ssd.shared.semantic_execution import _semantic_available


def _generate(ex, bundle, record):
    from scene_completion.workflow.ssd.generate.scenarios import (
        apply_result,
        batches,
        capture_machine,
        model_packet,
        restore_handles,
    )

    bundle = deepcopy(bundle)
    # A transport-handle repair does not invalidate already verified business analyses.
    # Reuse machine baselines only, never effective human edits or another channel.
    from scene_completion.workflow.ssd.generate.scenarios import regenerate_machine

    for previous in _machine_baselines(ex, bundle["case"]["id"]):
        # Preparation publishes first. Its previous baseline still owns the last
        # verified analyses; reading only "original" would discard that reuse.
        known = {r["id"]: r for r in regenerate_machine(bundle, previous)["scenarios"]}
        for row in bundle["channels"]["G"]["scenarios"]:
            if row.get("analysis"):
                continue
            source = known.get(row["id"], {})
            if source.get("analysis") and all(
                source.get(k) == row.get(k) for k in ("condition", "expected", "template_version")
            ):
                for key in (
                    "analysis",
                    "analysis_origin",
                    "analysis_version",
                    "generation_context",
                ):
                    if key in source:
                        row[key] = deepcopy(source[key])
    if _semantic_available(ex):
        for inputs in batches(bundle):
            projected, handles = model_packet(inputs)
            record["_short_id_mapping"] = {"scenarios": handles}
            result, _ = ex.semantic("ssd-generate", projected, record)
            apply_result(bundle, inputs, restore_handles(result, handles))
    capture_machine(bundle)
    return ssd_validation.validate(bundle)
