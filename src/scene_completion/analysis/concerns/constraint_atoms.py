"""Deterministic constraint normalization for declared entity and field rules.

Every declared rule must yield at least one normalized item or an explicitly
unresolved record. Nothing is silently dropped: a rule the fast path cannot
classify stays visible for review instead of disappearing into ``other``.

Values are never invented. A rule that names a bound without a number keeps a
null value and records the missing fact, while the concern itself is still
produced so omission is not mistaken for an absent requirement.
"""

import re
from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint

VERSION = "constraint-atoms-v1"

# Stable concern identity for each normalized operation.
OPERATION_CONCERNS = {
    "required": "api.data.completeness",
    "type": "api.data.type",
    "format": "api.data.format",
    "length": "api.data.length",
    "size": "api.data.size",
    "range": "api.data.range",
    "enum": "api.data.range",
    "validity": "api.data.validity",
    "unique": "database.uniqueness",
    "state": "service.business_attribute_constraint",
    "business": "service.business_attribute_constraint",
}

NUMERIC = r"(-?\d+(?:\.\d+)?)"

# Field lists such as "cartItemId/productId/..." describe a payload shape, not
# a check on this field. They are kept as payload facts, never as constraints.
PAYLOAD_SHAPE = re.compile(r"^[A-Za-z_][\w\[\]]*(?:\s*/\s*[A-Za-z_][\w\[\]]*)+\s*$")

# State transitions: {A → B} or A → B. The arrow is not an enum separator.
TRANSITION = re.compile(r"^\{?\s*([A-Z][A-Z0-9_]*)\s*(?:→|->|=>)\s*([A-Z][A-Z0-9_]*)\s*\}?$")


def _compact(text):
    return re.sub(r"\s+", "", text).replace("≤", "<=").replace("≥", ">=")


def _number(text):
    return float(text) if "." in text else int(text)


def _item(concern_key, operation, value, status, refs, field, **extra):
    row = {
        "id": "atom-" + fingerprint([field, concern_key, operation, value, refs])[:20],
        "concern_key": concern_key,
        "operation": operation,
        "value": value,
        "status": status,
        "field": field,
        "source_refs": deepcopy(refs),
    }
    row.update({k: v for k, v in extra.items() if v is not None})
    return row


def _pending_value(concern_key, operation, field, refs, missing):
    """The concern exists; only its numeric standard is absent."""
    return _item(concern_key, operation, None, "explicit", refs, field, value_pending=missing)


def _split_clauses(text):
    """Split a compound rule into independently checkable clauses.

    A shared-subject bound such as "1 <= x <= 100" is one closed interval and is
    handled by the caller; ">= 1 \u4e14 <= 10" is two independent bounds.
    """
    parts = [
        p.strip()
        for p in re.split(r"[、，,；;]+|\u4e14|\u5e76\u4e14|and(?=\s*[<>=≤≥])", text)
        if p.strip()
    ]
    return parts or [text]


def _symbolic_bounds(clause, field):
    """A bound that names another attribute instead of a number.

    Both operand orders are accepted: "maxPrice >= minPrice" constrains
    maxPrice from below, while "<= refundable_amount" constrains the field from
    above. The named symbol is what makes this a cross-attribute relation.
    """
    compact = _compact(clause)
    # Attribute names are Latin identifiers in these inputs, but a bound may be
    # written against a Chinese attribute label; both forms are relations.
    symbol = r"([A-Za-z_][\w.]*|[\u4e00-\u9fff][\w.]*)"
    for pattern, operation in (
        (r"(?:" + re.escape(field) + r")?(?:>=|≥)" + symbol, "minimum"),
        (r"(?:>=|≥)" + symbol, "minimum"),
        (r"(?:" + re.escape(field) + r")?(?:<=|≤)" + symbol, "maximum"),
        (r"(?:<=|≤)" + symbol, "maximum"),
        (symbol + r"(?:>=|≥)" + re.escape(field), "maximum"),
        (symbol + r"(?:<=|≤)" + re.escape(field), "minimum"),
    ):
        match = re.fullmatch(pattern, compact)
        if match and not re.fullmatch(NUMERIC, match[1]):
            return match[1], operation
    return None, None


