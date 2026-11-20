"""Index and select pinned original documents."""

import json
import re

from scene_completion.domain.ssd.construction import (
    ident,
)
from scene_completion.infrastructure.storage import io_path

ORIGIN_SUFFIXES = (".md", ".markdown", ".xlsx")


def origin_documents(root):
    """Original requirement/design documents shipped beside structured inputs."""
    from scene_completion.inputs.provenance import source_origins

    root = io_path(root).resolve()
    manifest = root / "source-documents.json"
    declared = {}
    registered = manifest.is_file()
    if registered:
        for row in json.loads(manifest.read_text(encoding="utf-8-sig"))["documents"]:
            path = (root / row["path"]).resolve()
            role = row["role"]
            if (
                not path.is_relative_to(root)
                or path.suffix.lower() not in ORIGIN_SUFFIXES
                or role not in {"RR", "SR", "test"}
                or path in declared
            ):
                raise ValueError("source-documents.json 的原文路径或角色无效：" + row["path"])
            aliases = row.get("aliases", [])
            if not isinstance(aliases, list) or any(
                not isinstance(a, str) or not a.strip() for a in aliases
            ):
                raise ValueError("原文别名须为非空字符串列表")
            declared[path] = (role, aliases)
    found = []
    for path in sorted(declared if registered else root.rglob("*")):
        if (
            path.suffix.lower() not in ORIGIN_SUFFIXES
            or any(part.startswith(".") for part in path.relative_to(root).parts)
            or not path.is_file()
        ):
            continue
        role, aliases = declared.get(path, (None, []))
        role = role or (
            "RR"
            if "需求" in path.name or re.match(r"RR[._-]", path.name, re.I)
            else "SR"
            if "设计" in path.name or re.match(r"SR[._-]", path.name, re.I)
            else "test"
            if path.suffix.lower() == ".xlsx"
            or "测试" in path.name
            or re.match(r"test[._-]", path.name, re.I)
            else None
        )
        if role is None:
            continue
        try:
            relative = path.relative_to(root).as_posix()
            for doc in source_origins.read_origin_document(
                path, role, "test" if role == "test" else "existing"
            ):
                key = relative + ("#" + doc["sheet"] if doc.get("sheet") else "")
                found.append(
                    {
                        **doc,
                        "path": key,
                        "source_path": relative,
                        "id": ident("document", key),
                        "configured_aliases": aliases,
                        "registered": registered,
                    }
                )
        except (OSError, UnicodeError, ValueError):
            continue
    return source_origins.origin_index(found)


def cited_origins(bundle, origins):
    """Only the original documents a citation actually points at."""
    names = {
        (row.get("origin") or {}).get("document")
        for row in walk_refs(bundle)
        if (row.get("origin") or {}).get("match") in {"exact", "located"}
    }
    return [
        {"name": doc.get("path") or doc["name"], "role": doc.get("role"), "content": doc["content"]}
        for doc in origins
        if (doc.get("path") or doc["name"]) in names
    ]


def walk_refs(value):
    from scene_completion.inputs.documents.source_documents import walk_references

    return walk_references(value)
