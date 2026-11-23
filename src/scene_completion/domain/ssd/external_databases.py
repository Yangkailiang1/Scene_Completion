"""Identify external database participants by role in the ordered main flow."""


def roles(step):
    """Prefer the receiver when the same database is on both sides of a local step."""
    result, seen = {}, set()
    for target in ("receiver", "sender"):
        party = step.get(target, {})
        if (
            party.get("type") == "service"
            and party.get("external")
            and party.get("technology") == "database"
            and party["id"] not in seen
        ):
            result[target] = party
            seen.add(party["id"])
    return result


def occurrences(steps):
    by_id = {}
    for step in sorted(steps, key=lambda step: step["order"]):
        for target, party in roles(step).items():
            by_id.setdefault(party["id"], []).append((step, target))
    return by_id


def availability_roles(step):
    result = roles(step)
    receiver = step.get("receiver", {})
    if (
        step.get("direction") == "request"
        and step.get("kind") != "action"
        and step.get("sender", {}).get("id") != receiver.get("id")
        and receiver.get("type") == "service"
        and receiver.get("external")
    ):
        result["receiver"] = receiver
    return result
