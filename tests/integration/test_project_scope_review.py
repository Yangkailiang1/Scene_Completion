import json
from copy import deepcopy

from scene_completion.application import project_scope_review as review
from scene_completion.application import project_scope_service as service
from scene_completion.review.offline.ssd_review import _PayloadParser
from tests.integration.test_project_scope_workflow import bundles


def test_project_offline_feedback_roundtrip_conflict_and_context_protection(tmp_path):
    service.publish(tmp_path, bundles()["business_chain"])
    html = review.export_legacy_review(tmp_path, {"scope": "business_chain"})
    parser = _PayloadParser()
    parser.feed(html)
    payload = json.loads("".join(parser.parts))
    assert payload["cases"][0]["rows"]
    assert payload["cases"][0]["bundle"]["documents"]
    assert review.preview_feedback(tmp_path, html)["status"] == "unchanged"
    row = payload["cases"][0]["bundle"]["channels"]["G"]["scenarios"][0]
    row["analysis"] = "业务人工修改"
    feedback = json.dumps(payload)
    assert review.preview_feedback(tmp_path, feedback)["status"] == "ready"
    applied = review.apply_feedback(tmp_path, feedback, "business_chain")
    assert applied["status"] == "applied"
    assert review.apply_feedback(tmp_path, feedback, "business_chain")["status"] == "unchanged"
    changed = deepcopy(payload)
    changed["cases"][0]["bundle"]["channels"]["G"]["scenarios"][0]["analysis"] += "另一份修改"
    assert review.preview_feedback(tmp_path, changed)["status"] == "conflict"
    changed = deepcopy(payload)
    changed["cases"][0]["bundle"]["anchors"] = []
    assert review.preview_feedback(tmp_path, changed)["status"] == "conflict"
    changed = deepcopy(payload)
    changed["cases"][0]["baseline"]["documents"] = []
    assert review.preview_feedback(tmp_path, changed)["status"] == "conflict"
