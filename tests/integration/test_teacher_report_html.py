import json
import subprocess
from copy import deepcopy

import pytest

from scene_completion.application import ssd_revision_service as service
from scene_completion.domain.concern_registry import default_registry, registry_scope
from scene_completion.domain.current_scope import AVAILABILITY
from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.review.offline import adoption, business_report_export
from tests.support.paths import ROOT
from tests.support.shared_services import service_case
from tests.support.ssd_results import coverage_bundle


def test_teacher_report_offline_tables_filters_and_frozen_evidence(tmp_path):
    bundle = coverage_bundle()
    bundle["case"]["name"] = "浏览商品"
    bundle["steps"][0]["sender"]["name"] = "顾客"
    bundle["steps"][0]["operation"]["name"] = "顾客发送商品查询"
    check = deepcopy(bundle["steps"][0])
    check.update(id="verify", order=2)
    check["operation"]["name"] = "商城核对商品是否存在"
    bundle["steps"].append(check)
    auth = bundle["channels"]["G"]["scenarios"][-1]
    auth["analysis"] = "凭证格式校验会拒绝无法识别的凭证。"
    auth["source_refs"] = [
        {"document_id": "req", "start_line": 2, "end_line": 2, "quote": "凭证必须有效。"}
    ]
    bundle["documents"] = [
        {"id": "req", "name": "原始需求.md", "role": "RR", "content": "# 身份认证\n凭证必须有效。"},
        {
            "id": "sheet",
            "name": "原始测试.xlsx#验证",
            "role": "test",
            "content": "\n" * 119 + "| GT01 | 资源不存在 |",
        },
    ]
    auth_extra = {**deepcopy(auth), "id": "G-auth-extra", "condition": "Token签发方不受信任"}
    bundle["channels"]["G"]["scenarios"].append(auth_extra)
    permission = {
        **deepcopy(bundle["channels"]["G"]["concerns"][0]),
        "id": "G-permission",
        "key": "human.authorization",
        "label": "权限控制",
    }
    bundle["channels"]["G"]["concerns"].append(permission)
    bundle["channels"]["G"]["scenarios"].append(
        {
            **deepcopy(auth),
            "id": "G-perm-s",
            "key": permission["key"],
            "concern_ids": [permission["id"]],
            "condition": "无访问权限",
            "analysis": "",
        }
    )
    truth = {
        **deepcopy(bundle["channels"]["GT"]["scenarios"][0]),
        "id": "GT-extra",
        "condition": "资源不存在",
        "failure_step_id": "verify",
        "source_refs": [
            {"document_id": "sheet", "start_line": 120, "end_line": 120, "quote": "资源不存在"}
        ],
    }
    bundle["channels"]["GT"]["scenarios"].append(truth)
    for i, generated in enumerate(bundle["channels"]["G"]["scenarios"]):
        for gt in [truth] if i < 3 else bundle["channels"]["GT"]["scenarios"]:
            bundle["decisions"].append(
                {
                    "id": f"none-{gt['id']}-{generated['id']}",
                    "level": "scenario",
                    "pair": "GT_G",
                    "left_id": gt["id"],
                    "right_id": generated["id"],
                    "status": "none",
                    "origin": "manual",
                    "reason": "独立失败条件",
                }
            )
    service.publish(tmp_path, bundle)
    for case_id in ("A", "B"):
        common = service_case(case_id)
        for kind in ("concerns", "scenarios"):
            common["channels"]["GT"][kind] = [
                r for r in common["channels"]["GT"][kind] if r["key"] != AVAILABILITY
            ]
        service.publish(tmp_path, common)

    before = service.editor(tmp_path, "case")
    write_json(tmp_path / "run/run_manifest.json", {"ssd_cases": ["case", "A", "B", "C"]})
    current_registry = default_registry()
    definitions = current_registry["definitions"]
    definitions["human.authorization"]["enabled"] = False
    definitions["human.example-review"] = {
        **definitions["human.authorization"],
        "key": "human.example-review",
        "label": "项目自定义关注点",
        "enabled": True,
    }
    current_registry["hash"] = fingerprint(
        {k: v for k, v in current_registry.items() if k != "hash"}
    )
    with registry_scope(current_registry):
        document = business_report_export.export_html(tmp_path)
    assert not (tmp_path / "review_exports").exists()
    assert service.editor(tmp_path, "case")["bundle"] == before["bundle"]
    with pytest.raises(ValueError):
        adoption.parse(document)
    path = tmp_path / "教师报告.html"
    path.write_text(document, encoding="utf8")
    process = subprocess.run(
        [
            "node",
            str(ROOT / "tests/support/offline_teacher_report.mjs"),
            str(path),
            str(ROOT / "frontend/node_modules/jsdom/lib/api.js"),
        ],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["saved_reopened"]
