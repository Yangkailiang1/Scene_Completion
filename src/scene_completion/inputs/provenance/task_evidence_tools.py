"""Read-only discovery over the evidence and structured records of one task."""

import re
from copy import deepcopy

from jsonpointer import JsonPointerException, resolve_pointer

from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.extraction.crud_evidence import MAX_LOOKUP_BYTES, location, size

DISCOVERY_TOOLS = frozenset({"search_evidence", "inspect_task_record"})


def enabled(config, task, inputs):
    if not config.get("agent_evidence_pilot"):
        return False
    if task == "business-crud":
        return "crud-entity-scope" in inputs
    return task == "api-map" and inputs.get("interface-scope", {}).get("boundary") in {
        "system",
        "external",
    }


def require_positive_documents(value):
    if isinstance(value, dict):
        if {"source_id", "channel", "lines"} <= value.keys():
            if value["channel"] != "normal":
                raise ValueError("evidence tools require positive task documents")
            return
        for item in value.values():
            require_positive_documents(item)
    elif isinstance(value, list):
        for item in value:
            require_positive_documents(item)


class TaskEvidenceTools:
    def __init__(self, context):
        self.references = dict(context.pool)
        inputs = context.input
        entities = inputs.get("business-entities", {}).get("entities", [])
        interactions = inputs.get("fused-ssd", {}).get("interactions", [])
        declarations = context.packet.get("interface_declarations", [])
        imports = {}
        for fragment in inputs.get("imported-fragments", []):
            if fragment["task"] == "api-map":
                for service in fragment["payload"].get("services", []):
                    for interface in service.get("interfaces", []):
                        record = {"service": service["name"], "interface": interface}
                        imports["imported-" + fingerprint(record)[:12]] = record
        self.records = {
            "entity": {item["id"]: item for item in entities},
            "interaction": {item["id"]: item for item in interactions},
            "interface_declaration": {
                "declaration-" + fingerprint(item)[:12]: item for item in declarations
            },
            "imported_interface": imports,
        }
        self.index = [
            {
                "kind": kind,
                "record_id": key,
                **{
                    field: item[field]
                    for field in ("receiver", "method", "path", "name", "source_refs")
                    if field in item
                },
                **(
                    {"service": item["service"], "interface_id": item["interface"]["id"]}
                    if kind == "imported_interface"
                    else {}
                ),
            }
            for kind in ("interface_declaration", "imported_interface")
            for key, item in self.records[kind].items()
        ]

    def search(self, query: str, source_id: str | None = None, after: str | None = None) -> dict:
        """Return exact match locations. The original text is read with lookup_evidence."""
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise ValueError("search query must contain 1..200 characters")
        if source_id is not None and not any(
            ref["source_id"] == source_id for ref in self.references.values()
        ):
            raise ValueError("source is outside this task")
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        def matches():
            for key, ref in self.references.items():
                if source_id is not None and ref["source_id"] != source_id:
                    continue
                match = pattern.search(ref["quote"])
                if match:
                    yield {
                        "evidence_id": key,
                        **location(ref),
                        "offset": match.start(),
                    }
            # This also makes declaration and import IDs discoverable by
            # normalized method, path, service or name.
            for item in self.index:
                record = self.records[item["kind"]][item["record_id"]]
                ids = self._references(record)
                if source_id is not None and not any(
                    self.references[key]["source_id"] == source_id
                    for key in ids
                    if key in self.references
                ):
                    continue
                if any(pattern.search(str(value)) for value in item.values()):
                    yield {"kind": item["kind"], "record_id": item["record_id"]}

        cursor = None
        results = []
        for item in matches():
            key = item.get("evidence_id") or item["record_id"]
            if after is not None:
                if key == after:
                    after = None
                continue
            candidate = {"matches": [*results, item], "next_after": key}
            if len(results) == 8 or size(candidate) > MAX_LOOKUP_BYTES:
                return {"matches": results, "next_after": cursor}
            results.append(item)
            cursor = key
        if after is not None:
            raise ValueError("search cursor is not valid for this query and scope")
        return {"matches": results, "next_after": None}

    @staticmethod
    def _references(value):
        if isinstance(value, dict):
            return set(value.get("source_refs", ())).union(
                *(TaskEvidenceTools._references(item) for item in value.values())
            )
        if isinstance(value, list):
            return set().union(*(TaskEvidenceTools._references(item) for item in value))
        return set()

    def inspect(self, kind: str, record_id: str, pointer: str = "") -> dict:
        """Resolve an RFC 6901 pointer within a known, task-local record."""
        if not isinstance(pointer, str) or len(pointer) > 512:
            raise ValueError("invalid JSON Pointer")
        try:
            record = self.records[kind][record_id]
            value = resolve_pointer(record, pointer)
        except (KeyError, JsonPointerException) as error:
            raise ValueError("record or pointer is outside this task") from error
        if not isinstance(value, (dict, list, str, int, float, bool, type(None))):
            raise ValueError("pointer must select an existing value")
        result = {"kind": kind, "record_id": record_id, "pointer": pointer, "value": value}
        if (not isinstance(value, list) or len(value) <= 8) and size(result) <= MAX_LOOKUP_BYTES:
            return deepcopy(result)
        fields = (
            list(value)[:8]
            if isinstance(value, dict)
            else list(range(min(len(value), 8)))
            if isinstance(value, list)
            else []
        )
        result = {
            "kind": kind,
            "record_id": record_id,
            "pointer": pointer,
            "status": "select_field",
        }
        if size({**result, "fields": fields}) <= MAX_LOOKUP_BYTES:
            result["fields"] = fields
        return result