def _enum_values(text):
    return [v.strip() for v in re.split(r"[|,，、]", text) if v.strip()]


def _clause_items(clause, field, refs, state_tag):
    """Normalize one clause; return the produced items (possibly empty)."""
    text = clause.strip()
    compact = _compact(text)
    escaped = re.escape(field)

    transition = TRANSITION.fullmatch(text)
    if transition:
        return [
            _item(
                OPERATION_CONCERNS["state"],
                "state_precondition",
                {"from": transition[1], "to": transition[2]},
                "explicit",
                refs,
                field,
                reason="state transition described by the rule",
            )
        ]

    # "枚举 {A|B}" prefixes the same set with a Chinese label.
    enum = re.fullmatch(r"(?:枚举|取值|允许值)?\s*\{([^{}]+)\}", text)
    if enum:
        values = _enum_values(enum[1])
        if values and all(re.fullmatch(r"[A-Z][A-Z0-9_]*", v) for v in values):
            if state_tag:
                return [
                    _item(
                        OPERATION_CONCERNS["state"],
                        "state_enum",
                        values,
                        "explicit",
                        refs,
                        field,
                        reason="declared state set for a status-like field",
                    )
                ]
            return [_item(OPERATION_CONCERNS["enum"], "enum", values, "explicit", refs, field)]

    if re.fullmatch(r"=\s*([A-Z][A-Z0-9_]*)", text):
        return [
            _item(
                OPERATION_CONCERNS["state"],
                "state_equals",
                re.fullmatch(r"=\s*([A-Z][A-Z0-9_]*)", text)[1],
                "explicit",
                refs,
                field,
            )
        ]

    if re.fullmatch(r"(?:必填|非空|不能为空|不可为空)", text):
        return [_item(OPERATION_CONCERNS["required"], "required", True, "explicit", refs, field)]

    # A closed interval written as 1 <= x <= 100, 1 <= field <= 100, or against
    # a differently-cased spelling of the declared field name.
    subject = r"(?:" + escaped + r"|[A-Za-z_][\w]*)?"
    both = re.fullmatch(NUMERIC + r"(<=?)" + subject + r"(<=?)" + NUMERIC, compact)
    if both:
        return [
            _item(
                OPERATION_CONCERNS["range"],
                operation,
                _number(value),
                "explicit",
                refs,
                field,
                exclusive=True if operator == "<" else None,
            )
            for operation, value, operator in (
                ("minimum", both[1], both[2]),
                ("maximum", both[4], both[3]),
            )
        ]

    forward = re.fullmatch(subject + r"(>=?|<=?)" + NUMERIC, compact)
    reversed_bound = re.fullmatch(
        NUMERIC + r"(>=?|<=?)(?:" + escaped + r"|[A-Za-z_][\w]*)", compact
    )
    if forward or reversed_bound:
        if forward:
            operator, value = forward.groups()
            operation = "minimum" if operator.startswith(">") else "maximum"
        else:
            value, operator = reversed_bound.groups()
            operation = "minimum" if operator.startswith("<") else "maximum"
        return [
            _item(
                OPERATION_CONCERNS["range"],
                operation,
                _number(value),
                "explicit",
                refs,
                field,
                exclusive=True if len(operator) == 1 else None,
            )
        ]
    for match, operation in (
        (re.fullmatch(r"(?:≥|>=)\s*([A-Za-z_][\w.]*)", compact), "minimum"),
        (re.fullmatch(r"(?:≤|<=)\s*([A-Za-z_][\w.]*)", compact), "maximum"),
        (re.fullmatch(r"(?:" + escaped + r")?>=\s*([A-Za-z_][\w.]*)", compact), "minimum"),
        (re.fullmatch(r"(?:" + escaped + r")?<=\s*([A-Za-z_][\w.]*)", compact), "maximum"),
        (re.fullmatch(escaped + r">=\s*([A-Za-z_][\w.]*)", compact), "minimum"),
        (re.fullmatch(escaped + r"<=\s*([A-Za-z_][\w.]*)", compact), "maximum"),
    ):
        if match:
            # Symbolic bound (e.g. ">= minPrice"): a real relation, value elsewhere.
            return [
                _pending_value(
                    OPERATION_CONCERNS["range"],
                    operation,
                    field,
                    refs,
                    "边界引用符号" + match.group(1) + "，具体取值需结合该属性确定",
                )
            ]

    if re.search(r"格式|合法格式|URL|邮箱|email", text, re.I):
        items = [_item(OPERATION_CONCERNS["format"], "format", text, "explicit", refs, field)]
        if re.search(r"大小|字节|(?:MB|KB|bytes)", text, re.I):
            items.append(
                _item(
                    OPERATION_CONCERNS["size"],
                    "max_size",
                    None,
                    "explicit",
                    refs,
                    field,
                    value_pending="原文未给出大小上限数值",
                )
            )
        return items
    if re.search(r"长度|字符数|字符", text):
        span = re.search(r"(\d+)\s*(?:-|~|～|至|到)\s*(\d+)", text)
        if span:
            items = [
                _item(
                    OPERATION_CONCERNS["length"],
                    "max_length",
                    int(span[2]),
                    "explicit",
                    refs,
                    field,
                )
            ]
            if int(span[1]) > 0:
                items.append(
                    _item(
                        OPERATION_CONCERNS["length"],
                        "min_length",
                        int(span[1]),
                        "explicit",
                        refs,
                        field,
                    )
                )
            return items
        value = None
        pending = None
        bound = re.search(r"(?:<=|≤)\s*(\d+)", compact)
        if bound:
            value = int(bound[1])
        else:
            pending = "原文未给出长度上限数值"
        return [
            _item(
                OPERATION_CONCERNS["length"],
                "max_length",
                value,
                "explicit",
                refs,
                field,
                value_pending=pending,
            )
        ]
    if re.search(r"大小|字节|(?:MB|KB|bytes)", text, re.I):
        value = None
        pending = "原文未给出大小上限数值"
        bound = re.search(r"(?:<=|≤)\s*(\d+)", compact)
        if bound:
            value = int(bound[1])
            pending = None
        return [
            _item(
                OPERATION_CONCERNS["size"],
                "max_size",
                value,
                "explicit",
                refs,
                field,
                value_pending=pending,
            )
        ]
    # Uniqueness must be the rule's subject. "repeated requests do not change
    # the value" describes behaviour, not a uniqueness requirement on the field.
    if (
        re.fullmatch(r"(?:必须)?唯一(?:编号|标识)?", text)
        or re.match(r"^[A-Za-z_][\w]*\s*唯一$|^唯一|^不重复|^不得重复|^禁止重复", text)
        or re.search(r"不可重名|不能重名|不得重名", text)
    ):
        return [_item(OPERATION_CONCERNS["unique"], "unique", True, "explicit", refs, field)]
    # Referenced-resource validity needs an explicit reference to another
    # resource. A bare "valid" adjective ("valid requests do not increase the
    # version") neither names a resource nor establishes such a check.
    # A conditional rule that binds two attributes ("productType为SERVICE时price>=1")
    # states a relationship between them, not a plain range on one field.
    spoken = {"大于等于": ">=", "不小于": ">=", "至少": ">=", "大于": ">", "超过": ">"}
    operator = r"(>=|>|≤|<=|<|大于等于|不小于|至少|大于|超过|不等于)"
    relation = re.search(
        r"^([A-Za-z_][\w]*)\s*(?:为|=|是)\s*(\S+?)\s*(?:时|的情况下)\s*"
        r"([A-Za-z_][\w]*)\s*必须\s*" + operator + r"\s*(-?\d+(?:\.\d+)?)",
        text,
    )
    if relation:
        op = relation[4]
        return [
            _item(
                OPERATION_CONCERNS["business"],
                "conditional_range",
                {
                    "when": {"field": relation[1], "equals": relation[2]},
                    "then": {
                        "field": relation[3],
                        "operator": spoken.get(op, op),
                        "value": float(relation[5]),
                    },
                },
                "explicit",
                refs,
                field,
                counterpart=relation[1],
            )
        ]
    if re.search(r"存在|未停用|未失效|属于当前|归属|拥有|权限|未启用|已停用", text) or re.search(
        r"^(?:\S+)?有效(?:且|$)", text.strip()
    ):
        return [_item(OPERATION_CONCERNS["validity"], "validity", text, "explicit", refs, field)]
    # A quantity that must exceed a business limit is a range relation; the
    # limit itself is another attribute, so the bound stays symbolic.
    if re.search(r"不超过|不多于|不超过上限|限购|上限", text):
        return [
            _item(
                OPERATION_CONCERNS["range"],
                "maximum",
                None,
                "explicit",
                refs,
                field,
                value_pending="上限由其他属性或业务规则给出，具体取值需结合该规则确定",
            )
        ]
    # Non-negative and "must be positive" are stated without a comparator sign.
    if re.search(r"非负|不能为负|不得为负", text):
        return [_item(OPERATION_CONCERNS["range"], "minimum", 0, "explicit", refs, field)]
    if re.search(r"充足|足够|不足", text):
        return [
            _item(
                OPERATION_CONCERNS["range"],
                "minimum",
                None,
                "explicit",
                refs,
                field,
                value_pending="下限由本次请求所需数量决定，具体取值需结合该规则确定",
            )
        ]
    return []


