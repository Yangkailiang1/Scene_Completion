import copy
import json
import os
import tempfile
from pathlib import Path

from openpyxl import load_workbook
from tests.test_scene_completion import sample_model
from tools.scene_completion.assembly import _merge_equivalent_database_failures, assemble_results
from tools.scene_completion.concerns import plan_concern_matrix, validate_concern_matrix
from tools.scene_completion.exporters import export_workbooks
from tools.scene_completion.review import _batch_payload, load_ecnu_env_file, review_concerns
from tools.scene_completion.schemas import validate_scene_model
from tools.scene_completion.ssd import generate_ssd_bundle, validate_ssd
from tools.scene_completion.ssd import write_ssd_bundle
from tools.scene_completion.png_renderer import convert_svg_to_png, find_svg_converter
from tools.scene_completion.svg_renderer import render_system_composition_svg


def test_v6_normalization_and_non_data_routing():
    model = sample_model()
    model["version"] = "6"
    model["use_cases"][0]["architecture"]["sr"]["service_type"] = "resource_mutation"
    normalized = validate_scene_model(model)["normalized_model"]
    rr_services = [
        node for node in normalized["system_composition"]["nodes"]
        if node.get("kind") == "abstract_service" and node.get("layer") == "RR"
    ]
    assert len(rr_services) == len(normalized["use_cases"])

    bundle = generate_ssd_bundle(model, "UC-001")
    matrix = plan_concern_matrix(model, bundle["fused"])
    keys = {item["concern_key"] for item in matrix["items"]}
    assert "internal_service.resource_mutation.business_constraint" in keys
    assert "service_relation.call_order" in keys
    assert any(item["status"] == "pending_review" for item in matrix["items"])
    assert not validate_concern_matrix(model, matrix, require_complete=True)["valid"]


def test_v6_semantic_duplicate_messages_are_rejected():
    model = sample_model()
    model["version"] = "6"
    bundle = generate_ssd_bundle(model, "UC-001")
    duplicate = copy.deepcopy(bundle["fused"])
    duplicate["messages"].append(copy.deepcopy(duplicate["messages"][0]))
    report = validate_ssd(duplicate, model)
    assert not report["valid"]
    assert any("duplicate" in error.lower() for error in report["errors"])


def test_png_outputs_are_generated_when_local_converter_exists():
    if not find_svg_converter():
        return
    with tempfile.TemporaryDirectory() as tmp:
        svg = Path(tmp) / "sample.svg"
        png = Path(tmp) / "sample.png"
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="red"/></svg>', encoding="utf-8")
        result = convert_svg_to_png(svg, png, require=True)
        assert result["status"] == "rendered"
        assert png.exists() and png.read_bytes().startswith(b"\x89PNG")

    model = sample_model()
    model["version"] = "6"
    bundle = generate_ssd_bundle(model, "UC-001")
    with tempfile.TemporaryDirectory() as tmp:
        manifest = write_ssd_bundle(bundle, model, tmp)
        assert all(Path(item["png"]).exists() for item in manifest["artifacts"].values())


def test_v7_actor_and_external_service_associations_reach_ellipse_sides():
    model = sample_model()
    model["version"] = "6"
    sr_service = next(node for node in model["system_composition"]["nodes"] if node["node_id"] == "sr-order")
    sr_service.update({"name": "OrderService"})
    model["system_composition"]["edges"].append({"edge_id": "EDGE-EXT", "from_node": "sr-order", "to_node": "ext-service", "relation": "sr_external_dependency"})
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    associations = [edge for edge in normalized["system_composition"]["edges"] if edge.get("relation") in {"participates_in", "uses_external_service"}]
    assert any(edge["from_node"] == "user" and edge["use_case_id"] == "UC-001" for edge in associations)
    assert any(edge["to_node"] == "ext-service" and edge["use_case_id"] == "UC-001" for edge in associations)
    with tempfile.TemporaryDirectory() as tmp:
        svg = render_system_composition_svg(normalized, Path(tmp) / "system.svg").read_text(encoding="utf-8")
    assert 'data-relation="participates_in"' in svg
    assert 'data-relation="uses_external_service"' in svg
    assert '<path data-relation="participates_in"' in svg
    assert '<path data-relation="uses_external_service"' in svg


