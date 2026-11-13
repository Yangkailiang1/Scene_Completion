"""Offline test support extracted without changing builder behavior."""


def model(layer="RR"):
    entities = [
        {"entity_id": "actor", "entity_type": "actor", "canonical_name": "开发者"},
        {"entity_id": "sys", "entity_type": "system", "canonical_name": "平台"},
    ]
    relations = []
    for n in (1, 2):
        cid = f"{layer}-UC-{n}"
        entities.append(
            {
                "entity_id": cid,
                "entity_type": "use_case",
                "canonical_name": "用例" + str(n),
                "use_case_id": "UC-" + str(n),
                "actors": ["actor"] if layer == "RR" else [],
            }
        )
        for kind in ("main_success", "exception", "alternative"):
            sid = f"{layer}-scene-{n}-{kind}"
            entities.append(
                {
                    "entity_id": sid,
                    "entity_type": "scenario",
                    "scenario_kind": kind,
                    "steps": [f"{kind} {n} 开发者向平台查询"],
                    "expected_result": kind + " result",
                    "evidence": [
                        {
                            "source_id": "ABSENT-SPEC",
                            "quote": "DO_NOT_LEAK_EVIDENCE_ANSWER",
                            "locator": "L999-L1000",
                        }
                    ],
                }
            )
            relations.append(
                {
                    "source_entity_id": sid,
                    "target_entity_id": cid,
                    "relation_type": "associated_with_usecase",
                }
            )
    return {
        "schema_version": "3",
        "scope": {"model_level": layer},
        "entities": entities,
        "relations": relations,
        "source_inputs": [{"source_id": "BASE", "secret": "DO_NOT_LEAK_BASELINE"}],
        "review_items": [{"question": "DO_NOT_LEAK_BASELINE_REVIEW"}],
    }


__all__ = ["model"]
