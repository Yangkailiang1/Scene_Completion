"""Read-only links from an actual call to local checks within its return span.

These are navigation references, never additional matching/scoring bindings.
Ambiguous/crossing call spans are deliberately not used as a call tree.
"""


def references(rows):
    positions = {r["interaction"]["id"]: n for n, r in enumerate(rows)}
    spans = []
    for n, row in enumerate(rows):
        call = row["interaction"]
        if call.get("direction") != "request" or call.get("step_kind") == "action":
            continue
        returns = [
            positions[r["interaction"]["id"]]
            for r in rows
            if r["interaction"].get("direction") == "return"
            and r["interaction"].get("parent_id") == call["id"]
        ]
        if len(returns) == 1 and n < returns[0]:
            spans.append((n, returns[0]))
    out = {}
    for start, end in spans:
        if any(a < start < b < end or start < a < end < b for a, b in spans):
            continue
        links = []
        for row in rows[start + 1 : end]:
            check = row["interaction"]
            if check.get("step_kind") != "action":
                continue
            concerns = sorted(
                {
                    r["anchor"]["concern_key"]
                    for r in row.get("concern_rows", [])
                    if r["anchor"].get("target") in {"receiver", "operation"}
                }
            )
            if concerns:
                links.append(
                    {
                        "interaction_id": check["id"],
                        "operation": check["operation"]["name"],
                        "concern_keys": concerns,
                        "counted_here": False,
                    }
                )
        if links:
            out[rows[start]["interaction"]["id"]] = links
    return out
