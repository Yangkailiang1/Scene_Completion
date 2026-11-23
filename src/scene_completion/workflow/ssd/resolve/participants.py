"""Classify main-flow participants by their own cited declarations."""

from scene_completion.domain.ssd.construction import ident

TASK = "ssd-participant-classify"


def classify(bundle, semantic):
    if semantic is None:
        return
    parties = {}
    for step in bundle["steps"]:
        for party in (step["sender"], step["receiver"]):
            parties.setdefault(party["id"], []).append(party)
    declarations = []
    for pid, occurrences in parties.items():
        party = occurrences[0]
        if party.get("kind_override"):
            continue
        refs = {
            ident("Q", pid, ref): ref["quote"]
            for ref in party.get("source_refs", [])
            if isinstance(ref, dict) and isinstance(ref.get("quote"), str) and ref["quote"].strip()
        }
        if refs:
            declarations.append(
                {
                    "id": pid,
                    "name": party["name"],
                    "kind": party.get("declared_kind"),
                    "role": party.get("role"),
                    "element_type": party.get("element_type"),
                    "source_refs": [{"id": key, "quote": quote} for key, quote in refs.items()],
                }
            )

    case = {key: bundle["case"][key] for key in ("id", "name")}
    decisions = []
    for offset in range(0, len(declarations), 8):
        inputs = {"case": case, "participants": declarations[offset : offset + 8]}
        decisions.extend(semantic(TASK, inputs)["participants"])
    if decisions:
        bundle["participant_classifications"] = decisions
    for row in decisions:
        kind = row["kind"]
        if kind is None:
            continue
        for party in parties[row["participant_id"]]:
            party.update(
                type="human" if kind == "external_actor" else "service",
                external=kind != "internal_service",
                classification_source=TASK,
            )
            if kind == "external_actor":
                party["technology"] = None


def validate_result(payload, inputs):
    refs = {row["id"]: {ref["id"] for ref in row["source_refs"]} for row in inputs["participants"]}
    rows = payload["participants"]
    if {row["participant_id"] for row in rows} != refs.keys() or len(rows) != len(refs):
        raise ValueError("必须对本批每个参与者恰好返回一条判定")
    for row in rows:
        cites = set(row["source_ref_ids"])
        if not cites <= refs[row["participant_id"]] or len(cites) != len(row["source_ref_ids"]):
            raise ValueError("参与者判定只能引用该参与者自己的原文编号且不得重复")
        if (row["kind"] is not None and not cites) or not row["reason"].strip():
            raise ValueError("明确的参与者类型必须引用原文，每条判定都须说明依据或缺口")
    return payload
