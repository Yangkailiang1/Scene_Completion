"""Replay the published browse-product route with an in-process semantic test client."""

import json
import re

from fastapi.testclient import TestClient

from scene_completion.api.application import create_app
from scene_completion.cli.main import main
from scene_completion.infrastructure.storage import read_json
from tests.support.model_accounts_cli import FakeAPI
from tests.support.paths import ROOT

CASE = "UC-BROWSE-01"
SOURCE = ROOT / "datasets/mini-mall/examples/browse-product"


class BrowseProductClient:
    """Fixed answers for the published sample only. Every packet uses the real validator."""

    base_url = "http://offline.invalid"
    api_key = "offline-fixture"

    def __init__(self, config, root):
        self.config = config

    def model(self, kind):
        return "browse-product-offline"

    def agent(self, packet):
        data = packet["input"]
        task = packet["task"]
        if task == "ssd-operation-units":
            return {
                "operations": [
                    {
                        "unit_id": unit["id"],
                        "step_id": unit["step_id"],
                        "crud": ["read"],
                        "reason": "两个请求均按条件读取商品目录",
                    }
                    for unit in data["units"]
                ]
            }
        if task == "ssd-generate":
            return {
                "analyses": [
                    {"scenario_id": row["id"], "analysis": "离线样例核对：" + row["condition"]}
                    for row in data["templates"]
                ],
                "supplements": [],
            }
        if task == "ssd-evidence-classify":
            rows = []
            for record in data["records"]:
                condition = record["condition"]
                key = {
                    "pageSize < 1": "api.data.range",
                    "pageSize > 100": "api.data.range",
                    "keyword 长度 > 32": "api.data.length",
                }.get(condition)
                if not key:
                    assert condition in {"未找到符合筛选条件的商品", "pageSize=1 或 pageSize=100"}
                rows.append(
                    {
                        "record_id": record["id"],
                        "kind": "exception" if key else "normal",
                        "reason": "依据本条条件及预期",
                        "parts": [
                            {"condition": condition, "expected": record["expected"], "keys": [key]}
                        ]
                        if key
                        else [],
                    }
                )
            return {"records": rows}
        if task == "ssd-ground-align":
            rows = []
            for part in data["parts"]:
                fallback = None
                if part["condition"] == "keyword 长度 > 32":
                    field = next(
                        f
                        for f in data["interface_fields"]
                        if f["name"] == "keyword" and f["command_id"] == "BROWSE-GET"
                    )
                    fallback = dict(
                        step_id="B1",
                        key="api.data.length",
                        target="interface",
                        field_id=field["id"],
                        entity_id=None,
                        attribute=None,
                        operation_unit_id=None,
                    )
                rows.append(
                    {
                        "part_id": part["id"],
                        **(
                            {
                                "failure_step_id": "B2",
                                "failure_step_reason": "分支指向 B2 参数校验之后",
                            }
                            if data["channel"] == "E" and part["failure_step_hint"]
                            else {}
                        ),
                        "matches": [
                            {
                                "candidate_id": c["id"],
                                "status": "full" if c["condition"] == part["condition"] else "none",
                                "reason": "逐项核对字段与边界",
                            }
                            for c in part["candidates"]
                        ],
                        "fallback": fallback,
                        "reason": "按样例的请求字段与失败条件定位",
                    }
                )
            return {"parts": rows}
        if task == "ssd-semantic-compare":
            return {
                "decisions": [
                    {
                        "left_id": pair["left"]["id"],
                        "right_id": pair["right"]["id"],
                        "status": "full"
                        if pair["left"]["condition"] == pair["right"]["condition"]
                        else "none",
                        "reason": "核对同一独立失败条件",
                    }
                    for pair in data["pairs"]
                ]
            }
        raise AssertionError("未登记的离线样例任务：" + task)


