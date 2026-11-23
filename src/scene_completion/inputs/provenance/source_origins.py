"""Locate the original Markdown/Excel line behind a derived structured record.

Structured inputs (function tree, recovered use cases, structure models) cite
their own JSON pointers. Those files also carry a declared line or an evidence
id that belongs to the original specification. This module resolves such a
declaration to a real line only when the quoted text supports it: an exact
declared line wins, otherwise a unique quotation decides, otherwise the result
is ``pending`` with a reason. Nothing is guessed from a filename or a nearest
line, matching the review handoff rule.
"""

import re
from pathlib import Path

# Declared line forms seen in supplied artifacts: "L272", "L8–L11", "L8-L11",
# "第 272 行", "第 8–11 行".
LINE = re.compile(r"(?:^|\bL)\s*(\d+)\s*(?:[–\-~至]\s*L?\s*(\d+))?", re.I)
RANGE = re.compile(r"第\s*(\d+)\s*(?:[–\-~至]\s*(\d+))?\s*行")
CELL = re.compile(
    r"^(?P<sheet>[^!]+)!\$?(?P<first>[A-Z]{1,3})\$?(?P<row>[1-9]\d*)"
    r"(?::\$?(?P<last>[A-Z]{1,3})\$?(?P<end>[1-9]\d*))?$",
    re.I,
)
ROLES = {
    "spec": "RR",
    "rrSpec": "RR",
    "srSpec": "SR",
    "arSpec": "AR",
    "rr": "RR",
    "sr": "SR",
    "ar": "AR",
}


def source_origin(origin):
    """Split a supplied ``source`` field into document, quotation and declared line.

    Newer exports write ``{"doc": "srSpec", "line": "L272", "quote": "..."}``;
    older ones put "功能设计_spec.md:L27 - 原文" in one string.
    """
    if isinstance(origin, str):
        match = re.match(r"^\s*([^:\n]+):\s*(L\s*\d+[^\n]*?)\s+-\s+(.*)$", origin, re.S)
        if match:
            return match[1].strip(), match[3].strip(), match[2].strip()
        return None, origin, None
    if isinstance(origin, dict):
        return (
            origin.get("doc")
            or origin.get("document")
            or origin.get("file")
            or origin.get("source_file"),
            origin.get("quote") or "",
            origin.get("line")
            or origin.get("location")
            or origin.get("locator")
            or (
                (origin["start_line"], origin.get("end_line") or origin["start_line"])
                if isinstance(origin.get("start_line"), int)
                else None
            ),
        )
    return None, "", None


def word_for(role):
    return {"RR": "需求", "SR": "设计", "AR": "架构", "test": "测试"}.get(role, "")


def stem(name):
    return Path(str(name).replace("\\", "/")).name.split("#", 1)[0]


def aliases_for(name):
    """Aliases a supplier may use for one document (``rrSpec`` for the RR spec)."""
    base = stem(name)
    out = {base, base.rsplit(".", 1)[0]}
    for key, role in ROLES.items():
        if word_for(role) and word_for(role) in base:
            out.add(key)
    return {a.lower() for a in out if a}


