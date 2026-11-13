from scene_completion.application.execution import Execution
from scene_completion.infrastructure.storage import read_json
from tests.support.workflow import exchange


def test_resume_partitions_only_after_current_upstream_is_verified(tmp_path):
    seen = []

    def model(p):
        seen.append(p["input"]["fused-ssd"]["interactions"][0]["operation"]["name"])
        return {"rules": [], "pending": []}

    def run(name):
        i = exchange()
        i["operation"]["name"] = name
        ex = Execution(tmp_path, mocks={"normal-rules": model})
        ex.add(
            "source",
            "document-context",
            static={"interactions": [i], "rr_sr_links": []},
            transform=lambda d: d,
        )
        ex.partitioned(
            "case:normal",
            "normal-rules",
            ("source",),
            lambda d: {"normal-documents": [], "fused-ssd": d["source"]},
            "CASE-A",
        )
        assert ex.finish()["complete"]
        result = read_json(tmp_path / ex.scheduler.state["tasks"]["case:normal"]["output_file"])
        assert result["payload"] == {"rules": [], "pending": []}
        return ex

    run("old operation")
    seen.clear()
    run("new operation")
    assert seen == ["new operation"]
    seen.clear()
    run("new operation")
    assert not seen  # a verified unchanged cache still skips all model calls
