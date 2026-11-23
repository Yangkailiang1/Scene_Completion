import json
from io import BytesIO
from shutil import copytree
from zipfile import ZipFile

import pytest

from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
from scene_completion.inputs.provenance.ssd_sources import Sources
from scene_completion.inputs.structured import authoring_cases
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.input_conversion.core_input import convert, validate_core
from scene_completion.workflow.ssd.input_conversion.provenance import origin_documents
from tests.support.paths import ROOT
from tests.support.test_sources import workbook

BROWSE = ROOT / "datasets/mini-mall/examples/browse-product"
BOOK = "原件/RR-400#样例.xlsx"
SHEET = "测试#用例"


@pytest.fixture
def excel_case(tmp_path):
    source = tmp_path / "input"
    copytree(BROWSE, source)
    recovered = source / "recovered_usecases.json"
    records = json.loads(recovered.read_text(encoding="utf8"))
    citation = records[0]["evidence_locations"][1]
    citation.update(source_file="\\\\supplier\\share\\" + BOOK, location=f"{SHEET}!A51:O51")
    recovered.write_text(json.dumps(records, ensure_ascii=False), encoding="utf8")

    target = source / BOOK
    target.parent.mkdir()
    # Both worksheets have identical content at row 51. Only the declared sheet is evidence.
    rows = [[] for _ in range(50)] + [[""] * 14 + [citation["quote"], "邻列文本"]]
    with ZipFile(BytesIO(workbook(rows))) as sample, ZipFile(target, "w") as xlsx:
        sheets = sample.read("xl/workbook.xml").decode()
        xlsx.writestr(
            "xl/workbook.xml",
            sheets.replace('name="测试"', f'name="{SHEET}"').replace(
                "</sheets>", '<sheet name="另一工作表" sheetId="2" r:id="rId2"/></sheets>'
            ),
        )
        relations = sample.read("xl/_rels/workbook.xml.rels").decode()
        xlsx.writestr(
            "xl/_rels/workbook.xml.rels",
            relations.replace(
                "</Relationships>",
                '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
            ),
        )
        contents = sample.read("xl/worksheets/sheet1.xml")
        xlsx.writestr("xl/worksheets/sheet1.xml", contents)
        xlsx.writestr("xl/worksheets/sheet2.xml", contents)
    return source, citation


def test_excel_reference_round_trip_and_legacy_anchor(excel_case, tmp_path):
    source, citation = excel_case
    core = tmp_path / "core"
    assert convert(source, core, profile=COMMAND_OPERATION_PROFILE)["output"]
    assert validate_core(core)["valid"]
    assert (core / BOOK).read_bytes() == (source / BOOK).read_bytes()
    main = next(core.glob("cases/*/main-success.json"))
    documents = json.loads(main.read_text(encoding="utf8"))["documents"]
    sheets = {d["sheet"]: d for d in documents if d.get("sheet")}
    assert {d["path"] for d in sheets.values()} == {BOOK}
    assert len({d["id"] for d in sheets.values()}) == 2

    source_index = Sources(source, origin_documents(source))
    original = source_index.trace(citation)
    assert original["document"] == f"{BOOK}#{SHEET}"
    assert original["cell_range"] == "A51:O51"
    bundle = build_cases(core)[0]
    test = next(r for r in bundle["test_import_records"] if r["original_id"] == "EXT-02")
    assert [r["origin"] for r in test["source_refs"] if r.get("origin")] == [original]
    assert any(doc["name"] == original["document"] for doc in bundle["documents"])

    indexed = Sources(core, origin_documents(core))
    raw = authoring_cases.sys_operation(authoring_cases.read(main, core))
    item = next(r for r in raw["test-exceptions"] if r["extension_id"] == "EXT-02")
    assert item["anchor"]["document_id"] == sheets[SHEET]["id"]
    assert item["anchor"]["location"] == citation["location"]
    assert item["anchor"]["cell_quote"] == citation["quote"]

    def origins():
        rows = authoring_cases.supplied_exceptions(raw, indexed, main, "GT")
        row = next(r for r in rows if r["extension_id"] == "EXT-02")
        return [r["origin"] for r in row["source_refs"] if r.get("origin")]

    precise = item.pop("source_refs")
    assert origins() == [original]  # The new anchor also works on its own.

    legacy_doc = next(d for d in raw["documents"] if d["id"] == sheets[SHEET]["id"])
    legacy_doc.pop("sheet")
    legacy_doc["path"] = f"{BOOK}#{SHEET}"
    item["anchor"].pop("location")
    item["anchor"].pop("cell_quote")
    legacy_precise = [{k: v for k, v in r.items() if k != "sheet"} for r in precise]
    item["source_refs"] = legacy_precise
    assert origins() == [original]

    # An explicit but invalid cell citation must not be saved by the row fallback.
    legacy_precise[0]["quote"] = "邻列文本"
    [invalid] = origins()
    assert invalid["match"] == "pending" and "引文不吻合" in invalid["reason"]
    legacy_precise[0]["location"] = f"{SHEET}!A51:051"
    [invalid] = origins()
    assert invalid["match"] == "pending" and "坐标无效" in invalid["reason"]

    item["source_refs"] = []
    [row_only] = origins()
    assert row_only["document"] == original["document"]
    assert row_only["match"] == "exact" and row_only["start_line"] == 51
    assert "cell_range" not in row_only
    item["anchor"]["quote"] = "错误的行引文"
    assert origins()[0]["match"] == "pending"


def test_excel_basename_ambiguity_and_missing_sheet_remain_pending(excel_case):
    source, citation = excel_case
    second = source / "另一目录" / (source / BOOK).name
    second.parent.mkdir()
    second.write_bytes((source / BOOK).read_bytes())
    manifest = {
        "documents": [
            {"path": file.relative_to(source).as_posix(), "role": "RR"}
            for file in (source / BOOK, second)
        ]
    }
    (source / "source-documents.json").write_text(json.dumps(manifest), encoding="utf8")
    indexed = Sources(source, origin_documents(source))
    assert indexed.trace(citation)["match"] == "exact"
    assert (
        indexed.trace({**citation, "source_file": "\\\\supplier\\share\\" + second.name})["match"]
        == "pending"
    )
    ambiguous = indexed.trace({**citation, "source_file": second.name})
    assert ambiguous["match"] == "pending" and "唯一原始 Excel 工作簿" in ambiguous["reason"]
    missing = indexed.trace({**citation, "location": "已移除!A51:O51"})
    assert missing["match"] == "pending" and "Excel 工作表" in missing["reason"]