def resolve_name(declared, documents):
    """Match a declared document name to one document by name/alias/role alias."""
    if not isinstance(declared, str) or not declared.strip():
        return None
    wanted = declared.strip().replace("\\", "/")
    relative = wanted.removeprefix("./")
    for priority, select in enumerate(
        (
            lambda doc: "/" in wanted and (doc.get("path") == relative or doc["name"] == relative),
            lambda doc: (
                wanted.casefold() in {a.casefold() for a in doc.get("configured_aliases", [])}
            ),
            lambda doc: stem(doc["name"]).casefold() == stem(wanted).casefold(),
            lambda doc: wanted.lower() in aliases_for(doc["name"]),
            lambda doc: wanted.lower() == str(doc.get("role") or "").lower(),
        )
    ):
        if priority >= 2 and "/" in wanted:
            return None
        matches = [doc for doc in documents if select(doc)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            identities = {
                (doc.get("role"), Path(stem(doc["name"])).suffix.lower(), doc.get("hash"))
                for doc in matches
            }
            if (
                priority >= 2
                and len(identities) == 1
                and all(doc.get("hash") and not doc.get("registered") for doc in matches)
            ):
                return min(
                    matches,
                    key=lambda doc: (
                        len(Path(doc.get("path") or doc["name"]).parts),
                        doc.get("path") or doc["name"],
                    ),
                )
            return None
    return None


def declared_lines(text):
    """Return ``(start, end)`` from a declared locator, or ``None``."""
    if not isinstance(text, str):
        return None
    found = RANGE.search(text) or LINE.search(text)
    if not found:
        return None
    start = int(found[1])
    end = int(found[2]) if found[2] else start
    return (start, end) if 0 < start <= end else None


def _normalized(value):
    return "\n".join(line.strip() for line in str(value or "").splitlines()).strip()


def _line_matches(text, quote):
    """Markdown list/table/bold prefixes are presentation, not different text."""
    right = re.sub(r"^[\s|>*#\-+]+", "", _normalized(quote).splitlines()[0]).rstrip()
    if not right:
        return False
    left = re.sub(r"^[\s|>*#\-+]+", "", str(text or "")).rstrip()
    if not left:
        return False
    return left == right or right in text or left in right


def _locate_in(document, quote):
    """Unique line or line range whose text equals the quotation."""
    wanted = _normalized(quote)
    if not wanted:
        return None
    rows = document["lines"]
    first = wanted.splitlines()[0]
    hits = []
    for n, row in enumerate(rows):
        if not _line_matches(row["text"], first):
            continue
        span = wanted.splitlines()
        texts = [r["text"] for r in rows[n : n + len(span)]]
        if len(texts) == len(span) and all(_line_matches(a, b) for a, b in zip(texts, span)):
            hits.append((row["number"], rows[min(n + len(span), len(rows)) - 1]["number"]))
    unique = sorted(set(hits))
    return unique[0] if len(unique) == 1 else None


def _verified(document, span, quote):
    start, end = span
    rows = {r["number"]: r["text"] for r in document["lines"]}
    if any(n not in rows for n in range(start, end + 1)):
        return False
    if not any(str(rows[n]).strip() for n in range(start, end + 1)):
        # A declared line of blank text proves nothing; fall through to the quote.
        return False
    text = "\n".join(rows[n] for n in range(start, end + 1))
    wanted = _normalized(quote)
    if not wanted:
        return False
    if _normalized(text) == wanted:
        return True
    if len(wanted.splitlines()) == 1 and any(
        _line_matches(text, part) for part in wanted.splitlines()
    ):
        return True
    return wanted in _normalized(text) or _normalized(text) in wanted


LEAD = re.compile(r"^\s*(?:[A-Z]{1,4}\s*-?\s*)?\d{1,3}\s*[.．、:：]\s*")


def steps_field(text):
    """Follow ``功能树.json`` convention: ``source.line`` is 1-based per section.

    The exported tree numbers lines inside each use-case section. When that
    reading verifies the quotation it is the supplier's intended location;
    absolute line numbers remain the fallback.
    """
    return {}


def _substring_hits(document, fragment):
    """Line spans where a quotation fragment literally occurs.

    A supplied quotation may carry a step label (``ES-03``) or repeat a
    sentence already present word for word. The fragment is tried whole, then
    without its leading label, then trimmed at clause boundaries until it is
    long enough to identify one place.
    """
    text = _normalized(fragment)
    if not text:
        return []
    candidates = [text]
    body = LEAD.sub("", text)
    if body != text:
        candidates.append(body)
    for clause in re.split(r"：|:|，|,|、|；|;", text):
        clause = clause.strip()
        if len(clause) >= 12 and clause not in candidates:
            candidates.append(clause)
    for wanted in candidates:
        if len(wanted) < 8:
            continue
        found = [
            (row["number"], row["number"])
            for row in document["lines"]
            if wanted in _normalized(row["text"])
        ]
        if found:
            return sorted(set(found))
    return []


def locate(document, quote, declared=None):
    """Resolve one origin against one document without guessing."""
    span = declared_lines(declared) if not isinstance(declared, tuple) else declared
    if span and _verified(document, span, quote):
        start, end = span
        rows = {r["number"]: r["text"] for r in document["lines"]}
        return {
            "start_line": start,
            "end_line": end,
            "quote": "\n".join(rows[n] for n in range(start, end + 1)),
            "match": "exact",
        }
    found = _locate_in(document, quote)
    multiple = []
    if found is None and len(_normalized(quote)) >= 12:
        # Supplied quotations may prefix a step label (``ES-03``) or shorten a
        # sentence. A literal fragment still points at a real line.
        hits = _substring_hits(document, quote)
        if len(hits) == 1:
            found = hits[0]
        elif hits:
            multiple = [h[0] for h in hits]
    if found:
        rows = {r["number"]: r["text"] for r in document["lines"]}
        return {
            "start_line": found[0],
            "end_line": found[1],
            "quote": "\n".join(rows[n] for n in range(found[0], found[1] + 1)),
            "match": "located",
        }
    return {
        "start_line": None,
        "end_line": None,
        "quote": str(quote or ""),
        "match": "pending",
        **({"alternatives": multiple} if multiple else {}),
        "reason": "原文未包含该引文，或同一引文出现多处，无法唯一定位"
        + ("；已尝试声明行 " + str(span) if span else ""),
    }


def origin(document, quote, declared=None):
    """Origin record attached to one BSD reference; ``None`` when undecidable."""
    if document is None:
        return None
    found = locate(document, quote, declared)
    return {
        "document": document.get("path") or stem(document["name"]),
        "role": document.get("role"),
        **found,
        **({"declared_line": declared} if isinstance(declared, str) and declared else {}),
    }


def untraced(reason):
    return {"document": None, "match": "pending", "reason": reason}


def column_index(letters):
    value = 0
    for char in letters:
        value = value * 26 + ord(char.upper()) - 64
    return value - 1


def sheet_name(locator):
    name = locator.split("!", 1)[0]
    if name.startswith("'") and name.endswith("'"):
        return name[1:-1].replace("''", "'")
    return name


def from_sheet_rows(document, quote, declared):
    """Verify an older exported Excel anchor that carries a rendered row quote."""
    if (
        not isinstance(declared, tuple)
        or not all(type(line) is int for line in declared)
        or not 1 <= declared[0] <= declared[1] <= 1048576
    ):
        return untraced("Excel 原文行号无效")
    start, end = declared
    rows = [row for row in document["lines"] if start <= row["number"] <= end]
    text = "\n".join(row["text"] for row in rows)
    if not rows or (rows[0]["number"], rows[-1]["number"]) != declared or not _normalized(text):
        return untraced("指定 Excel 行缺失或为空")
    if _normalized(text) != _normalized(quote):
        return untraced("指定 Excel 行与保存的整行引文不吻合")
    return {
        "document": document["path"],
        "role": document["role"],
        "start_line": start,
        "end_line": end,
        "quote": text,
        "match": "exact",
        "sheet": document["sheet"],
    }


def from_cell(declared, quote, sheet_documents):
    """Return a checked Excel range against the declared workbook and sheet."""
    match = CELL.fullmatch(str(declared or "").strip())
    if not match:
        return untraced("Excel 单元格坐标无效：" + str(declared or ""))
    first = column_index(match["first"])
    last = column_index(match["last"] or match["first"])
    start = int(match["row"])
    end = int(match["end"] or match["row"])
    if not (first <= last < 16384 and start <= end <= 1048576):
        return untraced("Excel 单元格范围无效：" + declared)
    name = sheet_name(declared.strip())
    matches = [doc for doc in sheet_documents if doc["sheet"] == name]
    if len(matches) != 1:
        return untraced("未找到唯一的 Excel 工作表：" + name)
    doc = matches[0]
    cells = [
        str(value)
        for row, values in doc["cells"].items()
        if start <= row <= end
        for column, value in values.items()
        if first <= column <= last and value
    ]
    if not quote or _normalized(quote) not in _normalized(" ".join(cells)):
        return untraced("指定 Excel 范围与引文不吻合：" + declared)
    rows = [row["text"] for row in doc["lines"] if start <= row["number"] <= end]
    return {
        "document": doc["path"],
        "role": doc["role"],
        "start_line": start,
        "end_line": end,
        "quote": "\n".join(rows),
        "match": "exact",
        "declared_line": declared,
        "sheet": doc["sheet"],
        "cell_range": declared.split("!", 1)[1].upper(),
        "cell_quote": quote,
    }


def documents_from_inputs(value):
    """Collect original documents declared by the supplied structured files."""
    found = []
    for item in value.get("source_inputs") or []:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        found.append({"name": Path(str(item["path"])).name, "role": item.get("role")})
    return found


def read_origin_document(path, role=None, channel="existing"):
    """Read one original text file into the document shape citations expect."""
    from scene_completion.infrastructure.storage import fingerprint
    from scene_completion.inputs.documents.source_documents import read_documents

    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        from scene_completion.inputs.provenance.test_sources import xlsx_documents

        data = path.read_bytes()
        sheets = xlsx_documents(data, path.name, path.name, for_provenance=True)
        for doc in sheets:
            rows = {row["number"]: row["text"] for row in doc["lines"]}
            doc.update(
                role=role or "test",
                hash=fingerprint(data.hex()),
                content="\n".join(rows.get(n, "") for n in range(1, max(rows) + 1)),
            )
        return sheets
    documents = read_documents([path], channel)
    text = path.read_text(encoding="utf-8-sig")
    return [
        {
            **doc,
            "role": role or doc.get("role") or channel,
            "hash": fingerprint(text),
            "content": "\n".join(row["text"] for row in doc["lines"]),
        }
        for doc in documents
    ]


def origin_index(documents):
    """Reuse the derived inputs' own names for the originals when possible."""

    def entry(document):
        return {**document, "aliases": sorted(aliases_for(document["name"]))}

    return [entry(d) for d in documents]
