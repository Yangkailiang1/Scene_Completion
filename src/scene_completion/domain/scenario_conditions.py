"""Conservative proof of incompatible single numeric failure predicates."""

import re
from decimal import Decimal

_PREDICATE = re.compile(r"([A-Za-z_][\w.]*)\s*(<=|>=|==|=|<|>)\s*(-?\d+(?:\.\d+)?)")


def _interval(text):
    text = str(text or "")
    if re.search(r"或|并非|不是|不满足|\bor\b|\bnot\b|\|", text, re.I):
        return None
    found = _PREDICATE.findall(text)
    if len(found) != 1:
        return None
    field, op, number = found[0]
    n = Decimal(number)
    low, high = Decimal("-Infinity"), Decimal("Infinity")
    low_closed = high_closed = False
    if op in {"=", "=="}:
        low = high = n
        low_closed = high_closed = True
    elif op in {">", ">="}:
        low, low_closed = n, op == ">="
    else:
        high, high_closed = n, op == "<="
    return field.rsplit(".", 1)[-1], low, high, low_closed, high_closed


def disjoint(left, right):
    a, b = _interval(left), _interval(right)
    if not a or not b or a[0] != b[0]:
        return False
    if a[2] < b[1] or b[2] < a[1]:
        return True
    return (a[2] == b[1] and not (a[4] and b[3])) or (b[2] == a[1] and not (b[4] and a[3]))


def validate_decisions(value, inputs):
    pairs = {(p["left"]["id"], p["right"]["id"]): p for p in inputs["pairs"]}
    for decision in value["decisions"]:
        pair = pairs.get((decision["left_id"], decision["right_id"]))
        if (
            pair
            and decision["status"] in {"full", "partial"}
            and disjoint(pair["left"].get("condition"), pair["right"].get("condition"))
        ):
            raise ValueError(
                "两个明确数值失败条件互斥，应为none；相同字段、关注点或错误码不构成覆盖"
            )
