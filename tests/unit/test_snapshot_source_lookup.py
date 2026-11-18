"""Result-page citations carry snapshot document ids, not imported source ids."""

import hashlib

import pytest

from scene_completion.infrastructure.storage import write_json
from scene_completion.review.handoff.review_handoff import snapshot_source, source_view

TEXT = "# 需求\n" + "\n".join(f"第 {n} 行正文" for n in range(1, 40))


def project_with_snapshot(tmp_path, *, content=TEXT, duplicates=False, file_text=None):
    snapshot_id = "document-abc123"
    (tmp_path / "ssd_results/case").mkdir(parents=True)
    write_json(
        tmp_path / "ssd_results/case/revisions/1.json",
        {"bundle": {"documents": [{"id": snapshot_id, "name": "spec.md", "content": content}]}},
    )
    file = tmp_path / "imports/spec.md"
    file.parent.mkdir(parents=True)
    file.write_bytes(
        (file_text if file_text is not None else content).replace("\n", "\r\n").encode()
    )
    rows = [{"number": n, "text": v} for n, v in enumerate(content.splitlines(), 1)]
    document = {
        "source_id": "import-raw-spec",
        "name": "spec.md",
        "path": "imports/spec.md",
        "file_hash": hashlib.sha256(file.read_bytes()).hexdigest(),
        "lines": rows,
        "role": "RR",
    }
    documents = [document]
    if duplicates:
        copy = tmp_path / "imports/spec-copy.md"
        copy.write_bytes(file.read_bytes())
        documents.append(
            {**document, "source_id": "import-raw-copy", "path": "imports/spec-copy.md"}
        )
    write_json(tmp_path / "review_sources.json", {"documents": documents})
    return snapshot_id


def test_snapshot_document_id_resolves_to_the_identical_source_lines(tmp_path):
    snapshot_id = project_with_snapshot(tmp_path)
    view = source_view(tmp_path, snapshot_id, start=12, end=14, context=0, view="window")
    assert (view["highlight_start"], view["highlight_end"]) == (12, 14)
    assert [r["number"] for r in view["lines"]] == [12, 13, 14]
    assert view["lines"][0]["text"] == "第 11 行正文"


def test_identical_copies_resolve_but_different_content_is_never_guessed(tmp_path):
    assert snapshot_source(tmp_path, project_with_snapshot(tmp_path, duplicates=True))

    other = tmp_path / "other"
    other.mkdir()
    # The snapshot holds text that no source file contains.
    snapshot_id = project_with_snapshot(other, file_text=TEXT + "\n额外一行")
    assert snapshot_source(other, snapshot_id) is None
    with pytest.raises(ValueError):
        source_view(other, snapshot_id, start=1, view="window")
