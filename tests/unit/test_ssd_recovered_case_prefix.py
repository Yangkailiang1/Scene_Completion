import json
from copy import deepcopy
from pathlib import Path
from shutil import copytree

from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
from scene_completion.inputs.structured.case_names import candidates
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.input_conversion.core_input import convert

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"


def test_numbered_title_fallback_preserves_exact_explicit_and_entity_precedence():
    rows = [
        {"id": "1", "name": "浏览商品", "entity": "Product"},
        {"id": "2", "name": "ＳＣ００１－ＵＣ００３：浏览商品", "entity": "Other"},
    ]

    def find(title, entity=None, explicit_id=None):
        return [
            row["id"]
            for _, row in candidates(
                rows, title, entity, explicit_id=explicit_id, allow_numbered_prefix=True
            )
        ]

    assert find("sc001-uc003:浏览商品", "Product") == ["2"]
    assert find("sc001-uc004:浏览商品", "Product") == ["1"]
    assert find("sc001-uc004:浏览商品") == ["1", "2"]
    assert find("任意名称", explicit_id="2") == ["2"]
    assert find("浏览商品", explicit_id="wrong") == []
    assert find("sc001-uc003浏览商品") == []


def test_recovered_extensions_attach_to_numbered_case_in_conversion_and_single_worker(tmp_path):
    raw = tmp_path / "raw"
    copytree(BROWSE, raw)
    path = next(raw.rglob("SysOperation.json"))
    content = json.loads(path.read_text(encoding="utf8"))
    content["use_case"] = "sc001-uc003 浏览商品"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf8")
    tests = raw / "recovered_usecases.json"
    recovered = json.loads(tests.read_text(encoding="utf8"))
    recovered[0]["id"] = "TEST-BROWSE-55"
    tests.write_text(json.dumps(recovered, ensure_ascii=False), encoding="utf8")

    [bundle] = build_cases(raw, case_files=path, profile=COMMAND_OPERATION_PROFILE)
    expected = {extension["id"] for extension in recovered[0]["extensions"]}
    assert bundle["case"]["name"] == content["use_case"]
    assert bundle["test_source_case_id"] == "TEST-BROWSE-55"
    assert bundle["gt_source_available"]
    assert {row["original_id"] for row in bundle["test_import_records"]} == expected

    core = tmp_path / "core"
    assert convert(raw, core, profile=COMMAND_OPERATION_PROFILE)["output"]
    [reopened] = build_cases(core)
    assert reopened["test_source_case_id"] == "TEST-BROWSE-55"
    assert {row["original_id"] for row in reopened["test_import_records"]} == expected

    peer = path.parent.with_name("另一个用例") / path.name
    peer.parent.mkdir()
    duplicate = deepcopy(content)
    duplicate.update(use_case_id="SECOND", use_case="【SC009-UC003】浏览商品")
    peer.write_text(json.dumps(duplicate, ensure_ascii=False), encoding="utf8")
    for selected, conflict in ((path, "SECOND"), (peer, content["use_case_id"])):
        [isolated] = build_cases(raw, case_files=selected, profile=COMMAND_OPERATION_PROFILE)
        [pending] = isolated["channels"]["GT"]["pending"]
        assert pending["candidates"] == ["TEST-BROWSE-55"]
        assert pending["conflicting_case_ids"] == [conflict]
        assert not isolated["gt_source_available"]
        assert isolated["test_source_path"] == "recovered_usecases.json"

    conflicted_core = tmp_path / "conflicted-core"
    assert convert(raw, conflicted_core, profile=COMMAND_OPERATION_PROFILE)["output"]
    raw_test = conflicted_core / "recovered_usecases.json"
    assert raw_test.is_file()
    for mapping_file in conflicted_core.glob("cases/*/extension-mapping.json"):
        mapping = json.loads(mapping_file.read_text(encoding="utf8"))
        if mapping["case_id"] == content["use_case_id"]:
            mapping["source_uc_id"] = "TEST-BROWSE-55"
            mapping_file.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf8")
    by_id = {row["case"]["id"]: row for row in build_cases(conflicted_core)}
    assert by_id[content["use_case_id"]]["test_source_case_id"] == "TEST-BROWSE-55"
    assert by_id["SECOND"]["channels"]["GT"]["pending"][0]["conflicting_case_ids"] == [
        content["use_case_id"]
    ]
