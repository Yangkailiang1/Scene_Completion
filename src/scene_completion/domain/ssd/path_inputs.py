"""The vocabulary of path and field character validation."""

import re

from scene_completion.domain.ssd import concern_policy as policy

_CHARACTER = re.compile(r"特殊.{0,3}(?:字符|字符串)|非法字符|不允许的字符|字符集|字符白名单", re.I)
_PATH = re.compile(r"路径参数|路径中的参数|\bpath\s+(?:parameter|param)s?\b|\{[^{}\s/]+\}", re.I)


def failure_keys(condition):
    keys = set()
    if re.search(r"缺失|未(?:填|提供|传)|为空|空串|空值|\bempty\b|\bmissing\b", condition, re.I):
        keys.add(policy.COMPLETENESS)
    if (_CHARACTER.search(condition) or injection_risk(condition)) and not re.search(
        r"无特殊|不含(?:任何)?特殊|未含特殊|不包含(?:任何)?特殊", condition
    ):
        keys.add(policy.PATH_CHARACTERS)
    return keys


def injection_risk(condition):
    return bool(
        re.search(
            r"SQL\s*注入|HTML\s*(?:脚本|注入)|\bXSS\b|路径穿越|目录遍历|"
            r"SQL\s+injection|path\s+traversal",
            condition,
            re.I,
        )
    )


def declared_character_rule(text):
    return bool(re.search(r"正则|白名单|字符集|明确禁止", text))


def path_keys(condition):
    return failure_keys(condition) if _PATH.search(condition) else set()


def character_failure(condition):
    return bool(_CHARACTER.search(condition) or injection_risk(condition)) and not _PATH.search(
        condition
    )


def database_failure(condition):
    return (
        character_failure(condition)
        and bool(
            re.search(
                r"数据库.{0,18}(?:存储|入库|执行|查询|读取|转义|处理)|"
                r"SQL\s*(?:语句)?\s*(?:被(?:错误)?执行|执行(?:失败|异常|不正确))",
                condition,
                re.I,
            )
        )
        and not re.search(r"拒绝入参|入口校验|参数校验", condition)
    )
