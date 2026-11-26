"""Identity and positive evidence for CREATE's name inputs."""

from scene_completion.domain.ssd.interface_fields import legacy_name
from scene_completion.domain.ssd.path_resources import path_parameters
from scene_completion.infrastructure.identity import fingerprint


def names(field):
    return {
        legacy_name(field.get("wire_name")),
        legacy_name(field.get("name")),
        (field.get("entity_binding") or {}).get("attribute"),
    } - {"", None}


def location(field):
    for value in (field.get("name"), field.get("wire_name")):
        prefix, dot, _ = (value or "").partition(".")
        if dot and prefix in {"path", "body", "query", "header", "response", "storage"}:
            return prefix
    return field.get("declared_name_location") or field.get("location")


def name_field(field):
    return (
        "name" in names(field)
        and not field.get("conflicts")
        and location(field) not in {"response", "storage"}
        and field.get("direction") not in {"response", "return", "storage"}
    )


def entity_names(bundle, entity_ids):
    allowed = set(entity_ids)
    return {
        entity["id"]: attribute
        for entity in bundle.get("entities", [])
        if entity["id"] in allowed
        for attribute in entity.get("attributes", [])
        if attribute["name"] == "name"
    }


def path_name(field, command):
    """Only merge when the interface states that this input is in the path."""
    if location(field) == "path":
        declared = {legacy_name(field.get(key)) for key in ("name", "wire_name")}
        names_in_path = sorted(declared.intersection(path_parameters(command.get("path"))))
        if len(names_in_path) == 1:
            return names_in_path[0]
    return None


def operation_context(step):
    return fingerprint(
        [
            step.get("kind"),
            step.get("direction"),
            step.get("description"),
            (step.get("operation") or {}).get("name"),
            step.get("entity_ids", []),
            step.get("sender", {}).get("id"),
            step.get("receiver", {}).get("id"),
        ]
    )
