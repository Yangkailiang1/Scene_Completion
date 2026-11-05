"""Review coverage and compact, positive-only context for business CRUD."""

from copy import deepcopy


def request_index(inputs):
    return [
        i
        for i in inputs["fused-ssd"]["interactions"]
        if i["direction"] == "request"
        and i.get("step_kind") != "action"
        and i["sender"]["name"] != i["receiver"]["name"]
    ]


def validate_reviews(value, inputs):
    expected = {i["id"] for i in request_index(inputs)}
    reviews = value.get("reviews", [])
    seen = [r["interaction_id"] for r in reviews]
    if len(seen) != len(set(seen)) or set(seen) != expected:
        raise ValueError(
            "CRUD must explicitly review every actual receiving service entry: missing="
            + str(sorted(expected - set(seen)))
            + "; extra="
            + str(sorted(set(seen) - expected))
            + ". Submit reviews with decision crud/not_crud/pending and evidence; "
            "a database-only matrix does not establish that upstream entries were reviewed."
        )
    row_ids = {r["interaction_id"] for r in value["rows"]}
    for review in reviews:
        iid = review["interaction_id"]
        if (review["decision"] == "crud") != (iid in row_ids):
            raise ValueError("CRUD review/rows disagree at " + iid)


def context(inputs):
    """Keep business effects and references, omit duplicate raw SSD views.

    Field-level constraints are irrelevant to classifying a business effect;
    the complete positive source documents remain available to the model.
    This view never infers or inserts a CRUD result.
    """
    out = deepcopy(inputs)
    fused = out["fused-ssd"]
    fused.pop("source_views", None)
    fused.pop("aliases", None)
    for interaction in fused["interactions"]:
        for side in ("sender", "receiver"):
            interaction[side] = {
                k: v for k, v in interaction[side].items() if k in {"name", "position"}
            }
    out["business-entities"] = {
        "entities": [
            {k: v for k, v in entity.items() if k in {"id", "name", "source_refs"}}
            for entity in out["business-entities"]["entities"]
        ]
    }
    out["required_entry_reviews"] = [
        {
            "interaction_id": i["id"],
            "sender": i["sender"]["name"],
            "receiver": i["receiver"]["name"],
        }
        for i in request_index(out)
    ]
    return out
