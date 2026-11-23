"""Identity and evidence for SR input fields."""

import re
import unicodedata

INPUT_FIELD_POLICY = "sr-input-by-name-v1"
LEGACY_PREFIXES = {"path", "query", "header", "body", "response", "cookie", "storage"}


def field_name(value):
    return unicodedata.normalize("NFKC", value or "").strip()


def legacy_name(value):
    name = field_name(value)
    prefix, dot, tail = name.partition(".")
    return tail if dot and prefix in LEGACY_PREFIXES else name


def command_id(record):
    return (
        (record.get("parameter") or {}).get("command_id")
        or record.get("command_id")
        or record.get("api_id")
        or (record.get("raw") or {}).get("api_id")
    )


def related_steps(link):
    return {
        link["primary_step_id"],
        *link.get("occurrences", []),
        *link.get("validation_step_ids", []),
        *link.get("response_step_ids", []),
    }


def commands_at(bindings, step_id, declared=None):
    related = {cid for cid, link in bindings.items() if step_id in related_steps(link)}
    if declared:
        return (
            {declared} if declared in bindings and (not related or declared in related) else set()
        )
    # Exact step evidence narrows the search. Without it, callers check the
    # case-wide candidate set for uniqueness.
    return related or set(bindings)


def candidates(bundle, step_id, record, *, include_conflicted=False):
    param = record.get("parameter") or {}
    name = field_name(param.get("name") or record.get("field_name"))
    commands = commands_at(bundle.get("command_bindings", {}), step_id, command_id(record))
    fields = [
        (step, field)
        for step in bundle["steps"]
        for field in step["data"]
        if field.get("command_id") in commands
        and (include_conflicted or not field.get("conflicts"))
    ]
    exact = [(step, field) for step, field in fields if field["name"] == name]
    return exact or [
        (step, field) for step, field in fields if legacy_name(field["name"]) == legacy_name(name)
    ]


def output_only(condition):
    """An explicitly faulty returned value, rather than an error sent for bad input."""
    text = unicodedata.normalize("NFKC", condition or "").strip()
    return bool(
        re.search(
            r"^(?:系统|服务|接口)?(?:实际)?(?:返回(?:的|值|字段|数据|结果)|响应(?:体|字段|数据|结构)|输出(?:字段|数据))",
            text,
        )
        and re.search(r"缺少|缺失|为空|错误|非法|不符|不正确|超出|超过|低于|未返回|格式|越界", text)
        and not re.search(
            r"(?:请求|输入|传入|提交)(?:的)?(?:数据|参数|字段|体|非法)|[；;\n]|则|导致", text
        )
    )
