"""Response obligations for an external model service within a single use case."""

import re

KEY = "llm.response_parsing_failure"
GENERIC = "response_parse_failure"
JSON = "invalid_json"
REQUIRED = "missing_required_field"
MODEL = r"(?<![A-Za-z0-9_])LLM(?![A-Za-z0-9_])|大语言模型|大模型|模型服务|AI模型"
_OUTPUT = re.compile(r"返回|响应|输出|\b(?:response|output|returns?)\b", re.I)
_INPUT = re.compile(
    r"请求(?:体|参数|字段|格式|数据|中|侧)?|输入|传入|提交|\b(?:request|input)\b", re.I
)
_JSON = re.compile(r"(?<![A-Za-z0-9_])JSON(?![A-Za-z0-9_])", re.I)
_JSON_CONTRACT = re.compile(
    r"(?:返回|输出|响应(?:体|格式|内容)?|\breturns?\b|\boutput\b|\bresponse\b)\s*"
    r"(?:(?:为|是|采用|使用|一份|一个|结构化|标准|合法|有效|按|必须|应|以|严格|序列化为|[:：=]|"
    r"\b(?:as|in|is|a|valid)\b)\s*){0,6}[`“「\"]?"
    + _JSON.pattern
    + r"|JSON\s*(?:格式|对象|结构|文档|数组|of\s+shape|format|schema|object|array)",
    re.I,
)
_REQUIRED = re.compile(
    r"必填(?:的)?字段|字段.{0,20}(?:必填|必需)|必须(?:包含|提供|返回)|必须存在|"
    r"fields?\s+(?:is\s+|are\s+)?required|required\s+fields?",
    re.I,
)


def roles(step):
    target = {"request": "receiver", "return": "sender"}.get(step.get("direction"))
    if not target or step.get("kind") == "action":
        return {}
    party = step[target]
    if (
        step["sender"]["id"] != step["receiver"]["id"]
        and party["type"] == "service"
        and party.get("external")
        and party.get("technology") == "llm"
    ):
        return {target: party}
    return {}


def occurrences(steps):
    services = {}
    for step in sorted(steps, key=lambda row: row["order"]):
        for target, party in roles(step).items():
            services.setdefault(party["id"], []).append((step, target))
    return services


def anchor(rows):
    return next((row for row in rows if row[1] == "receiver"), rows[0])


def _clauses(text):
    return re.split(r"[，,。；;\n]+", text or "")


def contract(members):
    """Take format/required-field evidence from the positive response contract."""
    variants, refs = set(), []
    for step, target in members:
        origin_refs = [ref for ref in step.get("source_refs", []) if ref.get("kind") == "origin"]
        for text, source_refs in [
            (step["operation"]["name"], step.get("source_refs", [])),
            (step.get("description"), step.get("source_refs", [])),
            *((ref.get("quote"), [ref]) for ref in origin_refs),
        ]:
            output = target == "sender"
            for clause in _clauses(text):
                # When both directions appear in a clause, inspect the suffix
                # introduced by the last direction marker.
                marker = list(re.finditer(f"({_OUTPUT.pattern})|({_INPUT.pattern})", clause, re.I))
                if marker:
                    output = bool(marker[-1].group(1))
                    if output and any(m.group(2) for m in marker):
                        clause = clause[marker[-1].start() :]
                if not output or re.search(
                    r"无需|不要求|可选|失败|非法|错误|缺失|缺少|不符合|optional|invalid|missing",
                    clause,
                    re.I,
                ):
                    continue
                if _JSON_CONTRACT.search(clause) or (
                    target == "sender" and clause.strip().casefold() == "json"
                ):
                    variants.add(JSON)
                    refs.extend(source_refs)
                if _REQUIRED.search(clause):
                    variants.add(REQUIRED)
                    refs.extend(source_refs)
    return variants or {GENERIC}, refs


def failure_variant(condition):
    """Recognize structural failures without assuming what emitted the data."""
    if not condition or re.search(r"[；;\n]|或者?|\bor\b", condition, re.I):
        return None
    if _INPUT.search(condition) and (
        not (output := _OUTPUT.search(condition))
        or _INPUT.search(condition).start() < output.start()
    ):
        return None
    if re.search(
        r"幻觉|编造|事实错误|超时|不可用|网络错误|hallucination|timeout|unavailable",
        condition,
        re.I,
    ):
        return None
    if re.search(
        r"(?:(?:缺失|缺少|缺了?|未返回).{0,28}(?:字段|必填项)|"
        r"(?:字段|必填项).{0,28}(?:缺失|缺少|未返回|不完整)|"
        r"(?:返回|响应|输出).{0,8}(?:缺失|缺少).{0,12}[A-Za-z_][\w.-]*|"
        r"(?:missing|absent).{0,24}(?:field|property)|required.{0,36}(?:missing|absent))",
        condition,
        re.I,
    ):
        return REQUIRED
    parse = re.search(
        r"解析.{0,6}(?:失败|错误|异常|不通过)|无法解析|解析不了|(?:malformed|invalid)\s+JSON|"
        r"pars(?:ing|e).{0,15}(?:fail|error)|(?:fail|unable).{0,16}pars",
        condition,
        re.I,
    )
    if _JSON.search(condition) and (
        parse
        or re.search(
            r"非法|格式(?:错误|非法|不符|无效)|语法错误|不合法|invalid|malformed", condition, re.I
        )
    ):
        return JSON
    if parse or re.search(
        r"(?:响应|输出|返回).{0,2}(?:结构|格式)(?:错误|不符|不合法|不正确)", condition
    ):
        return GENERIC
    return None


def placements(bundle, condition, actual, *, context=()):
    """Return only service anchors supported by the source or explicit flow links."""
    services = occurrences(bundle["steps"])
    at = next((step for step in bundle["steps"] if step["id"] == actual), {})
    direct = {party["id"] for party in roles(at).values()}
    related = {at.get("parent_id"), at.get("delegated_from"), *at.get("validates", [])}
    scoped = direct or {
        service_id
        for service_id, rows in services.items()
        if any(step["id"] in related for step, _ in rows)
    }
    if at.get("kind") not in {None, "action"} and not scoped:
        return []

    def named_in(text):
        return {
            service_id
            for service_id, rows in services.items()
            if any(
                re.search(
                    r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])", text, re.I
                )
                for step, target in rows[:1]
                for name in {service_id, step[target]["name"]}
                if name
            )
        }

    named = named_in(condition)
    if not named and not scoped:
        named = named_in("\n".join(context))
    if scoped and not _OUTPUT.search(condition) and at.get("direction") == "request":
        selected = set()
    elif scoped and named:
        selected = scoped & named
    else:
        selected = scoped or named
    if (
        not scoped
        and not named
        and not actual
        and len(services) == 1
        and re.search(MODEL, condition, re.I)
    ):
        selected = services.keys()
    return [anchor(services[next(iter(selected))])] if len(selected) == 1 else []


def different_failures(left, right):
    if left.get("key") != KEY or right.get("key") != KEY:
        return False
    variants = [
        record.get("variant_id") or failure_variant(record.get("condition"))
        for record in (left, right)
    ]
    return all(variants) and variants[0] != variants[1]