def test_v7_matrix_workbook_has_real_exchange_uc_and_timeout_only_tab():
    model = sample_model()
    model["version"] = "6"
    matrix = plan_concern_matrix(model)
    for item in matrix["items"]:
        item.update({"status": "not_applicable", "basis": "该交换没有此类异常依据", "evidence_types": ["ssd"]})
    timeout = next(item for item in matrix["items"] if item["concern_key"] == "common.timeout")
    timeout.update({"status": "needs_requirement", "basis": "缺少服务时限要求", "requirement_impact": "unknown", "subsequent_behavior_impact": "unknown", "environment_coordination_impact": "unknown"})
    assert validate_concern_matrix(model, matrix, require_complete=True)["valid"]
    bundle = assemble_results(model, matrix, {"findings": []})
    with tempfile.TemporaryDirectory() as tmp:
        paths = export_workbooks(bundle, tmp)
        workbook = load_workbook(paths["scenario_workbook"], read_only=True, data_only=True)
        assert workbook.sheetnames == ["场景清单", "关注点矩阵", "超时判断"]
        concern = workbook["关注点矩阵"]
        headers = [concern.cell(3, col).value for col in range(1, concern.max_column + 1)]
        assert "交互ID" not in headers
        assert any("用例ID" in str(value) for value in headers)
        assert all(concern.cell(row, headers.index("用例ID") + 1).value for row in range(4, concern.max_row + 1))
        timeout_sheet = workbook["超时判断"]
        timeout_headers = [timeout_sheet.cell(3, col).value for col in range(1, timeout_sheet.max_column + 1)]
        assert "需求满足影响" in timeout_headers
        assert timeout_sheet.max_row - 3 == sum(item["concern_key"] == "common.timeout" for item in matrix["items"])
        impact_col = timeout_headers.index("需求满足影响") + 1
        impact_values = [timeout_sheet.cell(row, impact_col).value for row in range(4, timeout_sheet.max_row + 1)]
        assert "待需求确认" in impact_values
        assert all(value in {"待需求确认", "—", "yes", "no"} for value in impact_values)
        matrix_sheet = workbook["关注点矩阵"]
        matrix_headers = [matrix_sheet.cell(3, col).value for col in range(1, matrix_sheet.max_column + 1)]
        message_col = matrix_headers.index("交互消息") + 1
        assert all(matrix_sheet.cell(row, message_col).value for row in range(4, matrix_sheet.max_row + 1))


def test_v7_source_scenarios_survive_version_six_and_get_exception_predictions():
    model = sample_model()
    model["version"] = "6"
    model["use_cases"][0]["scenarios"] = [
        {"scenario_id": "UC-001-main", "scenario_type": "main", "anchor_step_index": 0, "steps": model["use_cases"][0]["main_flow"]},
        {"scenario_id": "UC-001-alt", "scenario_type": "alternative", "anchor_step_index": 1, "steps": [{"step_index": 1, "text": "默认查询订单"}]},
        {"scenario_id": "UC-001-error", "scenario_type": "requirement_exception", "anchor_step_index": 2, "anchor_label": "2.a", "steps": [{"step_index": 1, "text": "查询订单"}, {"step_index": 2, "text": "订单不存在，系统提示"}], "trigger": "订单不存在", "expected_result": "提示订单不存在", "recovery": "结束分支", "source_location": "fixture.md:10"},
    ]
    matrix = plan_concern_matrix(model)
    for item in matrix["items"]:
        item.update({"status": "not_applicable", "basis": "该交换没有此类异常依据", "evidence_types": ["ssd"]})
    bundle = assemble_results(model, matrix, {"findings": []})
    types = [item["scenario_type"] for item in bundle["scenario_catalog"]]
    assert "main_success" in types
    assert "alternative" in types
    exception = next(item for item in bundle["scenario_catalog"] if item["scenario_type"] == "requirement_exception")
    assert exception["prediction_id"]
    assert exception["concern_key"] == ""
    assert exception["concern"] == "需求来源异常（非关注点）"
    assert any(item["scenario_id"] == exception["scenario_id"] for item in bundle["findings"])


