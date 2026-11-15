import pytest

from scene_completion.domain.scenario_conditions import disjoint, validate_decisions


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("query.pageSize=0", "pageSize=101", True),
        ("pageSize < 1", "pageSize > 100", True),
        ("pageSize=0", "pageSize < 1", False),
        ("pageSize=1", "pageSize <= 1", False),
        ("pageSize=1", "pageSize < 1", True),
        ("pageSize=0 或 pageSize=101", "pageSize=0", False),
        ("分页参数非法", "pageSize=0", False),
        ("page=0", "pageSize=101", False),
    ],
)
def test_only_proven_disjoint_numeric_conditions_are_rejected(left, right, expected):
    assert disjoint(left, right) is expected


def test_partial_cannot_cover_opposite_boundary_but_manual_results_stay_editable():
    inputs = {
        "pairs": [
            {
                "left": {"id": "GT", "condition": "pageSize=0"},
                "right": {"id": "G", "condition": "pageSize=101"},
            }
        ]
    }
    value = {"decisions": [{"left_id": "GT", "right_id": "G", "status": "partial"}]}
    with pytest.raises(ValueError, match="互斥"):
        validate_decisions(value, inputs)
    value["decisions"][0]["status"] = "none"
    validate_decisions(value, inputs)
