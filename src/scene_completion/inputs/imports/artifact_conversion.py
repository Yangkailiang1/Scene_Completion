"""Evidence-preserving conversion and target schema validation."""

import json
import time
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.contracts import schema, validate
from scene_completion.infrastructure.paths import SKILLS_ROOT
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.documents.source_documents import normal_projection
from scene_completion.inputs.imports.artifact_recognition import ROOTS as ROOTS
from scene_completion.inputs.imports.artifact_recognition import TASKS as TASKS
from scene_completion.inputs.imports.artifact_recognition import deterministic as deterministic
from scene_completion.inputs.imports.artifact_recognition import role_hint as role_hint
from scene_completion.inputs.imports.artifact_store import LOCK, archive, case_catalogue, load, save
from scene_completion.inputs.imports.artifact_views import view


def cited_payload(payload, task, file_id, name):
    """Cite an inspectable normalized JSONL view, never invent RR/SR references."""
    lines = []
    sid = "import-" + file_id + "-" + fingerprint(payload)[:12]

    def visit(value):
        if isinstance(value, list):
            return [visit(x) for x in value]
        if not isinstance(value, dict):
            return deepcopy(value)
        clean = {k: visit(v) for k, v in value.items() if k != "source_refs"}
        quote = json.dumps(
            {k: v for k, v in clean.items() if k != "source_refs"},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if "source_refs" in value:
            lines.append({"number": len(lines) + 1, "text": quote})
            clean["source_refs"] = [
                {"source_id": sid, "line_start": len(lines), "line_end": len(lines), "quote": quote}
            ]
        return clean

    # Fill required citation containers only, leaving all factual unknowns intact.
    def fill(value, spec):
        if isinstance(value, dict):
            if "source_refs" in spec.get("properties", {}):
                value.setdefault("source_refs", [])
            for k, v in value.items():
                fill(v, spec.get("properties", {}).get(k, {}))
        elif isinstance(value, list):
            for v in value:
                fill(v, spec.get("items", {}))

    value = deepcopy(payload)
    fill(value, schema(task))
    value = visit(value)
    return value, {
        "source_id": sid,
        "name": name + " · 规范化事实（原文件可查看）",
        "channel": "normal",
        "lines": lines,
    }


def _targets(row, artifacts, prepared=False):
    for n, a in enumerate(artifacts):
        if not isinstance(a, dict) or a.get("task") not in TASKS:
            raise ValueError("导入目标不在支持的正向任务范围")
        if prepared:
            value, doc = deepcopy(a["payload"]), deepcopy(a["document"])
            from scene_completion.inputs.documents.source_documents import validate_evidence

            if (
                doc["source_id"] != "import-" + row["id"] + "-facts-v1"
                or doc["channel"] != "normal"
            ):
                raise ValueError("结构转换的来源身份无效")
            validate_evidence(value, [doc])
        else:
            value, doc = cited_payload(
                a.get("payload"), a["task"], row["id"] + "-" + str(n), row["name"]
            )
        try:
            validate(a["task"], value)
            error = None
        except ValueError as e:
            error = str(e)
        row["artifacts"].append(
            {
                "id": row["id"] + ":" + str(n),
                "task": a["task"],
                "case_hint": a.get("case_hint"),
                "coverage": a.get("coverage", "partial"),
                "payload": value,
                "document": doc,
                "status": "needs_confirmation"
                if a.get("coverage") != "complete" or error
                else "candidate",
                "error": error,
                "accepted_partial": False,
                "source_layer": a.get("source_layer"),
                "conversion_source_refs": a.get("source_refs", []),
            }
        )
        if prepared:
            row["artifacts"][-1].update(
                json_locations=a.get("json_locations", []),
                coverage_details=a.get("coverage_details", {}),
                literal_adapter=a.get("literal_adapter"),
            )


def convert(project, iid, client):
    from scene_completion.domain.contracts import packet
    from scene_completion.infrastructure.execution_events import EventStore, bind, emit

    project = Path(project)
    row = view(project, iid)
    if row["status"] not in {"needs_conversion", "conversion_failed"}:
        return row
    path = project / row["original"]
    text = path.read_text(encoding="utf-8-sig")
    doc = {
        "source_id": "import-raw-" + iid,
        "name": row["name"],
        "channel": "normal",
        "lines": [{"number": n, "text": s} for n, s in enumerate(text.splitlines(), 1)],
    }
    # Conversion never consumes the project's G/E/GT or private files. Prose
    # sections labelled tests/exceptions are excluded from positive candidates.
    docs = normal_projection([doc])
    chunks = []
    chunk = []
    size = 0
    for line in docs[0]["lines"]:
        cost = len(line["text"].encode())
        if cost > 32000:
            raise ValueError("单行过大，请先拆分为可定位段落")
        if size + cost > 32000 and chunk:
            chunks.append(chunk)
            chunk = []
            size = 0
        chunk.append(line)
        size += cost
    if chunk:
        chunks.append(chunk)
    artifacts = []
    roles = set()
    catalogue = case_catalogue(project)
    try:
        for n, lines in enumerate(chunks):
            p = packet(
                "artifact-convert",
                {
                    "documents": [{**doc, "lines": lines}],
                    "file_name": row["name"],
                    "case-catalogue": catalogue,
                    "target_schemas": json.dumps({t: schema(t) for t in TASKS}, ensure_ascii=False),
                },
            )
            p["node_key"] = "imports:" + iid
            p["skill_text"] = (SKILLS_ROOT / "scene-artifact-import/SKILL.md").read_text()
            with bind(
                EventStore(project / "run"),
                task_key=p["node_key"],
                role="modeler",
                case="shared",
                attempt=n + 1,
            ):
                emit(
                    "import_conversion_started", file_id=iid, chunk=n + 1, total_chunks=len(chunks)
                )
                value = client.agent(p)
                roles.add(value["source_role"])
                if value["source_role"] == "artifact":
                    for a in value["artifacts"]:
                        if len(chunks) > 1:
                            a["coverage"] = "partial"
                        artifacts.append(a)
        with LOCK:
            index = load(project)
            current = read_json(project / index["items"][iid]["record"])
            if current["revision"] != row["revision"]:
                raise ValueError("文件转换期间版本已变化")
            if roles != {"artifact"}:
                current["role"] = next(iter(roles)) if len(roles) == 1 else "unknown"
                artifacts = []
            archive(project, current)
            current["artifacts"] = []
            _targets(current, artifacts)
            current.update(
                status="converted"
                if artifacts
                else "source_pending"
                if current["role"] in {"RR", "SR", "test"}
                else "unclassified",
                revision=row["revision"] + 1,
            )
            current["history"].append(
                {"action": "converted", "at": time.time(), "chunks": len(chunks)}
            )
            write_json(project / index["items"][iid]["record"], current)
            index["items"][iid].update(status=current["status"], role=current["role"])
            save(project, index)
            return current
    except Exception as e:
        with LOCK:
            index = load(project)
            current = read_json(project / index["items"][iid]["record"])
            current.update(
                status="conversion_failed", error=str(e), revision=current["revision"] + 1
            )
            write_json(project / index["items"][iid]["record"], current)
            index["items"][iid]["status"] = current["status"]
            save(project, index)
        raise