def test_browse_product_route(tmp_path, capsys):
    core = tmp_path / "core/001"
    data_dir = tmp_path / "workbench"
    env = tmp_path / "empty.env"
    env.touch()
    local = ["--local", "--data-dir", str(data_dir), "--env-file", str(env)]
    selected = ["--case", CASE]

    def cli(args):
        assert main(args) == 0
        return json.loads(capsys.readouterr().out)

    inspected = cli(["core-input", "inspect", "--input", str(SOURCE), *selected])
    converted = cli(
        ["core-input", "convert", "--input", str(SOURCE), "--output", str(core), *selected]
    )
    assert inspected["input_hash"] == converted["input_hash"]
    assert cli(["core-input", "validate", "--input", str(core), *selected])["valid"]
    folder = next((core / "cases").iterdir())
    handoff = read_json(folder / "main-success.json")
    field = next(row for row in handoff["data_obligations"] if row["name"] == "pageSize")
    assert field["command_id"] == "BROWSE-GET" and field["step_id"] == "B1"
    source_map = read_json(folder / "source-map.json")
    constraints = source_map["interface_fields"][field["field_id"]]["constraints"]
    upper = next(c for c in constraints if c["operation"] == "maximum")
    assert any(
        ref.get("json_pointer") == "/functions/0/srLayer/commands/0/attributes/1/constraints/0"
        for ref in upper["source_refs"]
    )
    assert any(
        ref["file"] == "功能设计_spec.md" and ref["start_line"] == 10
        for ref in upper["source_refs"]
    )
    rid = cli(
        [
            *local,
            "create",
            "--name",
            "浏览商品离线验收",
            "--input-dir",
            str(core),
            "--adopt-partial",
            "--mode",
            "auto",
            *selected,
        ]
    )["id"]

    with TestClient(
        create_app(data_dir, client_factory=BrowseProductClient, env_file=env)
    ) as client:
        args = ["run", "--project", rid, *selected, "--wait", "--poll", "0.2", "--timeout", "90"]
        rc = main(args, client=FakeAPI(client))
        lines = capsys.readouterr().out.splitlines()
        assert rc == 0, lines[-2:]
        tasks = read_json(data_dir / rid / "run/workflow_tasks.json")["tasks"]
        stages = (
            "ssd-prepare",
            "ssd-resolve",
            "ssd-generate",
            "ssd-compare",
            "shared-services-merge",
        )
        assert {key: task["status"] for key, task in tasks.items()} == {
            f"{CASE}:{stage}": "passed" for stage in stages
        }
        view = cli([*local, "results", "--project", rid, *selected])
        bundle = view["bundle"]
        assert bundle["coverage_policy"] == "coverage-g-obligation-v3"
        high = next(
            row
            for row in view["comparison"]["scenarios"]
            if row.get("generated_id") and row["cells"]["G"][0]["condition"] == "pageSize > 100"
        )
        assert high["cells"]["G"][0]["field_id"] == field["field_id"]
        assert high["cells"]["E"][0]["failure_step_id"] == "B2"
        assert high["cells"]["GT"][0]["condition"] == "pageSize > 100"
        assert any(
            ref["start_line"] == 5 and (ref.get("origin") or {}).get("document") == "test_browse.md"
            for ref in high["cells"]["GT"][0]["source_refs"]
        )
        response = client.post(f"/api/projects/{rid}/ssd-review/report", json={})
        response.raise_for_status()
        report = json.loads(
            re.search(
                r'<script[^>]*id="ssd-business-report-data"[^>]*>(.*?)</script>',
                response.text,
                re.S,
            )[1]
        )
        assert "异常场景完整性补全识别结果" in response.text
        assert report["report"]["concern_options"]["human.authentication"] == "身份认证"
        group = next(g for g in report["report"]["groups"] if g["case_id"] == CASE)
        covered = {row["text"].splitlines()[-1]: row for row in group["categories"]["covered"]}
        assert set(covered) == {"具体异常 · pageSize < 1", "具体异常 · pageSize > 100"}
        upper = covered["具体异常 · pageSize > 100"]
        assert upper["text"].startswith("实际失败步骤 · B2 商城校验 B1 的查询参数")
        assert any(
            ref.get("kind") == "origin" and ref["start_line"] == 4
            for step in upper["step_evidence"]
            for ref in step["source_refs"]
        )
        (gt_only,) = group["categories"]["gt_only"]
        assert gt_only["text"].startswith("实际失败步骤 · B2 商城校验 B1 的查询参数")
        assert gt_only["text"].endswith("具体异常 · keyword 长度 > 32")
        assert group["categories"]["g_only"]
        delivery = tmp_path / "delivery"
        delivery.mkdir()
        (delivery / "异常场景完整性补全识别结果.html").write_text(response.text, encoding="utf8")