def normalize_rules(
    rules,
    field,
    refs,
    *,
    tags=None,
    data_type=None,
    entity_only=False,
    rule_refs=None,
    tag_refs=None,
):
    """Normalize declared rules for one attribute into concerns.

    Returns ``{"items": [...], "payload": [...], "unresolved": [...]}``.
    ``payload`` holds field-shape facts that are not checks on this attribute.
    ``unresolved`` keeps anything the fast path could not classify.
    """
    tags = tags or []
    out = {"version": VERSION, "items": [], "payload": [], "unresolved": []}
    # A generic enum field is a value range, not a state machine. Only an
    # explicitly status-like field turns "{A}" / "{A -> B}" into a precondition.
    state_tag = bool(re.search(r"status|state", field, re.I) or any(t in tags for t in ("状态",)))
    if entity_only:
        if "必填" in tags or "PK" in tags:
            required_refs = [ref for tag in ("必填", "PK") for ref in (tag_refs or {}).get(tag, [])]
            out["items"].append(
                _item(
                    OPERATION_CONCERNS["required"],
                    "required",
                    True,
                    "explicit",
                    required_refs or refs,
                    field,
                )
            )
        if data_type:
            out["items"].append(
                _item(OPERATION_CONCERNS["type"], "type", data_type, "explicit", refs, field)
            )
    field_refs = refs
    for index, record in enumerate(rules or []):
        refs = field_refs if rule_refs is None else rule_refs[index]
        rule = record.get("rule") if isinstance(record, dict) else record
        if not isinstance(rule, str) or not rule.strip():
            continue
        text = rule.strip()
        original = record if isinstance(record, dict) else {"rule": text, "error": None}
        if rule_refs is not None and re.fullmatch(
            rf"(?:更新时)?(?:{re.escape(field)}|状态|该字段)?(?:不可修改|不允许修改|不得修改|不可变|只读)[。.]?",
            _compact(text).replace("`", ""),
        ):
            out["items"].append(
                _item(
                    OPERATION_CONCERNS["business"],
                    "immutable",
                    None,
                    "explicit",
                    refs,
                    field,
                    failure_condition="尝试修改禁止变更的值",
                    applicable_operations=["update"],
                )
            )
            continue
        if PAYLOAD_SHAPE.fullmatch(text):
            out["payload"].append({"text": text, "source_refs": deepcopy(refs), "error": None})
            continue
        # Necessity is sometimes stated in prose instead of the ``必填`` tag.
        # The trailing display fallback is kept with the rule but does not make
        # the field optional; the completeness concern is what gets mounted.
        necessity = re.search(r"必要字段|必需字段|必填项|必需项|不可缺失|必须提供|必须存在", text)
        handles_absence = re.search(r"缺失时|未指定|缺省展示|缺省处理|隐藏", text)
        if handles_absence and not necessity:
            out["payload"].append(
                {
                    "text": text,
                    "source_refs": deepcopy(refs),
                    "error": original.get("error"),
                    "reason": "缺失时的展示或过滤策略，不是字段约束",
                }
            )
            continue
        if necessity and handles_absence:
            out["items"].append(
                _item(
                    OPERATION_CONCERNS["required"],
                    "required",
                    True,
                    "explicit",
                    refs,
                    field,
                    note="必要性由规则文本声明：" + text,
                )
            )
            continue
        produced = []
        # A trailing parenthetical is a note about the rule, not a new subject.
        note = ""
        annotated = re.fullmatch(r"(.+?)[（(]([^（）()]+)[）)]\s*", text)
        if annotated:
            text, note = annotated[1].strip(), annotated[2].strip()
        # A closed interval "a <= x <= b" is one rule, not two clauses.
        if re.fullmatch(
            NUMERIC + r"\s*<=\s*(?:" + re.escape(field) + r")?\s*<=\s*" + NUMERIC, _compact(text)
        ):
            produced.extend(_clause_items(text, field, refs, state_tag))
        else:
            for clause in _split_clauses(text):
                produced.extend(_clause_items(clause, field, refs, state_tag))
        if not produced and note:
            # The annotation itself may carry a comparison against another attribute.
            symbol, operation = _symbolic_bounds(note, field)
            if not symbol and re.search(r"[<>=≤≥]" + re.escape(field), _compact(note)):
                produced.append(
                    _item(
                        OPERATION_CONCERNS["range"],
                        "maximum",
                        None,
                        "explicit",
                        refs,
                        field,
                        value_pending="上限由 " + note + " 约束，具体取值需结合该规则确定",
                    )
                )
        if not produced:
            symbol, operation = _symbolic_bounds(text, field)
            if symbol:
                produced.append(
                    _pending_value(
                        OPERATION_CONCERNS["range"],
                        operation,
                        field,
                        refs,
                        "边界引用符号" + symbol + "，具体取值需结合该属性确定",
                    )
                )
        if entity_only and any(item["operation"] == "unique" for item in produced):
            produced = [item for item in produced if item["operation"] != "unique"]
            out["unresolved"].append(
                {
                    "text": rule,
                    "field": field,
                    "error": original.get("error"),
                    "source_refs": deepcopy(refs),
                    "reason": "唯一性规则需确定业务作用域",
                }
            )
            if not produced:
                continue
        if not produced:
            out["unresolved"].append(
                {
                    "text": text,
                    "field": field,
                    "error": original.get("error"),
                    "source_refs": deepcopy(refs),
                    "reason": "未匹配到确定性约束模式，需语义规范化",
                }
            )
            continue
        out["items"].extend(produced)
    unique = {}
    for item in out["items"]:
        identity = fingerprint(
            [item["concern_key"], item["operation"], item["value"], item.get("exclusive")]
        )
        first = unique.setdefault(identity, item)
        if first is not item and rule_refs is not None:
            first["source_refs"] = list(
                {
                    fingerprint(ref): ref for ref in first["source_refs"] + item["source_refs"]
                }.values()
            )
    out["items"] = list(unique.values())
    return out


def validate_atoms(value, inputs):
    """Reject normalized output that invents values or splits a relation."""
    from scene_completion.domain.concern_registry import registry

    definitions = registry()["definitions"]
    allowed = inputs.get("attributes") or [value.get("field")]
    for item in value.get("items", []):
        key = item["concern_key"]
        if key not in definitions or not definitions[key].get("enabled", True):
            raise ValueError("未知或已停用的关注点：" + key)
        if not item.get("source_refs"):
            raise ValueError("约束项必须保留原文出处：" + key)
        if item.get("value_pending") and item.get("value") is not None:
            raise ValueError(
                "value_pending 与具体数值不能同时给出，不得编造标准：" + str(item.get("value"))
            )
        if item["operation"] in {"minimum", "maximum"} and item.get("value") is not None:
            if not isinstance(item["value"], (int, float)):
                raise ValueError("数值边界必须是数字：")
    for relation in value.get("relations", []):
        if relation["concern_key"] != "service.business_attribute_constraint":
            raise ValueError("跨字段关系必须使用业务实体属性约束")
        unknown = [f for f in relation.get("fields", []) if f not in allowed]
        if unknown:
            raise ValueError("跨字段关系引用了本实体之外的属性：" + ", ".join(unknown))
    return value