def test_v7_requirement_exception_trace_nodes_are_resolved_from_ssd(tmp_path):
    model = sample_model()
    model["version"] = "6"
    model["use_cases"][0]["scenarios"] = [{
        "scenario_id": "UC-001-main", "scenario_type": "main", "anchor_step_index": 0,
        "steps": model["use_cases"][0]["main_flow"],
    }, {
        "scenario_id": "UC-001-error", "scenario_type": "requirement_exception", "anchor_step_index": 2,
        "anchor_label": "2.a", "steps": [{"step_index": 1, "text": "提交查询"}, {"step_index": 2, "text": "系统拒绝请求"}],
        "trigger": "参数非法", "expected_result": "返回400", "recovery": "修改后重试", "source_location": "fixture.md:10",
    }]
    bundle_ssd = generate_ssd_bundle(model, "UC-001")
    manifest = write_ssd_bundle(bundle_ssd, model, tmp_path / "ssd")
    matrix = plan_concern_matrix(model)
    for item in matrix["items"]:
        item.update({"status": "not_applicable", "basis": "该交换没有此类异常依据", "evidence_types": ["ssd"]})
    assembled = assemble_results(model, matrix, {"findings": []}, {"use_cases": [manifest]})
    exception = next(item for item in assembled["scenario_catalog"] if item["scenario_type"] == "requirement_exception")
    assert exception["source_node"] and exception["target_node"]
    prediction = next(item for item in assembled["findings"] if item.get("exception_origin") == "requirement_branch")
    assert prediction["source_node"] and prediction["target_node"]


def test_v7_database_availability_merges_same_failure_and_preserves_all_trace_refs():
    model = sample_model()
    target = "int-db"
    common = {
        "use_case_id": "UC-001", "source_step_index": 2, "target_node": target,
        "target_node_name": "内部数据库", "concern_key": "internal_database.availability",
        "expected_result": "请求失败并返回服务暂不可用。", "recovery": "提示稍后重试。",
        "trigger": "数据库连接失败。", "source_node": "impl-order", "source_node_name": "订单服务",
        "layer": "AR", "interaction_message": "查询资源", "source_location": "fixture.md:12",
    }
    items = [
        {**common, "exception_type": "数据库连接失败", "exception_desc": "商品查询失败。", "exchange_id": "EX-1", "ssd_message_id": "MSG-1"},
        {**common, "exception_type": "数据库不可用", "exception_desc": "库存读取失败。", "exchange_id": "EX-2", "ssd_message_id": "MSG-2"},
        {**common, "exception_type": "DatabaseUnavailableException", "exception_desc": "价格读取失败。", "exchange_id": "EX-3", "ssd_message_id": "MSG-3"},
    ]
    merged = _merge_equivalent_database_failures(items, validate_scene_model(model)["normalized_model"])
    assert len(merged) == 1
    assert merged[0]["exception_type"] == "数据库不可用"
    assert set(merged[0]["related_exchange_ids"]) == {"EX-1", "EX-2", "EX-3"}
    assert set(merged[0]["related_ssd_message_ids"]) == {"MSG-1", "MSG-2", "MSG-3"}
    different_recovery = {**items[1], "recovery": "由管理员恢复后重新查询。"}
    separate = _merge_equivalent_database_failures([items[0], different_recovery], validate_scene_model(model)["normalized_model"])
    assert len(separate) == 2
    paraphrased = [
        {**items[0], "expected_result": "系统应提示错误信息，如‘商品加载失败’", "recovery": "提示用户稍后重试，恢复后继续主流程。"},
        {**items[1], "expected_result": "系统提示‘商品加载失败，请稍后重试’", "recovery": "提示后结束或回到主流程。"},
        {**items[2], "expected_result": "商品查询失败，系统返回错误信息", "recovery": "按该分支处理后结束或回到主流程。"},
    ]
    merged_paraphrases = _merge_equivalent_database_failures(paraphrased, validate_scene_model(model)["normalized_model"])
    assert len(merged_paraphrases) == 1
    assert set(merged_paraphrases[0]["related_exchange_ids"]) == {"EX-1", "EX-2", "EX-3"}


