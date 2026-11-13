"""Existing-file input entry point: receive, inspect, convert and adopt."""

import base64
import json
import re
import time
from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.documents.source_documents import normal_projection
from scene_completion.inputs.imports.artifact_adoption import candidate as candidate
from scene_completion.inputs.imports.artifact_adoption import decide as decide
from scene_completion.inputs.imports.artifact_adoption import documents as documents
from scene_completion.inputs.imports.artifact_adoption import fragments_for as fragments_for
from scene_completion.inputs.imports.artifact_adoption import identity as identity
from scene_completion.inputs.imports.artifact_adoption import merge as merge
from scene_completion.inputs.imports.artifact_adoption import record_use as record_use
from scene_completion.inputs.imports.artifact_adoption import selections as selections
from scene_completion.inputs.imports.artifact_conversion import _targets as _targets
from scene_completion.inputs.imports.artifact_conversion import cited_payload as cited_payload
from scene_completion.inputs.imports.artifact_conversion import convert as convert
from scene_completion.inputs.imports.artifact_recognition import ROOTS as ROOTS
from scene_completion.inputs.imports.artifact_recognition import TASKS as TASKS
from scene_completion.inputs.imports.artifact_recognition import deterministic as deterministic
from scene_completion.inputs.imports.artifact_recognition import role_hint as role_hint
from scene_completion.inputs.imports.artifact_store import LOCK
from scene_completion.inputs.imports.artifact_store import archive as archive
from scene_completion.inputs.imports.artifact_store import case_catalogue as case_catalogue
from scene_completion.inputs.imports.artifact_store import load as load
from scene_completion.inputs.imports.artifact_store import resolve_case as resolve_case
from scene_completion.inputs.imports.artifact_store import save as save
from scene_completion.inputs.imports.artifact_store import snapshot as snapshot
from scene_completion.inputs.imports.artifact_views import provenance_label as provenance_label
from scene_completion.inputs.imports.artifact_views import purpose as purpose
from scene_completion.inputs.imports.artifact_views import view as view


