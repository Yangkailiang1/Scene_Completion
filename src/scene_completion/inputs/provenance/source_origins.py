"""Locate the original Markdown/Excel line behind a derived structured record.

Structured inputs (function tree, recovered use cases, structure models) cite
their own JSON pointers. Those files also carry a declared line or an evidence
id that belongs to the original specification. This module resolves such a
declaration to real lines supported by the quoted text. A verified declaration
selects its own range. Searching the document can return several locations,
each with its own citation. Missing quotations remain pending.
"""

import re
from bisect import bisect_right
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
        match = re.match(r"^\s*([^\n]+?):\s*(L\s*\d+[^\n]*?)\s+-\s+(.*)$", origin, re.S)
        if match:
            return match[1].strip(), match[3].strip(), match[2].strip()
        return None, origin, None
    if isinstance(origin, dict):
        return (
            origin.get("doc")
            or origin.get("document")
            or origin.get("file")
            or origin.get("source_file")
            or origin.get("path"),
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


def _reference_path(value):
    path = value.strip().replace("\\", "/")
    if path[:8].lower() == "//?/unc/":
        return "//" + path[8:]
    return path.removeprefix("//?/")


def _absolute_match(wanted, documents):
    windows = wanted.startswith("//") or bool(re.match(r"^[A-Za-z]:/", wanted))

    def parts(path):
        if windows:
            path = path.casefold()
        return [part for part in path.split("/") if part and part != "."]

    declared = parts(wanted)
    if not declared or ".." in declared:
        return None
    best, matches = 0, []
    for doc in documents:
        local = parts(_reference_path(doc.get("path") or doc["name"]))
        score = 0
        for given, registered in zip(reversed(declared), reversed(local)):
            if given != registered:
                break
            score += 1
        if score > best:
            best, matches = score, [doc]
        elif score and score == best:
            matches.append(doc)
    return matches[0] if len(matches) == 1 else None


def resolve_name(declared, documents):
    """Match a declared document name to one document by name/alias/role alias."""
    if not isinstance(declared, str) or not declared.strip():
        return None
    wanted = _reference_path(declared)
    relative = wanted.removeprefix("./")
    for priority, select in enumerate(
        (
            lambda doc: "/" in wanted and (doc.get("path") == relative or doc["name"] == relative),
            lambda doc: (
                wanted.casefold()
                in {_reference_path(a).casefold() for a in doc.get("configured_aliases", [])}
            ),
            lambda doc: stem(doc["name"]).casefold() == stem(wanted).casefold(),
            lambda doc: wanted.lower() in aliases_for(doc["name"]),
            lambda doc: wanted.lower() == str(doc.get("role") or "").lower(),
        )
    ):
        if priority >= 2 and "/" in wanted:
            if wanted.startswith("/") or re.match(r"^[A-Za-z]:/", wanted):
                return _absolute_match(wanted, documents)
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
    quoted_lines = _normalized(quote).splitlines()
    if not quoted_lines:
        return not str(text or "").strip()
    right = re.sub(r"^[\s|>*#\-+]+", "", quoted_lines[0]).rstrip()
    if not right:
        return False
    left = re.sub(r"^[\s|>*#\-+]+", "", str(text or "")).rstrip()
    if not left:
        return False
    return left == right or right in text or left in right


def _line_quote_hits(rows, quote):
    """Match quoted lines in order, including any blank lines in the quotation."""
    span = _normalized(quote).splitlines()
    if not span:
        return []
    hits = set()
    for n, row in enumerate(rows):
        if not _line_matches(row["text"], span[0]):
            continue
        window = rows[n : n + len(span)]
        if (
            len(window) == len(span)
            and window[-1]["number"] - row["number"] == len(span) - 1
            and all(_line_matches(source["text"], part) for source, part in zip(window, span))
        ):
            hits.add((row["number"], window[-1]["number"]))
    return sorted(hits)


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
    if wanted in _normalized(text):
        return True
    if "\n\n" in wanted:
        return False
    compact = _compact_quote(wanted)
    return bool(compact and compact in _compact_quote(text))


def _compact_quote(text):
    """Ignore whitespace and Markdown line decoration without changing words."""
    return "".join(
        re.sub(r"\s+", "", re.sub(r"^\s*(?:[>|]\s*|#{1,6}\s+|[*+-]\s+)+", "", line))
        for line in text.splitlines()
    )


def _quotation_hits(rows, quote):
    """Locate all occurrences, even when the document wraps a sentence."""
    if "\n\n" in _normalized(quote):
        return _line_quote_hits(rows, quote)
    wanted = _compact_quote(quote)
    if not wanted:
        return []
    pieces, offsets, length = [], [], 0
    for row in rows:
        offsets.append(length)
        piece = _compact_quote(row["text"])
        pieces.append(piece)
        length += len(piece)
    text = "".join(pieces)
    hits = set()
    for match in re.finditer(r"(?=" + re.escape(wanted) + ")", text):
        first = bisect_right(offsets, match.start()) - 1
        last = bisect_right(offsets, match.start() + len(wanted) - 1) - 1
        first_line, last_line = rows[first]["number"], rows[last]["number"]
        if last_line - first_line == last - first:
            hits.add((first_line, last_line))
    return sorted(hits)


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
    """Check the reported line and then search the named document for the quote."""
    span = declared if isinstance(declared, tuple) else declared_lines(declared)
    if span and (
        len(span) != 2 or not all(type(n) is int for n in span) or not 0 < span[0] <= span[1]
    ):
        span = None
    rows = document["lines"]
    if span and _verified(document, span, quote):
        hits, match = [span], "exact"
    else:
        hits, match = _quotation_hits(rows, quote), "located"
        if not hits:
            hits = _line_quote_hits(rows, quote)
        if not hits and len(_normalized(quote)) >= 12:
            # Some suppliers prepend a label or quote only part of a sentence.
            hits = _substring_hits(document, quote)
        if span:
            # Keep the nearby hit first for callers which open an initial location.
            hits.sort(key=lambda hit: not (span[0] - 2 <= hit[0] <= hit[1] <= span[1] + 2))
    if hits:
        by_number = {row["number"]: row["text"] for row in rows}
        first, *rest = [
            {
                "start_line": start,
                "end_line": end,
                "quote": "\n".join(by_number[n] for n in range(start, end + 1)),
            }
            for start, end in hits
        ]
        return {**first, "match": match, **({"additional_locations": rest} if rest else {})}
    return {
        "start_line": None,
        "end_line": None,
        "quote": str(quote or ""),
        "match": "pending",
        "reason": "原文未包含该引文" + ("；已尝试声明行 " + str(span) if span else ""),
    }


def locations(origin):
    """Return each location as its own citation with the same document identity."""
    primary = {key: value for key, value in origin.items() if key != "additional_locations"}
    return [
        primary,
        *({**primary, **location} for location in origin.get("additional_locations", [])),
    ]


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
        **(
            {"declared_line": f"L{declared[0]}–L{declared[1]}"}
            if isinstance(declared, tuple)
            else {}
        ),
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
