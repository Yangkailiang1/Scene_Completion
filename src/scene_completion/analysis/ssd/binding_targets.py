"""Handle role words in model replies without changing the advertised enum."""

from jsonschema import Draft202012Validator

from scene_completion.analysis.ssd.failure_context import auth_request
from scene_completion.domain.contracts import schema

ROLE_WORDS = {"human", "service"}


def validate_reply(task, value):
    contract = schema(task)
    props = contract["properties"]
    if task == "ssd-ground-align":
        target = props["parts"]["items"]["properties"]["fallback"]["anyOf"][0]["properties"]
    else:
        target = props["records"]["items"]["properties"]["bindings"]["items"]["properties"]
    target["target"]["enum"].extend(sorted(ROLE_WORDS))
    errors = sorted(
        Draft202012Validator(contract).iter_errors(value), key=lambda error: str(list(error.path))
    )
    if errors:
        raise ValueError("; ".join(f"{list(e.path)}: {e.message}" for e in errors[:12]))


def resolve(binding, steps, operation_units=()):
    """Return a verified direction or an unresolved binding with its original role."""
    role = binding["target"]
    if role not in ROLE_WORDS:
        return binding, None
    step = steps[binding["step_id"]]
    key = binding["key"]
    direction = None
    call = auth_request(step)
    participant = not any(binding.get(field) for field in ("entity_id", "attribute", "field_id"))
    if (
        participant
        and role == "human"
        and call == "human.authentication"
        and key.startswith("human.")
    ):
        direction = "sender"
    if participant and role == "service" and call:
        if call == "service_relation.authentication" and key.startswith("service_relation."):
            direction = "receiver"
        elif key == "service.base.availability" and step.get("receiver_external"):
            direction = "receiver"
        elif key == "database.special_characters" and step.get("receiver_technology") == "database":
            direction = "receiver"
        elif key.startswith("service.crud.") or key == "service.query_retrieval.resource_existence":
            related = [
                unit
                for unit in operation_units
                if not unit.get("functional_owner_id")
                and step["id"] in unit.get("related_steps", [])
                and unit.get("crud")
            ]
            selected = binding.get("operation_unit_id")
            if (selected and any(u["id"] == selected for u in related)) or (
                not selected and (len(related) == 1 or (not operation_units and step.get("crud")))
            ):
                direction = "receiver"
    note = {
        "original_target": role,
        "target": direction,
        "step_id": step["id"],
        "key": key,
        "reason": (
            f"按步骤 {step['id']} 的调用角色与关注点 {key} 将 {role} 纠正为 {direction}"
            if direction
            else f"目标 {role} 是参与者类型，步骤 {step['id']} 与关注点 {key} 未唯一确定挂载方向"
        ),
    }
    return ({**binding, "target": direction} if direction else None), note
