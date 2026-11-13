"""Independent source channels. Positive projections retain original line numbers."""

import re
from copy import deepcopy
from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint

# Section-level exclusion, including numbered use-case sections in existing specs.
EXCEPTION = re.compile(
    r"异常|扩展路径|备选流程|替代流程|失败路径|失败分支|错误处理|错误码|错误响应|错误返回|失败响应|异常处理|异常码|HTTP\s*[45]\d\d|exception|alternative\s+flow|error\s+(?:handling|responses?)",
    re.I,
)
SECTION = re.compile(r"^\s*(?:#{1,6}\s+|\d+[.、]\s*|\*\*\d+[.、]\s*)")


def read_documents(paths, channel):
    docs = []
    for path in paths:
        p = Path(path)
        if p.suffix.lower() == ".xlsx" and channel == "test":
            from scene_completion.inputs.provenance.test_sources import xlsx_documents

            docs.extend(xlsx_documents(p.read_bytes(), p.name, str(p.resolve())))
            continue
        if p.suffix.lower() not in {".md", ".markdown", ".json"}:
            raise ValueError(
                "需求来源支持Markdown或RR/SR结构模型JSON，测试来源支持Markdown、JSON或XLSX"
            )
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() == ".json":
            if channel == "test":
                from scene_completion.inputs.structured.recovered_tests import json_cases

                json_cases(text)
            else:
                from scene_completion.inputs.structured.structure_models import compile_model

                model = compile_model(text, p.name)
                if model is None:
                    raise ValueError(
                        "需求JSON必须为含scope.model_level、entities、relations的结构模型"
                    )
                docs.append({**model["document"], "channel": channel})
                continue
        lines = text.splitlines()
        docs.append(
            {
                "source_id": fingerprint(str(p.resolve()))[:20],
                "name": p.name,
                "channel": channel,
                "lines": [{"number": i, "text": s} for i, s in enumerate(lines, 1)],
            }
        )
    if len({d["source_id"] for d in docs}) != len(docs):
        raise ValueError("duplicate document")
    return docs


def read_project_documents(project, sources, channel):
    docs = []
    for source in sources:
        values = read_documents([Path(project) / source["path"]], channel)
        for d in values:
            suffix = "#" + d["name"].split("#", 1)[1] if "#" in d["name"] else ""
            from scene_completion.inputs.structured.structure_models import model_layer

            structured = model_layer(d) is not None
            d["name"] = source["name"] + (" · 结构化可读投影.md" if structured else suffix)
            if source.get("source_id") and not structured:
                d["source_id"] = source["source_id"] + (
                    "-" + fingerprint(suffix)[:12] if suffix else ""
                )
        docs.extend(values)
    return docs


def current_projection(documents):
    """Exclude explicitly labelled before-change sections; keep source line IDs."""
    out = []
    for doc in documents:
        rows = []
        blocked = False
        blocked_level = None
        for row in doc["lines"]:
            heading = re.match(r"^\s*(#{1,6})\s+", row["text"])
            level = len(heading[1]) if heading else None
            if heading and (
                "变更前" in row["text"]
                or "before change" in row["text"].lower()
                or "非抽取权威" in row["text"]
                or "关联实现接口OpenAPI文件" in row["text"]
            ):
                blocked = True
                blocked_level = level
                continue
            if blocked and level is not None and level <= blocked_level:
                blocked = False
            if not blocked:
                rows.append(deepcopy(row))
        out.append({**doc, "lines": rows})
    return out


def normal_projection(documents):
    result = []
    for doc in current_projection(documents):
        from scene_completion.inputs.structured.structure_models import model_layer

        if model_layer(doc) is not None:
            # Scenario kinds are explicit. A positive use case can legitimately
            # be named "重放异常事件"; keyword filtering would silently drop it.
            projected = []
            blocked = False
            for row in doc["lines"]:
                if row["text"].startswith("## "):
                    blocked = False
                if row["text"] == "### 异常及备选分支（仅已有场景通道）":
                    blocked = True
                if not blocked:
                    projected.append(deepcopy(row))
            result.append({**doc, "channel": "normal", "lines": projected})
            continue
        projected = []
        blocked = False
        blocked_heading = None
        for row in doc["lines"]:
            text = row["text"]
            is_section = bool(SECTION.match(text))
            heading = re.match(r"^\s*(#{1,6})\s+", text)
            level = len(heading[1]) if heading else None
            if (
                blocked
                and is_section
                and (
                    (blocked_heading is None and level is not None)
                    or (
                        level is not None
                        and blocked_heading is not None
                        and level <= blocked_heading
                    )
                )
            ):
                blocked = False
                blocked_heading = None
            if EXCEPTION.search(text):
                # Error table rows and mixed descriptive sentences are omitted,
                # not interpreted as a new section. Explicit branch labels block
                # all following response/action lines until the next section.
                if not text.lstrip().startswith("|") and (
                    is_section
                    or re.match(
                        r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:扩展路径|异常|错误响应|错误返回|失败响应|失败路径|失败分支)",
                        text,
                    )
                ):
                    blocked = True
                    blocked_heading = level
                continue
            if not blocked:
                projected.append(deepcopy(row))
        result.append({**doc, "channel": "normal", "lines": projected})
    return result


