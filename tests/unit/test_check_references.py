from copy import deepcopy

from scene_completion.analysis.scenarios.check_references import references


def row(iid, direction="request", kind="interaction", parent=None, keys=()):
    return {
        "interaction": {
            "id": iid,
            "direction": direction,
            "step_kind": kind,
            "parent_id": parent,
            "operation": {"name": iid},
        },
        "concern_rows": [{"anchor": {"target": "receiver", "concern_key": k}} for k in keys],
    }


def test_nested_calls_link_local_business_owner_without_copying_bindings():
    rows = [
        row("S1"),
        row("S3"),
        row("S4", kind="action", keys=["existence", "existence"]),
        row("S4b", "return", parent="S3"),
        row("S6", "return", parent="S1"),
    ]
    before = deepcopy(rows)
    links = references(rows)
    assert set(links) == {"S1", "S3"}
    assert links["S1"] == [
        {
            "interaction_id": "S4",
            "operation": "S4",
            "concern_keys": ["existence"],
            "counted_here": False,
        }
    ]
    assert rows == before


def test_ambiguous_crossing_or_missing_returns_do_not_infer_check_owners():
    rows = [
        row("S1"),
        row("S3"),
        row("check", kind="action", keys=["exists"]),
        row("return1", "return", parent="S1"),
        row("return2", "return", parent="S3"),
    ]
    assert not references(rows)
    assert not references(rows[:3])
