"""Regressions found by running the real five-case imported dataset."""

from scene_completion.analysis.validation import validate_result
from scene_completion.inputs.api_layers import scoped_imports


def test_same_path_different_method_contracts_cannot_be_merged():
    def api(ident, method):
        return {"id": ident, "address": "/products", "method": method, "source_layer": "RR"}

    part = {"payload": {"apis": [api("CREATE", "POST"), api("QUERY", "GET")]}, "source_layer": "RR"}
    scope = {**api("RR::QUERY", "GET"), "declared_id": "QUERY"}
    selected = scoped_imports([part], scope)
    assert len(selected) == 1
    assert selected[0]["payload"]["apis"] == [{**api("RR::QUERY", "GET"), "declared_id": "QUERY"}]


def test_aggregate_index_accepts_disjoint_slices_of_same_original_source():
    ref = {"source_id": "source", "line_start": 1, "line_end": 1, "quote": "POST /products"}
    api = {
        "id": "API-1",
        "name": "create",
        "address": "/products",
        "method": "POST",
        "source_refs": [ref],
    }
    inputs = {
        "RR": [
            {
                "source_id": "source",
                "channel": "normal",
                "name": "a",
                "lines": [{"number": 1, "text": "POST /products"}],
            }
        ],
        "SR": [
            {
                "source_id": "source",
                "channel": "normal",
                "name": "a",
                "lines": [{"number": 2, "text": "internal"}],
            }
        ],
        "api-map": {"services": [{"name": "Platform", "source_refs": [ref], "interfaces": [api]}]},
    }
    value = {
        "apis": [
            {
                "id": "API-1",
                "name": "create",
                "source_ranges": [{"source_id": "source", "start": 1, "end": 1}],
                "source_refs": [ref],
            }
        ]
    }
    validate_result("api-index", value, inputs)
