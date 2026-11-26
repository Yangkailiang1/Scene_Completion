"""Recognize narrow, explicit authentication failures and denial outcomes."""

import re
import unicodedata

from scene_completion.domain.ssd import concern_policy

_VARIANTS = {
    "missing_credential": r"缺失|缺少|未提供|未携带|未传入|未传",
    "empty_credential": r"为空|空值|空串|空白",
    "malformed_credential": r"格式(?:错误|非法|不合法|无效|不符)|非法|不合法",
    "invalid_token": r"无效|校验失败|校验不通过|签名(?:错误|无效)",
    "expired_token": r"已过期|过期|超期",
}
_HEADER = r"(?:请求头\s*)?Authorization"
_CREDENTIAL = rf"(?:{_HEADER}|Token|凭证)"
_DENIAL = (
    r"(?:返回|响应)?\s*(?:HTTP\s*)?401(?:\s+Unauthorized|\s*[,，]\s*AUTH_REQUIRED)?|"
    r"(?:身份)?认证(?:失败|不通过)|拒绝(?:请求|访问|调用)|"
    r"(?:按约定)?拒绝(?:该)?(?:未通过(?:身份)?认证|未认证)的?(?:请求|访问|调用)"
)


def _text(text):
    return unicodedata.normalize("NFKC", text).strip().rstrip("。.!！")


def _denial(text):
    return re.fullmatch(
        rf"(?:{_DENIAL})(?:\s*[,，：:]\s*(?:身份)?认证失败)?",
        text,
        re.I,
    )


def explicit_variants(condition, expected):
    text = _text(condition)
    text, *outcome = re.split(r"\s*(?:->|→|[,，])\s*", text, maxsplit=1)
    if outcome and not _denial(outcome[0]):
        return set()
    if (expected and not _denial(_text(expected))) or (not outcome and not expected):
        return set()
    if re.fullmatch(rf"(?:缺少|未提供|未携带|未传入)\s*{_CREDENTIAL}", text, re.I):
        return {"missing_credential"}
    if re.fullmatch("空凭证", text):
        return {"empty_credential"}
    head = re.match(rf"^(?P<credential>{_CREDENTIAL})\s*(?:[:=]\s*)?", text, re.I)
    if not head:
        return set()
    variants = set()
    for fragment in re.split(r"\s*(?:/|、|或)\s*", text[head.end() :]):
        variant = next(
            (key for key, expression in _VARIANTS.items() if re.fullmatch(expression, fragment)),
            None,
        )
        if not variant or (
            fragment in {"非法", "不合法"} and not re.fullmatch(_HEADER, head["credential"], re.I)
        ):
            return set()
        variants.add(variant)
    return variants


def generated_variants(candidate):
    variants = candidate.get("failure_variants")
    if variants:
        return set(variants) & concern_policy.AUTH_DETAILS.keys()
    variant = candidate.get("variant_id")
    return {variant} if variant in concern_policy.AUTH_DETAILS else set()


def equivalent_outcome(source, candidate):
    expected = _text(candidate["expected"])
    if not _denial(expected):
        return False
    # If G states its own status code, require the same explicit result.
    return not re.search(r"\b401\b", expected) or bool(re.search(r"\b401\b", source))
