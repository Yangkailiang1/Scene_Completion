"""Independent interaction availability examples, with different calling contexts."""

from copy import deepcopy

from scene_completion.domain.current_scope import AVAILABILITY
from tests.support.ssd_results import coverage_bundle


def service_case(case_id="A", faults=("service_unavailable",), service_id="DB"):
    b = coverage_bundle()
    b["case"].update(id=case_id, name="用例 " + case_id)
    step = b["steps"][0]
    step["receiver"].update(
        id=service_id,
        name="外部数据库 " + service_id,
        type="service",
        external=True,
        technology="database",
    )
    step["operation"]["name"] = "执行 " + case_id
    b["gt_identification_run_complete"] = True
    b["decisions"] = []
    for channel, data in b["channels"].items():
        concern = deepcopy(b["channels"]["G"]["concerns"][0])
        concern.update(
            id=channel + "-availability",
            key=AVAILABILITY,
            label="服务可用性",
            target="receiver",
            condition="外部依赖可用",
        )
        data["concerns"].append(concern)
        for fault in faults:
            row = {
                **deepcopy(concern),
                "id": channel + "-" + fault,
                "concern_ids": [concern["id"]],
                "fault_type": fault,
                "condition": case_id + " " + fault,
                "expected": "按 " + case_id + " 的业务约定处理",
                "analysis": "说明 " + case_id,
            }
            data["scenarios"].append(row)
    return b
