"""Deterministic SSD bindings, candidate discovery and match assignment."""

import re
import unicodedata

PAIRS = {"G_E": ("G", "E"), "GT_G": ("GT", "G"), "GT_E": ("GT", "E")}


def _records(bundle):
    for channel in ("G", "E", "GT"):
        for kind in ("concerns", "scenarios", "pending"):
            for row in bundle["channels"][channel].get(kind, []):
                yield channel, kind, row


def binding(row):
    return (
        row.get("step_id"),
        row.get("target"),
        row.get("field_id") or "",
        row.get("entity_id") or "",
        row.get("key"),
    )


def semantic_candidates(bundle):
    """Unreviewed wording differences within one concern anchor, without guesswork."""
    candidates = []
    for pair, (a, b) in PAIRS.items():
        decided = {
            (d["left_id"], d["right_id"])
            for d in bundle.get("decisions", [])
            if d.get("pair") == pair and d.get("level") == "scenario"
        }
        for left in bundle["channels"][a]["scenarios"]:
            for right in bundle["channels"][b]["scenarios"]:
                if (
                    left.get("status") == right.get("status") == "active"
                    and binding(left) == binding(right)
                    and (left["id"], right["id"]) not in decided
                    and (_text(left.get("condition")), _text(left.get("expected")))
                    != (_text(right.get("condition")), _text(right.get("expected")))
                ):
                    candidates.append(
                        {
                            "pair": pair,
                            "left_id": left["id"],
                            "right_id": right["id"],
                            "step_id": left.get("step_id"),
                        }
                    )
    return candidates


def _text(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text))).casefold()


def _units(bundle, kind):
    units, aliases = {}, {}
    for channel in ("G", "E", "GT"):
        grouped = {}
        aliases[channel] = {}
        for row in bundle["channels"][channel][kind]:
            if row["status"] != "active":
                continue
            identity = binding(row)
            if kind == "scenarios":
                identity += (_text(row.get("condition")), _text(row.get("expected")))
            representative = grouped.setdefault(identity, row)
            aliases[channel][row["id"]] = representative["id"]
        units[channel] = {r["id"]: r for r in grouped.values()}
    return units, aliases


def _edges(bundle, kind, units, aliases):
    edges = {}
    level = "concern" if kind == "concerns" else "scenario"
    for pair, (a, b) in PAIRS.items():
        matches = {}
        for x in units[a].values():
            for y in units[b].values():
                if binding(x) != binding(y):
                    continue
                exact = kind == "concerns" or (
                    _text(x.get("condition")) == _text(y.get("condition"))
                    and _text(x.get("expected")) == _text(y.get("expected"))
                )
                if exact:
                    matches[(x["id"], y["id"])] = "full"
        for d in sorted(bundle.get("decisions", []), key=lambda d: d.get("origin") == "manual"):
            if d["level"] != level or d["pair"] != pair:
                continue
            left, right = aliases[a].get(d["left_id"]), aliases[b].get(d["right_id"])
            if left and right:
                matches[(left, right)] = d["status"]
        edges[pair] = matches
    return edges


def _assignment(edges, left, right):
    """Maximum one-to-one assignment; one truth cannot count repeatedly."""
    assigned = {}

    def visit(x, seen):
        for y in sorted(y for (a, y), status in edges.items() if a == x and status == "full"):
            if y not in right or y in seen:
                continue
            seen.add(y)
            if y not in assigned or visit(assigned[y], seen):
                assigned[y] = x
                return True
        return False

    for x in sorted(left):
        visit(x, set())
    return {(x, y) for y, x in assigned.items()}
