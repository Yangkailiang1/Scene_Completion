"""Handle role words in model replies without changing the advertised enum."""

from jsonschema import Draft202012Validator

from scene_completion.domain.contracts import schema
from scene_completion.domain.ssd import actor_security, llm_responses
from scene_completion.workflow.ssd.resolve.operations import functional_owner
from scene_completion.workflow.ssd.shared.failure_context import request_actor

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
        messages = []
        for error in errors[:12]:
            path = list(error.path)
            if (
                task == "ssd-ground-align"
                and error.validator == "required"
                and isinstance(error.instance, dict)
            ):
                identity = error.instance.get("candidate_id") or error.instance.get("part_id")
                if (
                    identity
                    and "reason" not in error.instance
                    and error.message.startswith("'reason'")
                ):
                    path.append("reason")
                    messages.append(f"{path}: {identity} 缺少对齐依据")
                    continue
            messages.append(f"{path}: {error.message}")
        raise ValueError("; ".join(messages))


def resolve(binding, steps, operation_units=()):
    """Return a verified direction or an unresolved binding with its original role."""
    role = binding["target"]
    if role not in ROLE_WORDS:
        return binding, None
    step = steps[binding["step_id"]]
    key = binding["key"]
    direction = None
    caller = request_actor(step)
    participant = not any(binding.get(field) for field in ("entity_id", "attribute", "field_id"))
    databases = step.get("external_database_roles", {})
    models = step.get("external_llm_roles", {})
    if participant and role == "service" and key == llm_responses.KEY and len(models) == 1:
        direction = next(iter(models))
    if (
        participant
        and role == "service"
        and key
        in {
            "service.base.availability",
            "database.special_characters",
        }
        and len(databases) == 1
    ):
        direction = next(iter(databases))
    if participant and role == "human" and caller == "human" and key.startswith("human."):
        direction = "sender"
    if participant and role == "service" and caller and not direction:
        if (
            caller == "service"
            and key.startswith("service_relation.")
            and key not in actor_security.SERVICE_KEYS
        ):
            direction = "receiver"
        elif key == "service.base.availability" and step.get("receiver_external"):
            direction = "receiver"
        elif key == "database.special_characters" and step.get("receiver_technology") == "database":
            direction = "receiver"
        elif key.startswith("service.crud.") or key == "service.query_retrieval.resource_existence":
            related = [
                unit
                for unit in operation_units
                if functional_owner(unit)
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
