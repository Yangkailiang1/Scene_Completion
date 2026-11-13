"""Offline test support extracted without changing builder behavior."""

from tests.support.workflow import (
    R,
    memory_inputs,
    scenario,
)


def inverse_fixture():
    x = memory_inputs()
    i = x["sr-ssd"]["interactions"][0]
    s = scenario("parameter-branch", status="explicit")
    s.update(
        interaction_id=i["id"],
        object=i["receiver"]["name"],
        operation=i["operation"]["name"],
        cause="invalid_parameters",
        conditions=["请求参数非法"],
        concern_key="api.data.range",
        scope="interface",
        data_location=None,
        original_branch_id="b",
        coverage_kind="input_parameters",
    )
    inputs = {
        "fused-ssd": {"interactions": [i], "rr_sr_links": []},
        "normal-constraints": x["api-parameters"],
        "branches": {"branches": [{"id": "b", "description": "参数非法", "source_refs": R}]},
        "bindings": {
            "bindings": [{"branch_id": "b", "interaction_id": i["id"], "status": "confirmed"}]
        },
    }
    return x, s, inputs


__all__ = ["inverse_fixture"]
