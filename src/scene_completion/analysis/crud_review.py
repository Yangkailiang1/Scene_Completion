"""Review coverage and compact, positive-only context for business CRUD."""

from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.source_documents import documents_in, evidence_refs


def request_index(inputs):
    return [i for i in inputs["fused-ssd"]["interactions"] if i["direction"] == "request"]


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
    # RR/SR and adopted inputs can contribute the same source and line. Keep
    # the exact union so overlapping projections do not repeat the text.
    out["normal-documents"] = documents_in(out.get("normal-documents", []))
    fused = out["fused-ssd"]
    fused.pop("source_views", None)
    fused.pop("aliases", None)
    for interaction in fused["interactions"]:
        for side in ("sender", "receiver"):
            party = interaction[side]
            interaction[side] = {k: party[k] for k in ("name", "position") if k in party}
            if refs := evidence_refs(party):
                interaction[side]["source_refs"] = list({fingerprint(r): r for r in refs}.values())
        if data := interaction.get("data"):
            data["sequence"] = [
                {
                    **{k: field[k] for k in ("name", "location") if k in field},
                    "source_refs": list({fingerprint(r): r for r in evidence_refs(field)}.values()),
                }
                for field in data.get("sequence", [])
            ]
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
