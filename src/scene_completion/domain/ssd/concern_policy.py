"""Scenario granularity and enabled concern keys for current structured SSD."""

import re

from scene_completion.domain.ssd import actor_security

LEGACY_VERSION = "ssd-input-and-consolidated-scenarios-v1"
VERSION = "ssd-input-and-consolidated-scenarios-v2"
NAME_CHARACTERS_VERSION = "ssd-create-name-characters-v1"
AUTH = actor_security.AUTHENTICATION
DATABASE = "database.special_characters"
FIELD = "service.business_attribute_constraint"
COMPLETENESS = "api.data.completeness"
PATH_CHARACTERS = "api.data.path_special_characters"

AUTH_DETAILS = {
    "missing_credential": "未提供凭证",
    "empty_credential": "凭证为空",
    "malformed_credential": "凭证格式错误",
    "invalid_token": "凭证校验失败",
    "expired_token": "凭证过期",
}
DB_DETAILS = {
    "sql_injection": "SQL 内容被错误处理",
    "html_injection": "HTML 内容被错误处理",
    "wide_characters": "宽字符处理异常",
    "emoji_characters": "emoji 处理异常",
}
ACTIVE_CHECKS = {
    AUTH,
    "human.authorization",
    "service.base.availability",
    FIELD,
    PATH_CHARACTERS,
    "llm.response_parsing_failure",
    "service.query_retrieval.resource_existence",
    *(
        "api.data." + kind
        for kind in ("completeness", "type", "format", "length", "size", "range", "validity")
    ),
    *(
        f"service.crud.{operation}.{kind}"
        for operation in ("create", "update", "delete")
        for kind in ("concurrency_consistency", "idempotency", "resource_existence")
    ),
}


def applies(bundle):
    return bundle.get("scenario_policy") in {LEGACY_VERSION, VERSION}


def path_inputs(bundle):
    return bundle.get("scenario_policy") == VERSION


def name_characters(bundle):
    return bundle.get("name_character_policy") == NAME_CHARACTERS_VERSION


def enabled(key, *, path_policy=True):
    if key == DATABASE:
        return not path_policy
    if key == PATH_CHARACTERS:
        return path_policy
    return key == "service.base.request_data" or key in ACTIVE_CHECKS


def fixed_only(key):
    return key in {AUTH, DATABASE, PATH_CHARACTERS} or key.endswith(".concurrency_consistency")


def details(key):
    return AUTH_DETAILS if key == AUTH else DB_DETAILS if key == DATABASE else {}


def subtype(key, text):
    if key == AUTH:
        patterns = {
            "missing_credential": r"(?:未(?:提供|携带|传入)|缺(?:少|失)|无)(?:请求头\s*)?(?:Authorization|Token|凭证)|(?:Authorization|Token|凭证).{0,8}(?:缺失|缺少|未提供|未携带)",
            "empty_credential": r"空凭证|(?:Authorization|Token|凭证).{0,8}(?:为空|空串|空白)",
            "malformed_credential": r"(?:Authorization|Token|凭证).{0,16}(?:格式错误|格式不符|格式非法|格式无效)|格式.{0,8}(?:错误|无效|非法).{0,5}凭证",
            "expired_token": r"(?:Authorization|Token|凭证).{0,12}(?:过期|超期)",
            "invalid_token": r"(?:Authorization|Token|凭证).{0,14}(?:无效|校验不通过|校验失败|签名错误|签名无效)|无效(?:的)?(?:Token|凭证)",
        }
    elif key == DATABASE:
        patterns = {
            "sql_injection": r"(?<![A-Za-z])SQL(?![A-Za-z])",
            "html_injection": r"(?<![A-Za-z])HTML(?![A-Za-z])",
            "wide_characters": r"宽字符|全角字符|多字节字符",
            "emoji_characters": r"emoji|表情字符|表情符号",
        }
    else:
        return None
    hits = [kind for kind, pattern in patterns.items() if re.search(pattern, text or "", re.I)]
    if "malformed_credential" in hits and "invalid_token" in hits:
        hits.remove("invalid_token")
    return hits[0] if len(hits) == 1 else None


def different_subtypes(left, right):
    a, b = left.get("failure_subtype"), right.get("failure_subtype")
    return bool(a and b and left["key"] == right["key"] and a != b)


def optional_auth(bundle, step):
    cid = step["operation"].get("command_id")
    return any(
        row["id"] == cid and row.get("authentication") == "optional"
        for row in bundle.get("commands", [])
    )


def removed_concurrency(condition):
    return bool(
        re.search(r"并发删除", condition)
        and re.search(r"关联(?:业务)?资源|关联对象|依赖资源", condition)
        and not re.search(r"结果冲突|一致性冲突|更新被覆盖|重复写入", condition)
    )
