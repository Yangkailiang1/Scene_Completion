"""Conservative recognition of generic validation and JSON syntax evidence."""

import re
import unicodedata

from scene_completion.domain.ssd.interface_fields import INPUT_FIELD_POLICY

REQUEST_KEYS = frozenset(
    "api.data." + key for key in ("completeness", "format", "length", "range", "size", "type")
)


def summary_kind(condition):
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", condition or "")).casefold()
    text = re.sub(
        r"[,，;；]?(?:产生|触发|发生|返回|报出|抛出)(?:校验)?(?:异常|错误)[。.!！]?$", "", text
    )
    text = text.strip("。.!！")
    if re.fullmatch(
        r"(?:(?:请求体|请求报文|body)[:：]?)?(?:非法json(?:校验(?:格式)?(?:失败|不通过))?|"
        r"json(?:语法(?:错误|非法)|(?:解析|反序列化)(?:失败|错误|不通过)|报文格式(?:错误|非法)|格式(?:错误|非法))|"
        r"(?:无法|不能)解析json|不是(?:合法|有效)(?:的)?json)",
        text,
    ):
        return "json_syntax"
    if re.fullmatch(
        r"(?:请求)?(?:参数|字段|输入数据)(?:的)?格式(?:校验)?(?:失败|不通过|错误|非法|不合法|不正确)",
        text,
    ):
        return "field_format"
    if re.fullmatch(r"(?:请求)?(?:参数|字段|输入数据)(?:的)?(?:校验|验证)(?:失败|不通过)", text):
        return "request_validation"
    return None


def keys_for(summary):
    return REQUEST_KEYS if summary == "request_validation" else {"api.data.format"}


def applies(summary, scenario, field, fields, command, aliases, *, field_policy=None):
    named = field_policy == INPUT_FIELD_POLICY
    generated = summary_kind(scenario.get("condition"))
    if summary == "json_syntax":
        return (
            generated == "json_syntax"
            and (
                not field
                or (
                    (
                        named
                        or (
                            field.get("direction") == "request"
                            and field.get("location") in {"body", "request_body"}
                        )
                    )
                    and (field.get("wire_name") or field.get("name"))
                    in {"body", "$body", "requestBody", "请求体"}
                )
            )
            and scenario.get("target") in {"data", "receiver"}
        )
    if generated == "json_syntax" or scenario.get("key") not in keys_for(summary):
        return False
    if field:
        return named or field.get("direction") == "request"
    if not (scenario.get("entity_id") and scenario.get("attribute")):
        return False
    return any(
        f.get("command_id") == command
        and (named or f.get("direction") == "request")
        and (alias := aliases.get(f["id"], {}).get(scenario["key"]))
        and alias.get("entity_id") == scenario["entity_id"]
        and alias.get("attribute") == scenario["attribute"]
        for f in fields.values()
    )


def compatible(left, right):
    """Recognized JSON syntax failures cannot match a field validation failure."""
    return (summary_kind(left) == "json_syntax") == (summary_kind(right) == "json_syntax")
