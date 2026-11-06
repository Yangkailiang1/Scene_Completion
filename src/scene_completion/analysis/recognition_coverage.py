"""Check recognition coverage without adding observations to G.

The checklist is derived from explicit contracts. Only a model's submitted
field/category observations can satisfy it; registry membership is insufficient.
"""

from scene_completion.analysis.concern_matching import complete_data_matches


def field_reviews(inputs):
    from scene_completion.analysis.concern_alignment import interaction_rows

    rows = interaction_rows(inputs)
    material = {
        **inputs,
        "rr-ssd": {"interactions": [i for i in rows if i["layer"] == "RR"]},
        "sr-ssd": {"interactions": [i for i in rows if i["layer"] == "SR"]},
    }
    if "normal-constraints" in material and "api-parameters" not in material:
        material["api-parameters"] = material["normal-constraints"]
    unique = {}
    definitions = inputs.get("registry", {}).get("definitions")
    for row in complete_data_matches(material, []):
        if definitions is not None and (
            row["concern_key"] not in definitions
            or not definitions[row["concern_key"]].get("enabled", True)
        ):
            continue
        key = (row["interaction_id"], row["data_location"], row["object"], row["concern_key"])
        unique[key] = {
            "interaction_id": row["interaction_id"],
            "location": row["data_location"],
            "field": row["object"],
            "concern_key": row["concern_key"],
            "known_rule": row["concrete_rule"],
        }
    return list(unique.values())


def validate_coverage(value, inputs):
    if inputs.get("recognition_scope") == "data" and any(
        not m["concern_key"].startswith("api.data.") for m in value.get("matches", [])
    ):
        raise ValueError(
            "this scoped recognition task only identifies data fields; service and business observations belong to their own partition"
        )
    from scene_completion.analysis.normal_rules import rule_matches

    rules = rule_matches(
        {
            **inputs,
            "normal-rules": {
                "rules": [
                    r
                    for r in inputs.get("normal-rules", {}).get("rules", [])
                    if r["concern_key"]
                    in {
                        "human.authentication",
                        "human.authorization",
                        "service_relation.authentication",
                        "service_relation.authorization",
                    }
                ]
            },
        }
    )
    for m in value.get("matches", []):
        if m["concern_key"].startswith("human."):
            from scene_completion.analysis.concern_alignment import interaction_rows

            call = next(
                (i for i in interaction_rows(inputs) if i["id"] == m["interaction_id"]), None
            )
            if (
                call
                and call["direction"] == "request"
                and call.get("step_kind") != "action"
                and call["sender"]["name"] != call["receiver"]["name"]
                and "人类" in call["sender"]["position"]
            ):
                # The user explicitly requires both checks for every human
                # call. Do not spend model repair budget asking it to invent
                # a credential mechanism; G's policy resolver supplies basis.
                continue
        if m["concern_key"] in {
            "human.authentication",
            "human.authorization",
            "service_relation.authentication",
            "service_relation.authorization",
        } and m.get("concrete_rule"):
            guard = m["concern_key"].rsplit(".", 1)[1]
            if not any(
                g.get("kind") == guard and g.get("source_refs")
                for g in m.get("activation_evidence", [])
            ) and not any(
                r["interaction_id"] == m["interaction_id"] and r["concern_key"] == m["concern_key"]
                for r in rules
            ):
                raise ValueError(
                    "identified authentication/authorization needs explicit activation_evidence with its own rule and source_refs; concrete_rule alone is not a guard: "
                    + m["interaction_id"]
                    + " "
                    + m["concern_key"]
                )

    def key(row):
        name = row["object"]
        location = row.get("data_location")
        prefix, sep, rest = name.partition(".")
        if sep and prefix in {"header", "path", "query", "body", "response", "business"}:
            location, name = prefix, rest
        return (
            row["interaction_id"],
            location,
            name.casefold() if location == "header" else name,
            row["concern_key"],
        )

    observed = [key(m) for m in value.get("matches", []) if m.get("target") == "data"]
    missing = []
    for row in field_reviews(inputs):
        expected = (
            row["interaction_id"],
            row["location"],
            row["field"].casefold() if row["location"] == "header" else row["field"],
            row["concern_key"],
        )
        if expected not in observed:
            # Missing location is accepted only when the actual field is unique.
            if not any(
                o[0] == expected[0] and o[1] is None and o[2:] == expected[2:] for o in observed
            ):
                missing.append(row)
    if missing:
        import json

        raise ValueError(
            "recognition omitted explicit field constraints; identify each actual data field, "
            "not a parent entity such as Product. Known constraints cannot be silently "
            "downgraded to unknown. Missing reviews: " + json.dumps(missing, ensure_ascii=False)
        )