def receive(project, files):
    project = Path(project)
    out = []
    from scene_completion.inputs.structured.behavior_imports import context_for
    from scene_completion.inputs.structured.behavior_imports import format_of as behavior_format

    batch = []
    for f in files:
        try:
            raw = (
                base64.b64decode(f["content_base64"], validate=True)
                if f.get("content_base64")
                else str(f.get("content", "")).encode("utf8")
            )
            if len(raw) > 20 * 1024 * 1024:
                continue
            value = json.loads(raw.decode("utf-8-sig"))
            if behavior_format(value):
                batch.append({"path": f.get("relative_path") or f.get("name", ""), "value": value})
        except (ValueError, UnicodeError):
            pass
    with LOCK:
        index = load(project)
        for f in files:
            name = Path(str(f.get("name", "")).replace("\\", "/")).name
            if (
                not name
                or name.startswith(".")
                or any(
                    x in name.lower()
                    for x in (
                        ".local.",
                        "api-key",
                        "api_key",
                        "credential",
                        "token-budget",
                        "ledger",
                    )
                )
                or Path(name).suffix.lower() not in {".md", ".markdown", ".json", ".xlsx"}
            ):
                continue
            raw = (
                base64.b64decode(f["content_base64"], validate=True)
                if f.get("content_base64")
                else str(f.get("content", "")).encode("utf8")
            )
            if len(raw) > 20 * 1024 * 1024:
                raise ValueError("导入文件超过20MB，请按章节拆分")
            from scene_completion.inputs.structured.behavior_imports import (
                compile_product as compile_behavior,
            )
            from scene_completion.inputs.structured.behavior_imports import (
                format_of as behavior_format,
            )

            try:
                behavior_kind = (
                    behavior_format(json.loads(raw.decode("utf-8-sig")))
                    if Path(name).suffix.lower() == ".json"
                    else None
                )
            except (ValueError, UnicodeError):
                behavior_kind = None
            behavior_context = (
                f.get("behavior_context") or context_for(f.get("relative_path") or name, batch)
                if behavior_kind
                else {}
            )
            digest = (
                fingerprint([raw.hex(), behavior_context])
                if behavior_kind
                else fingerprint(raw.hex())
            )
            iid = digest[:24]
            if iid in index["items"]:
                if behavior_kind:
                    from scene_completion.inputs.structured.behavior_imports import (
                        VERSION as behavior_version,
                    )

                    old = read_json(project / index["items"][iid]["record"])
                    if old.get("behavior_product", {}).get("version") != behavior_version:
                        try:
                            converted = compile_behavior(
                                json.loads(raw.decode("utf-8-sig")), iid, name, behavior_context
                            )
                        except ValueError:
                            converted = None
                        if converted:
                            archive(project, old)
                            old.update(
                                behavior_product=converted,
                                behavior_enabled=False,
                                status="converted",
                                revision=old["revision"] + 1,
                            )
                            old.pop("behavior_error", None)
                            old["history"].append(
                                {
                                    "action": "behavior_adapter_upgrade",
                                    "version": behavior_version,
                                    "at": time.time(),
                                }
                            )
                            write_json(project / index["items"][iid]["record"], old)
                            index["items"][iid].update(status=old["status"], purpose=purpose(old))
                            out.append({"id": iid, "duplicate": True, "adapter_updated": True})
                            continue
                out.append({"id": iid, "duplicate": True})
                continue
            folder = project / "imports/files" / iid
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "original").mkdir(exist_ok=True)
            (folder / "original" / name).write_bytes(raw)
            text = raw.decode("utf-8-sig") if Path(name).suffix.lower() != ".xlsx" else ""
            role = f.get("role") or role_hint(name, text)
            from scene_completion.inputs.structured.structure_models import compile_model

            structured = compile_model(text, name) if Path(name).suffix.lower() == ".json" else None
            if structured or behavior_kind:
                role = "artifact"
            meta = (
                read_json(project / "project.json")
                if (project / "project.json").exists()
                else {"sources": {}}
            )
            bound = [
                r
                for r, files in meta["sources"].items()
                for source in files
                if (project / source["path"]).is_file()
                and (project / source["path"]).read_bytes() == raw
            ]
            if len(set(bound)) == 1:
                role = bound[0]
            if role not in {"RR", "SR", "test", "artifact", "unknown"}:
                raise ValueError("未知文件用途")
            positive = normal_projection(
                [
                    {
                        "source_id": "raw",
                        "name": name,
                        "lines": [
                            {"number": i, "text": v} for i, v in enumerate(text.splitlines(), 1)
                        ],
                    }
                ]
            )[0]
            parse_text = (
                "\n".join(v["text"] for v in positive["lines"])
                if Path(name).suffix.lower() in {".md", ".markdown"}
                else text
            )
            from scene_completion.inputs.structured.colleague_formats import (
                convert as convert_colleague,
            )

            product = (
                convert_colleague(json.loads(text), iid, name)
                if Path(name).suffix.lower() == ".json"
                and role == "artifact"
                and not structured
                and not behavior_kind
                else None
            )
            behavior = behavior_error = None
            if behavior_kind:
                try:
                    behavior = compile_behavior(json.loads(text), iid, name, behavior_context)
                except ValueError as e:
                    behavior_error = str(e)
            artifacts = (
                product["artifacts"]
                if product
                else deterministic(parse_text, name)
                if role == "artifact" and not behavior_kind
                else []
            )
            row = {
                "id": iid,
                "name": name,
                "hash": digest,
                "role": role,
                "status": "converted"
                if artifacts
                else "needs_conversion"
                if role == "artifact"
                else "source_pending",
                "artifacts": [],
                "created_at": time.time(),
                "revision": 0,
                "original": str((folder / "original" / name).relative_to(project)),
                "history": [],
            }
            if structured:
                row.update(structure_model=structured, structure_enabled=True, status="converted")
            if product:
                row.update(
                    colleague_product={k: v for k, v in product.items() if k != "artifacts"},
                    status="converted",
                )
            if behavior:
                row.update(
                    behavior_product=behavior,
                    behavior_enabled=False,
                    status="converted",
                    relative_path=f.get("relative_path"),
                )
            if behavior_error:
                row.update(
                    behavior_error=behavior_error,
                    status="invalid_behavior",
                    relative_path=f.get("relative_path"),
                )
            row["recognition"] = {
                "role": role,
                "reason": "正文含明确测试场景/恢复结构"
                if role == "test" and re.search(r"SC@|测试逆向", text)
                else "格式结构与文件用途识别",
                "source_file": name,
                "source_hash": digest,
            }
            if role == "test":
                from scene_completion.inputs.provenance.test_sources import preview

                documents = [
                    {
                        "source_id": "import-raw-" + iid,
                        "name": name,
                        "channel": "test",
                        "lines": [
                            {"number": i, "text": line}
                            for i, line in enumerate(text.splitlines(), 1)
                        ],
                    }
                ]
                if Path(name).suffix.lower() == ".xlsx":
                    from scene_completion.inputs.provenance.test_sources import xlsx_documents

                    documents = xlsx_documents(raw, name, iid)
                row["test_preview"] = preview(documents)
                row["target_nodes"] = [
                    "test-inventory",
                    "test-case-align",
                    "<用例>:test-concerns",
                    "<用例>:test-ground-truth",
                    "<用例>:concern-evaluation",
                    "<用例>:exception-evaluation",
                ]
            else:
                row["target_nodes"] = [a["task"] for a in row["artifacts"]]
            if bound:
                row["status"] = "source_active"
            _targets(row, artifacts, prepared=bool(product))
            row["target_nodes"] = (
                (
                    [
                        "rr-use-cases" if structured["layer"] == "RR" else "sr-use-cases",
                        "<用例>:existing-branches",
                    ]
                    if structured
                    else [a["task"] for a in row["artifacts"]]
                )
                if role == "artifact"
                else row.get("target_nodes", [])
            )
            row["target_nodes"] = list(dict.fromkeys(row["target_nodes"]))
            if product and product["format"] == "function_tree":
                row["target_nodes"] += [
                    "<用例>:business-crud（提供实体范围）",
                    "business-attribute-map（提供属性依据）",
                    "<用例>:interaction-enrich（精确字段补充）",
                ]
            if behavior:
                row["target_nodes"] = behavior["target_nodes"]
            from scene_completion.inputs.imports.artifact_parsers import mermaid_sequences

            row["literal_structure"] = {"mermaid": mermaid_sequences(parse_text)}
            # A mixed artifact file requires conversion of remaining structures too.
            if (
                role == "artifact"
                and not structured
                and not product
                and (
                    row["literal_structure"]["mermaid"]
                    or artifacts
                    and re.search(r"请求参数|数据类型|参数名称|支持的操作|系统组成", parse_text)
                )
            ):
                row["status"] = "needs_conversion"
            record = str((folder / "record.json").relative_to(project))
            write_json(project / record, row)
            index["items"][iid] = {
                "name": name,
                "role": role,
                "purpose": purpose(row),
                "status": row["status"],
                "record": record,
                "created_at": row["created_at"],
            }
            out.append({"id": iid, "duplicate": False})
        save(project, index)
    return {"received": out, "revision": index["revision"]}
