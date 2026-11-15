import json
import subprocess

from scene_completion.application import ssd_revision_service as service
from scene_completion.review.offline import adoption
from tests.support.paths import ROOT
from tests.support.ssd_results import coverage_bundle


def test_offline_html_adoption_save_reopen_and_source_rendering(tmp_path):
    bundle = coverage_bundle()
    bundle["documents"] = [
        {"id": "RR", "name": "系统需求.md", "content": "# 认证要求\n必须有合法凭证。"}
    ]
    bundle["channels"]["G"]["scenarios"][-1]["source_refs"] = [
        {"document_id": "RR", "start_line": 1, "end_line": 2, "quote": "必须有合法凭证。"}
    ]
    service.publish(tmp_path, bundle)
    path = tmp_path / "审核.html"
    path.write_text(adoption.export_html(tmp_path, {"scopes": ["interaction"]}), encoding="utf8")
    result = subprocess.run(
        [
            "node",
            str(ROOT / "tests/support/offline_adoption.mjs"),
            str(path),
            str(ROOT / "frontend/node_modules/jsdom/lib/api.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["saved_reopened"]


def test_grouped_five_auth_scenarios_keep_independent_decisions_and_bindings(tmp_path):
    from copy import deepcopy

    bundle = coverage_bundle()
    bundle["channels"]["GT"] = {"concerns": [], "scenarios": [], "pending": []}
    bundle["decisions"] = []
    base = deepcopy(bundle["channels"]["G"]["scenarios"][0])
    bundle["channels"]["G"]["scenarios"] = [
        {
            **deepcopy(base),
            "id": f"G-{i}",
            "condition": condition,
            "label": "身份认证",
            "analysis": "核对当前操作中的凭证失败原因",
            "expected": "拒绝当前认证失败调用",
        }
        for i, condition in enumerate(
            ["未携带凭证", "凭证格式错误", "空凭证", "Token校验失败", "Token过期"]
        )
    ]
    concern = {**deepcopy(bundle["channels"]["G"]["concerns"][0]), "id": "E-concern"}
    scenario = {
        **deepcopy(base),
        "id": "E-auth",
        "condition": "Authorization未提供或无效",
        "concern_ids": ["E-concern"],
    }
    bundle["documents"] = [
        {
            "id": "RR",
            "name": "系统需求.md",
            "role": "RR",
            "content": "# 认证\nAuthorization必须有效。",
        }
    ]
    ref = {"document_id": "RR", "start_line": 2, "end_line": 2, "quote": "Authorization必须有效。"}
    bundle["steps"][0]["source_refs"] = [ref]
    scenario["source_refs"] = [ref]
    bundle["channels"]["E"] = {"concerns": [concern], "scenarios": [scenario], "pending": []}
    service.publish(tmp_path, bundle)
    path = tmp_path / "分组审核.html"
    path.write_text(adoption.export_html(tmp_path, {"scopes": ["interaction"]}), encoding="utf8")
    result = subprocess.run(
        [
            "node",
            str(ROOT / "tests/support/offline_grouped.mjs"),
            str(path),
            str(ROOT / "frontend/node_modules/jsdom/lib/api.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["five_distinct"]


def test_restyle_preserves_prior_review_payload_and_does_not_create_export(tmp_path):
    service.publish(tmp_path, coverage_bundle())
    payload = adoption.export_payload(tmp_path, {"scopes": ["interaction"]})
    payload["decisions"] = [
        {
            "item_id": payload["items"][0]["id"],
            "g_id": "G-third",
            "adopted": True,
            "comment": "已有审核意见",
        }
    ]
    exports = sorted((tmp_path / "review_exports").iterdir())
    html = adoption.render_html(payload)
    assert adoption.parse(html) == payload
    assert adoption.parse(adoption.render_html(html)) == payload
    assert sorted((tmp_path / "review_exports").iterdir()) == exports
    assert adoption.feedback(tmp_path, html)["summary"]["ready"] == 1
    assert adoption.feedback(tmp_path, html, apply=True)["summary"]["applied"] == 1
    assert adoption.feedback(tmp_path, html, apply=True)["summary"]["unchanged"] == 1
