"""Identity and failure vocabulary for resource identifiers in a command path."""

import re

from scene_completion.domain.ssd import interface_fields

ROLES = {
    "target": "操作目标",
    "parent": "父对象",
    "ancestor": "祖先对象",
    "dependency": "依赖对象",
    "unknown": "引用对象",
}
KEYS = {
    "create": "service.crud.create.resource_existence",
    "read": "service.query_retrieval.resource_existence",
    "update": "service.crud.update.resource_existence",
    "delete": "service.crud.delete.resource_existence",
}
FAILURES = {
    "missing_resource": "不存在",
    "already_exists": "已存在",
    "disabled_reference": "已停用",
    "expired_reference": "已失效",
    "invalid_reference": "业务状态无效",
}
VALIDITY = "api.data.validity"


def path_parameters(path):
    pathname = re.split(r"[?#]", path or "", maxsplit=1)[0]
    return list(dict.fromkeys(re.findall(r"\{([^{}\s/]+)\}", pathname)))


def route_roles(path):
    """Use the route hierarchy when its path segments identify resources."""
    pathname = re.split(r"[?#]", path or "", maxsplit=1)[0].rstrip("/")
    names = path_parameters(pathname)
    if not names:
        return {}
    if pathname.endswith("/{" + names[-1] + "}"):
        roles = ["ancestor"] * max(0, len(names) - 2) + ["parent", "target"][-len(names) :]
    else:
        suffix = pathname.rsplit("{" + names[-1] + "}", 1)[-1]
        role = "parent" if re.fullmatch(r"/[\w-]+s", suffix) else "unknown"
        roles = ["ancestor"] * (len(names) - 1) + [role]
    if any(pathname.split("/").count("{" + name + "}") != 1 for name in names):
        return dict.fromkeys(names, "unknown")
    return dict(zip(names, roles, strict=True))


def identity(record):
    reference = record.get("resource_reference")
    return (
        (reference["command_id"], reference["parameter_name"], reference["role"])
        if reference
        else ()
    )


def is_existence(key):
    return key in KEYS.values()


def label(reference):
    return f"{ROLES[reference['role']]} {reference['parameter_name']}"


def failure(condition):
    """Recognize presence/state failures without treating a malformed ID as missing."""
    text = condition or ""
    if re.search(r"参数|字段|标识|ID", text, re.I) and re.search(
        r"格式|长度|缺失|未传|未提供|缺少|类型|不合法|为空", text
    ):
        return None
    if re.search(r"不存在|查无|找不到|未找到|未创建|已删除|not.found|does not exist", text, re.I):
        return "missing_resource"
    if re.search(r"停用|禁用|未启用|disabled", text, re.I):
        return "disabled_reference"
    if re.search(r"过期|失效|expired", text, re.I):
        return "expired_reference"
    if re.search(r"已存在|已经存在|重复创建|重名|already exists", text, re.I):
        return "already_exists"
    if re.search(r"状态无效|状态非法|状态不支持|状态不允许|状态不符", text):
        return "invalid_reference"
    return None


def atom_failures(atom):
    if atom.get("concern_key") != VALIDITY:
        return set()
    value = str(atom.get("value") or "")
    variants = set()
    if re.search(r"不得存在|不能存在|不可存在|不能已存在|必须不存在", value):
        variants.add("already_exists")
    elif re.search(r"存在|已删除|被删除", value):
        variants.add("missing_resource")
    if re.search(r"未停用|未禁用|必须启用|处于启用|未启用", value):
        variants.add("disabled_reference")
    if re.search(r"未失效|未过期|有效期", value):
        variants.add("expired_reference")
    if re.search(r"有效状态|状态有效|状态无效", value):
        variants.add("invalid_reference")
    if explicit := failure(atom.get("failure_condition")):
        variants.add(explicit)
    return variants


def mentions(name, text):
    return re.search(
        r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])",
        text or "",
        re.IGNORECASE,
    )


def different_failures(left, right):
    if not (is_existence(left["key"]) and is_existence(right["key"])):
        return False
    if not (left.get("resource_failure") or right.get("resource_failure")):
        return False
    a = left.get("resource_failure") or failure(left.get("condition"))
    b = right.get("resource_failure") or failure(right.get("condition"))
    return bool(a and b and a != b)


def source_scope(bundle, raw, actual):
    links = bundle.get("command_bindings", {})
    declared = interface_fields.command_id(raw)
    related = {cid for cid, link in links.items() if actual in interface_fields.related_steps(link)}
    if not related and actual:
        step = next((step for step in bundle["steps"] if step["id"] == actual), None)
        if step and any(
            actor.get("external") and actor["type"] == "service"
            for actor in (step["sender"], step["receiver"])
        ):
            return set()
    candidates = related or set(links)
    return candidates & {declared} if declared else candidates
