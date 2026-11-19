"""Check model containers before expanding references or saving questions."""


def payload_from_arguments(arguments, schema):
    """Put recognized business fields back inside the submission envelope."""
    promoted = arguments.keys() - {"payload", "review_questions"}
    allowed = schema.get("properties", {})
    if unknown := promoted - allowed.keys():
        raise ValueError(
            ", ".join(f"arguments.{k}: 不是当前任务的业务字段" for k in sorted(unknown))
        )
    if "payload" not in arguments and not promoted:
        raise ValueError("arguments.payload: 缺少业务结果")
    payload = arguments.get("payload", {})
    if not promoted:
        return payload
    if not isinstance(payload, dict):
        raise ValueError("arguments.payload: 存在提升字段时必须是 JSON 对象")
    if overlap := promoted & payload.keys():
        raise ValueError(", ".join(f"arguments.{k}: 与 payload.{k} 重复" for k in sorted(overlap)))
    return {**payload, **{k: arguments[k] for k in sorted(promoted)}}


def containers(value, schema, path="payload"):
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    if value is None and "null" in kinds:
        return
    if len(kinds) > 1:
        predicates = {
            "object": lambda x: isinstance(x, dict),
            "array": lambda x: isinstance(x, list),
            "string": lambda x: isinstance(x, str),
            "boolean": lambda x: isinstance(x, bool),
            "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
            "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        }
        actual = next((k for k in kinds if k in predicates and predicates[k](value)), None)
        if actual is None:
            raise ValueError(f"{path} must satisfy one of {kinds}")
        return containers(value, {**schema, "type": actual}, path)
    if "object" in kinds:
        if not isinstance(value, dict):
            raise ValueError(
                f"{path} must be a JSON object, not {type(value).__name__}; do not stringify records"
            )
        for key, spec in schema.get("properties", {}).items():
            if key in value:
                containers(value[key], spec, f"{path}.{key}")
    elif "array" in kinds:
        if not isinstance(value, list):
            raise ValueError(f"{path} must be a JSON array, not {type(value).__name__}")
        for n, row in enumerate(value):
            containers(row, schema.get("items", {}), f"{path}[{n}]")
    elif "string" in kinds and not isinstance(value, str):
        raise ValueError(
            f"{path} must be text"
            + (" or null" if "null" in kinds else "")
            + f", not {type(value).__name__}"
        )


def questions(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError("review_questions must be an array of at most 30 JSON objects")
    from scene_completion.review.decisions.review_questions import TYPES

    for n, row in enumerate(value):
        path = f"review_questions[{n}]"
        if not isinstance(row, dict):
            raise ValueError(
                path
                + " must be a JSON object with question, required_answer and source_refs; a plain string is not a question record"
            )
        if row.get("question_type", "general_clarification") not in TYPES:
            raise ValueError(path + ".question_type is not supported")
        for key, alias in [("question", "text"), ("required_answer", "decision")]:
            text = row.get(key) or row.get(alias)
            if not isinstance(text, str) or not text.strip():
                raise ValueError(path + "." + key + " must be nonempty text")
        refs = row.get("source_refs", [])
        if not isinstance(refs, list) or any(not isinstance(r, (str, dict)) for r in refs):
            raise ValueError(
                path + ".source_refs must be an array of supplied evidence IDs or source objects"
            )
    return value
