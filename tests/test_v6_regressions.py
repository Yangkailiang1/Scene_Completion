import copy
import tempfile
from pathlib import Path

from tests.test_scene_completion import sample_model
from tools.scene_completion.concerns import plan_concern_matrix, validate_concern_matrix
from tools.scene_completion.schemas import validate_scene_model
from tools.scene_completion.ssd import generate_ssd_bundle, validate_ssd
from tools.scene_completion.ssd import write_ssd_bundle
from tools.scene_completion.png_renderer import convert_svg_to_png, find_svg_converter


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