def validate_evidence(value, documents):
    allowed = {d["source_id"]: {r["number"]: r["text"] for r in d["lines"]} for d in documents}

    def visit(node):
        if isinstance(node, dict):
            if set(node) == {"source_id", "line_start", "line_end", "quote"}:
                rows = allowed.get(node["source_id"], {})
                start, end = node["line_start"], node["line_end"]
                if (
                    end < start
                    or end - start > 100
                    or any(i not in rows for i in range(start, end + 1))
                ):
                    raise ValueError(
                        "evidence outside allowed source channel: "
                        + node["source_id"]
                        + ":"
                        + str(start)
                        + "-"
                        + str(end)
                        + "; allowed sources: "
                        + ", ".join(allowed)
                    )
                text = "\n".join(rows[i] for i in range(start, end + 1))
                # Markdown indentation/CRLF is presentation. Keep all words,
                # internal spaces, punctuation and line boundaries significant.
                quote = node["quote"]
                if not quote.strip():
                    raise ValueError("evidence quote must contain actual source text")

                def normalized(s):
                    return "\n".join(line.strip() for line in s.splitlines())

                if quote not in text and normalized(quote) not in normalized(text):
                    raise ValueError(
                        f"evidence quote differs from source at {node['source_id']}:{start}-{end}; quote={node['quote'][:100]!r}; allowed_text={text[:240]!r}"
                    )
            else:
                for v in node.values():
                    visit(v)
        elif isinstance(node, list):
            for v in node:
                visit(v)

    visit(value)


def documents_in(value):
    docs = {}

    def visit(v):
        if isinstance(v, dict):
            if {"source_id", "channel", "lines"} <= v.keys():
                old = docs.get(v["source_id"])
                if old:
                    lines = {r["number"]: r for r in old["lines"]}
                    for row in v["lines"]:
                        if row["number"] in lines and lines[row["number"]]["text"] != row["text"]:
                            raise ValueError("same source line has conflicting content")
                        lines[row["number"]] = row
                    docs[v["source_id"]] = {
                        **old,
                        "lines": sorted(lines.values(), key=lambda r: r["number"]),
                    }
                else:
                    docs[v["source_id"]] = v
            else:
                for x in v.values():
                    visit(x)
        elif isinstance(v, list):
            for x in v:
                visit(x)

    visit(value)
    return list(docs.values())


def evidence_refs(value):
    refs = []

    def visit(v):
        if isinstance(v, dict):
            if set(v) == {"source_id", "line_start", "line_end", "quote"}:
                refs.append(v)
            else:
                for x in v.values():
                    visit(x)
        elif isinstance(v, list):
            for x in v:
                visit(x)

    visit(value)
    return refs


CASE_ID = re.compile(r"(?<![\w-])(?:UCG-\d+-UC\d+|SC\d+-UC\d+|UC-[A-Za-z0-9][\w-]*)(?![\w-])")


def discover_cases(documents):
    return list(
        dict.fromkeys(
            m.group()
            for d in documents
            for row in d["lines"]
            for m in CASE_ID.finditer(row["text"])
        )
    )


def case_projection(documents, case_id, case_ids):
    """Retain shared preamble and one case section; never mix neighbouring cases.

    Specs with IDs outside supported patterns must supply --use-case-id. Section
    boundaries then use those literal IDs. Line numbers remain original.
    """
    out = []
    for doc in documents:
        if doc.get("channel") == "test":
            # Test specifications commonly put use-case associations in table
            # rows, not Markdown headings. Never pass the whole test corpus
            # merely because its headings are AR/module names.
            def matches(text, cid):
                return bool(re.search(r"(?<![\w-])" + re.escape(cid) + r"(?![\w-])", text))

            associated = [
                r
                for r in doc["lines"]
                if r["text"].lstrip().startswith("|")
                and any(matches(r["text"], cid) for cid in case_ids)
            ]
            if associated:
                selected = {r["number"] for r in associated if matches(r["text"], case_id)}
                if not selected:
                    continue
                keep = set(selected)
                heading = []
                headers = []
                for row in doc["lines"]:
                    text = row["text"]
                    m = re.match(r"^\s*(#{1,6})\s+", text)
                    if m:
                        level = len(m[1])
                        heading = [p for p in heading if p[0] < level] + [(level, row["number"])]
                        headers = []
                    if text.lstrip().startswith("|") and not any(
                        matches(text, cid) for cid in case_ids
                    ):
                        if "关联需求" in text or re.match(r"^\s*\|\s*:?-+", text):
                            headers.append(row["number"])
                    if row["number"] in selected:
                        keep.update(n for _, n in heading)
                        keep.update(headers)
                out.append(
                    {**doc, "lines": [deepcopy(r) for r in doc["lines"] if r["number"] in keep]}
                )
                continue
            if not any(matches(r["text"], case_id) for r in doc["lines"]):
                continue
        current = None
        rows = []
        seen = False
        for row in doc["lines"]:
            text = row["text"]
            ids = [
                cid
                for cid in case_ids
                if re.search(r"(?<![\w-])" + re.escape(cid) + r"(?![\w-])", text)
            ]
            heading = bool(SECTION.match(text))
            if heading and ids:
                current = ids[0]
                seen = True
            if current is None or current == case_id:
                rows.append(deepcopy(row))
        if rows and (not seen or any(case_id in row["text"] for row in rows)):
            out.append({**doc, "lines": rows})
    return out
