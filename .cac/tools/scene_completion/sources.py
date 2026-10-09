"""Original-line chapter indexes and source citations shared by the three roles."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .document_extract import extract_document


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def index_document(path: str | Path) -> dict:
    document = extract_document(path)
    lines = document["text"].splitlines()
    chapters, stack = [], []
    fence = None
    for number, line in enumerate(lines, 1):
        marker = re.match(r"^\s*([\x60]{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif (marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence)
                  and not line[marker.end():].strip()):
                fence = None
            continue
        if fence:
            continue
        heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not heading:
            continue
        level, title = len(heading.group(1)), heading.group(2)
        while stack and stack[-1]["level"] >= level:
            stack.pop()["line_end"] = number - 1
        chapter = {"chapter_id": f"SEC-{fingerprint([Path(path).name, number, title])[:16]}",
                   "document": Path(path).name, "level": level, "title": title,
                   "heading_path": [x["title"] for x in stack] + [title],
                   "line_start": number, "line_end": len(lines)}
        chapters.append(chapter)
        stack.append(chapter)
    return {"document": Path(path).name, "format": document["format"],
            "content_hash": fingerprint(document["text"]), "line_count": len(lines),
            "text": document["text"], "chapters": chapters}


def index_sources(paths: list[str]) -> dict:
    documents = [index_document(path) for path in paths]
    if len({doc["document"] for doc in documents}) != len(documents):
        raise ValueError("source document filenames must be unique")
    return {"schema_version": "three-agent-v1", "documents": documents}


def chapter_ref(chapter: dict, start: int | None = None, end: int | None = None) -> dict:
    return {key: chapter[key] for key in ("document", "chapter_id", "heading_path")} | {
        "line_start": start or chapter["line_start"], "line_end": end or start or chapter["line_end"]}


def use_case_sections(index: dict, use_case_id: str) -> list[dict]:
    return [chapter for doc in index["documents"] for chapter in doc["chapters"]
            if re.search(re.escape(use_case_id) + r"(?![A-Za-z0-9])", chapter["title"])]


def source_refs(index: dict, location: str, use_case_id: str) -> list[dict]:
    for doc in index["documents"]:
        if doc["document"] not in str(location):
            continue
        match = re.search(r":(\d+)(?:-(\d+))?", str(location))
        if match:
            start, end = int(match[1]), int(match[2] or match[1])
            if not 1 <= start <= end <= doc["line_count"]:
                raise ValueError("source citation outside document")
            chapters = [c for c in doc["chapters"] if c["line_start"] <= start <= end <= c["line_end"]]
            if chapters:
                return [chapter_ref(max(chapters, key=lambda c: c["level"]), start, end)]
    return [chapter_ref(c) for c in use_case_sections(index, use_case_id)]


def validate_refs(refs: list, index: dict, allowed: list[dict] | None = None) -> list[dict]:
    if not isinstance(refs, list) or not refs:
        raise ValueError("source_refs must contain verifiable citations")
    validated = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("invalid citation")
        doc = next((d for d in index["documents"] if d["document"] == ref.get("document")), None)
        start, end = ref.get("line_start"), ref.get("line_end")
        if not doc or type(start) is not int or type(end) is not int or not 1 <= start <= end <= doc["line_count"]:
            raise ValueError("invalid source citation range")
        candidates = [c for c in doc["chapters"] if c["line_start"] <= start <= end <= c["line_end"]]
        if not candidates:
            raise ValueError("citation has no containing chapter")
        if allowed is not None:
            cursor = start
            for region in sorted((c for c in allowed if c["document"] == ref["document"]), key=lambda c: c["line_start"]):
                if region["line_start"] <= cursor <= region["line_end"] + 1:
                    cursor = max(cursor, region["line_end"] + 1)
            if cursor <= end:
                raise ValueError("citation outside assigned source sections")
        validated.append(chapter_ref(max(candidates, key=lambda c: c["level"]), start, end))
    return validated


def evidence_fragments(index: dict, use_case_id: str, width: int = 12) -> list[dict]:
    result = []
    for chapter in use_case_sections(index, use_case_id):
        doc = next(d for d in index["documents"] if d["document"] == chapter["document"])
        lines = doc["text"].splitlines()
        for start in range(chapter["line_start"], chapter["line_end"] + 1, width):
            end = min(start + width - 1, chapter["line_end"])
            text = "\n".join(lines[start - 1:end])
            if not text.strip():
                continue
            for offset in range(0, len(text), 8192):
                fragment = text[offset:offset + 8192]
                if fragment.strip():
                    result.append({"text": fragment, "source_ref": chapter_ref(chapter, start, end)})
    return result


def target_sections(index: dict, use_case_id: str) -> dict:
    return {doc["document"]: ([chapter_ref(c) for c in use_case_sections(index, use_case_id)
                              if c["document"] == doc["document"]] or []) for doc in index["documents"]}
