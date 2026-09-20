"""Document text extraction with source-location metadata."""

from __future__ import annotations

import re
from pathlib import Path


def _plain_text(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = [{"location": f"line {i}", "text": line} for i, line in enumerate(text.splitlines(), 1)]
    return {"path": str(path), "format": path.suffix.lower().lstrip("."), "text": text, "locations": lines}


def _docx_text(path: Path) -> dict:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("DOCX extraction requires python-docx") from exc
    document = Document(str(path))
    locations = []
    for idx, paragraph in enumerate(document.paragraphs, 1):
        if paragraph.text.strip():
            locations.append({"location": f"paragraph {idx}", "text": paragraph.text})
    for table_idx, table in enumerate(document.tables, 1):
        for row_idx, row in enumerate(table.rows, 1):
            text = " | ".join(cell.text.strip() for cell in row.cells)
            if text.strip():
                locations.append({"location": f"table {table_idx}, row {row_idx}", "text": text})
    return {"path": str(path), "format": "docx", "text": "\n".join(x["text"] for x in locations), "locations": locations}


def _pdf_text(path: Path) -> dict:
    pages = []
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        for page_idx, page in enumerate(reader.pages, 1):
            pages.append({"location": f"page {page_idx}", "text": page.extract_text() or ""})
    except ImportError:
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                for page_idx, page in enumerate(pdf.pages, 1):
                    pages.append({"location": f"page {page_idx}", "text": page.extract_text() or ""})
        except ImportError as exc:
            raise RuntimeError("PDF extraction requires pypdf or pdfplumber") from exc
    text = "\n".join(page["text"] for page in pages).strip()
    if not text:
        raise RuntimeError("PDF contains no extractable text; OCR or a text-based PDF is required")
    return {"path": str(path), "format": "pdf", "text": text, "locations": pages}


def extract_document(path: str | Path) -> dict:
    """Extract a supported document and return text plus source locations."""
    source = Path(path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"document not found: {source}")
    suffix = source.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        result = _plain_text(source)
    elif suffix == ".docx":
        result = _docx_text(source)
    elif suffix == ".pdf":
        result = _pdf_text(source)
    else:
        raise ValueError("unsupported document format; use .md, .markdown, .txt, .docx, or .pdf")
    result["text"] = re.sub(r"\n{3,}", "\n\n", result["text"]).strip()
    return result