def test_v7_batch_review_uses_exchange_batches_and_resumes_without_network(tmp_path, monkeypatch):
    model = sample_model()
    model["version"] = "6"
    model["use_cases"][0]["architecture"]["ar"][0]["microservice_id"] = "compute"
    bundle = generate_ssd_bundle(model, "UC-001")
    ssd_root = tmp_path / "ssds"
    manifest = write_ssd_bundle(bundle, model, ssd_root)
    matrix = plan_concern_matrix(model, ssd_manifest={"use_cases": [manifest]})
    for item in matrix["items"]:
        if item["concern_key"] != "common.timeout":
            item.update({"status": "not_applicable", "basis": "本次批测仅验证超时候选", "evidence_types": ["ssd"]})
    monkeypatch.setenv("ECNU_MAX_API_KEY", "not-a-real-secret")
    calls = []

    def fake_post(url, api_key, body, timeout, retries):
        calls.append((url, api_key, body))
        payload = json.loads(body["messages"][1]["content"].split("输入数据：", 1)[1])
        key = payload["candidates"][0]["concern_key"]
        if len(calls) == 1:
            malformed = {"items": [{"concern_key": key, "status": "needs_requirement"}]}
            return {"choices": [{"message": {"content": json.dumps(malformed)}}]}
        response = {"items": [{"concern_key": key, "status": "needs_requirement", "basis": "资料没有给出时限指标", "evidence_types": ["requirement"], "findings": [], "requirement_impact": "", "subsequent_behavior_impact": "", "environment_coordination_impact": ""}]}
        return {"choices": [{"message": {"content": json.dumps(response)}}]}

    config = {"base_url": "https://example.invalid/v1", "model": "mock", "api_key_env": "ECNU_MAX_API_KEY", "max_concurrency": 2, "json_mode": False}
    output = tmp_path / "reviewed.json"
    first = review_concerns(model, {"use_cases": [manifest]}, matrix, config, output, post=fake_post)
    expected_batches = len({item["exchange_id"] for item in matrix["items"] if item["status"] == "pending_review"})
    assert first["valid"] and len(calls) == expected_batches + 1
    call_count = len(calls)
    second = review_concerns(model, {"use_cases": [manifest]}, matrix, config, output, post=fake_post)
    assert second["valid"] and len(calls) == call_count
    assert all(call[1] == "not-a-real-secret" for call in calls)

    assembled_matrix = json.loads(output.read_text(encoding="utf-8"))
    candidate = next(item for item in assembled_matrix["items"] if item["concern_key"] != "common.timeout")
    candidate.update({
        "status": "applicable",
        "basis": "SSD/API evidence confirms a validated input boundary",
        "evidence_types": ["ssd", "api_contract"],
        "findings": [{
            "exception_type": "invalid input",
            "exception_desc": "An invalid request value is rejected.",
            "trigger": "Submit a value outside the interface contract.",
            "scenario_steps": ["Submit invalid data.", "The system returns a validation error."],
            "recovery": "Correct the value and retry.",
            "source_step_index": candidate.get("source_step_index") or 1,
        }],
    })
    assembled = assemble_results(model, assembled_matrix, {"findings": []}, {"use_cases": [manifest]})
    assert assembled["findings"]
    assert assembled["findings"][0]["exchange_id"] == candidate["exchange_id"]


def test_v7_review_payload_includes_matching_api_contract_constraints():
    model = sample_model()
    model["interfaces"] = [{
        "name": "API-S-IF1", "abstract_api_id": "API-S-IF1", "method": "GET", "path": "/products",
        "validation_rules": [{"field": "pageSize", "rule": "1<=pageSize<=100", "source_location": "design.md:12"}],
    }]
    candidate = {"use_case_id": "UC-001", "concern_key": "api.data.range"}
    exchange = {"use_case_id": "UC-001", "messages": [{
        "message_id": "REQ-1", "exchange_id": "EX-1", "message_kind": "request", "abstract_api_id": "API-S-IF1", "message": "查询商品",
    }]}
    payload = _batch_payload(model, "EX-1", [candidate], exchange)
    assert payload["api_contracts"][0]["validation_rules"][0]["field"] == "pageSize"

def test_ecnu_env_file_loader_only_reads_standard_keys(tmp_path, monkeypatch):
    for key in ("ECNU_MAX_MODEL", "ECNU_MAX_API_KEY", "ECNU_MAX_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ECNU_MAX_MODEL=mock-model\nECNU_MAX_API_KEY=not-a-real-secret\n"
        "ECNU_MAX_BASE_URL=https://example.invalid/v1\nUNRELATED=ignored\n",
        encoding="utf-8",
    )
    loaded = load_ecnu_env_file(env_file)
    assert set(loaded) == {"ECNU_MAX_MODEL", "ECNU_MAX_API_KEY", "ECNU_MAX_BASE_URL"}
    assert os.environ["ECNU_MAX_MODEL"] == "mock-model"
    assert "UNRELATED" not in loaded
