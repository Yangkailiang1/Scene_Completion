"""Prepare the initial SSD revision from either supported input path."""

from copy import deepcopy

from scene_completion.application import ssd_revision_service
from scene_completion.domain.ssd.validation import validate
from scene_completion.inputs.documents.ssd_adapter import normalize_extracted_case
from scene_completion.workflow.ssd.generate.fixed import generate_g
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.prepare.snapshot import pin_core


def structured(ex, directory, case_id, file, problem, test_claims=None):
    if problem:
        raise ValueError(problem)
    bundles = build_cases(
        directory, [case_id], case_files=[file], generate=False, test_claims=test_claims
    )
    if len(bundles) != 1:
        raise ValueError("当前用例没有唯一可用的结构化执行输入")
    bundle = validate(bundles[0])
    # Pin the exact model-independent core used for all downstream stages.
    bundle["core_snapshot"] = pin_core(ex.root, directory, bundle)
    bundle["registry"] = deepcopy(ex.registry_snapshot)
    bundle["analysis_policy"] = ex.registry_snapshot["analysis_policy"]
    bundle["channels"]["G"] = generate_g(bundle)
    ssd_revision_service.publish(ex.root.parent, bundle)
    return bundle


def extracted(ex, case, fused, parameters, entities, branches, tests, documents):
    bundle = normalize_extracted_case(case, fused, parameters, entities, branches, tests, documents)
    bundle["registry"] = deepcopy(ex.registry_snapshot)
    bundle["channels"]["G"] = generate_g(bundle)
    ssd_revision_service.publish(ex.root.parent, bundle)
    return bundle
