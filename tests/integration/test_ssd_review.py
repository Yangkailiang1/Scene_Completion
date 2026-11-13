import shutil
import subprocess
from copy import deepcopy

import pytest

from scene_completion.review.offline import ssd_review as review
from tests.support.paths import ROOT


class Store:
    def __init__(self):
        self.cases = {}
        self.saves = []
        for case_id in ("UC-001", "UC-002"):
            source = {"document_id": "rr", "start_line": 2, "end_line": 2, "quote": "要求"}
            records = {
                ch: {
                    "id": f"{case_id}-{ch}",
                    "step_id": "step-1",
                    "target": "data",
                    "key": "data.range",
                    "label": "取值范围",
                    "condition": ch,
                    "status": "active",
                    "source_refs": [source],
                }
                for ch in ("G", "E", "GT")
            }
            bundle = {
                "version": "ssd-case-v1",
                "case": {"id": case_id, "name": case_id},
                "steps": [{"id": "step-1"}],
                "decisions": [],
                "pending": [],
                "documents": [
                    {
                        "id": "rr",
                        "name": "原始需求.md",
                        "role": "RR",
                        "content": "# 需求\n要求\n</script><img src=x>",
                    }
                ],
                "channels": {
                    ch: {"concerns": [r], "scenarios": [], "pending": []}
                    for ch, r in records.items()
                },
            }
            row = {
                "id": "row-1",
                "step_id": "step-1",
                "target": "data",
                "key": "data.range",
                "field_id": None,
                "cells": {ch: [r] for ch, r in records.items()},
                "status": "partial",
                "reason": "条件不同",
            }
            self.cases[case_id] = {
                "bundle": bundle,
                "revision": "r0",
                "comparison": {
                    "concerns": [row, {**row, "id": "matched", "status": "triple"}],
                    "scenarios": [],
                },
            }

    def index(self, project):
        return {"cases": [{"id": k, "name": k} for k in self.cases]}

    def editor(self, project, case_id):
        return deepcopy(self.cases[case_id])

    def save_revision(self, project, case_id, body):
        assert body["base_revision"] == self.cases[case_id]["revision"]
        self.saves.append((case_id, deepcopy(body)))
        self.cases[case_id]["bundle"] = deepcopy(body["bundle"])
        self.cases[case_id]["revision"] = f"r{len(self.saves)}"
        return self.editor(project, case_id)


@pytest.fixture
def store(monkeypatch):
    value = Store()
    monkeypatch.setattr(review, "_results", lambda: value)
    return value


def exported(store, **selection):
    return review._parse(review.export_html(None, selection))


def edit(payload, index=0):
    payload["cases"][index]["bundle"]["channels"]["E"]["concerns"][0]["condition"] = "人工修正"


def test_export_only_selected_discrepancies_and_escape_script(store):
    html = review.export_html(None, {"case_ids": ["UC-002"], "record_ids": ["UC-002-E"]})
    payload = review._parse(html)
    assert [c["case_id"] for c in payload["cases"]] == ["UC-002"]
    assert [r["id"] for r in payload["cases"][0]["rows"]] == ["row-1"]
    assert "</script><img src=x>" not in html
    assert payload["cases"][0]["bundle"]["documents"][0]["content"].endswith("<img src=x>")
    assert "cdn." not in html
    assert not exported(store, case_ids=[])["cases"]
    assert not exported(store, record_ids=[])["cases"]


def test_preview_diff_does_not_write_and_apply_is_idempotent(store):
    payload = exported(store, case_ids=["UC-001"])
    assert review.preview_feedback(None, payload)["cases"][0]["status"] == "unchanged"
    edit(payload)
    preview = review.preview_feedback(None, payload)
    assert preview["cases"][0]["status"] == "ready"
    assert preview["cases"][0]["changes"][0]["path"].endswith("/UC-001-E/condition")
    assert not store.saves
    assert review.apply_feedback(None, payload)["cases"][0]["status"] == "applied"
    assert review.apply_feedback(None, payload)["cases"][0]["status"] == "unchanged"
    # The persisted receipt also prevents an old file overwriting a later edit.
    store.cases["UC-001"]["bundle"]["channels"]["E"]["concerns"][0]["condition"] = "后续修正"
    store.cases["UC-001"]["revision"] = "r2"
    assert review.apply_feedback(None, payload)["cases"][0]["status"] == "unchanged"
    assert len(store.saves) == 1


def test_concurrent_revision_and_changed_documents_never_overwrite(store):
    payload = exported(store, case_ids=["UC-001"])
    edit(payload)
    store.cases["UC-001"]["revision"] = "another"
    assert review.apply_feedback(None, payload)["cases"][0]["status"] == "conflict"
    store.cases["UC-001"]["revision"] = "r0"
    payload["cases"][0]["bundle"]["documents"][0]["content"] = "篡改原文"
    assert review.preview_feedback(None, payload)["cases"][0]["status"] == "conflict"
    assert not store.saves


def test_only_selected_cases_apply_and_current_context_is_preserved(store):
    payload = exported(store)
    edit(payload, 0)
    edit(payload, 1)
    original = deepcopy(store.cases["UC-002"]["bundle"]["documents"])
    result = review.apply_feedback(None, payload, ["UC-002"])
    assert [c["case_id"] for c in result["cases"]] == ["UC-002"]
    assert store.saves[0][0] == "UC-002"
    assert store.cases["UC-002"]["bundle"]["documents"] == original


def test_import_html_only_parses_json_and_rejects_ambiguous_data(store):
    html = review.export_html(None, {"case_ids": ["UC-001"]})
    injected = html + '<script>throw new Error("never executed")</script>'
    assert review.preview_feedback(None, injected)["cases"][0]["status"] == "unchanged"
    with pytest.raises(ValueError, match="仅包含"):
        review.preview_feedback(None, html + html)
    with pytest.raises(ValueError, match="重复用例"):
        payload = exported(store)
        payload["cases"].append(payload["cases"][0])
        review.preview_feedback(None, payload)


def test_new_edit_of_same_export_is_not_silently_treated_as_duplicate(store):
    payload = exported(store, case_ids=["UC-001"])
    edit(payload)
    review.apply_feedback(None, payload)
    payload["cases"][0]["bundle"]["channels"]["E"]["concerns"][0]["condition"] = "又一次修正"
    assert review.apply_feedback(None, payload)["cases"][0]["status"] == "conflict"


def test_concurrency_between_preview_and_save_is_reported(store, monkeypatch):
    payload = exported(store, case_ids=["UC-001"])
    edit(payload)

    def conflict(*args, **kwargs):
        raise ValueError("版本已变化")

    monkeypatch.setattr(store, "save_revision", conflict)
    result = review.apply_feedback(None, payload)
    assert result["cases"][0]["status"] == "conflict"
    assert not store.saves


def test_offline_edit_save_reopen_and_source_highlight(store, tmp_path):
    root = ROOT
    jsdom = root / "frontend/node_modules/jsdom/lib/api.js"
    assert shutil.which("node"), "完整开发验收需要 Node.js；Windows 离线包只运行 tests/portable"
    assert jsdom.is_file(), "请先运行 npm ci --prefix frontend 安装离线 HTML 验收依赖"
    path = tmp_path / "review.html"
    path.write_text(review.export_html(None, {"case_ids": ["UC-001"]}), encoding="utf-8")
    script = r"""
const {JSDOM,VirtualConsole}=require(process.argv[2]);
const fs=require('node:fs'),assert=require('node:assert/strict');
const errors=[];let downloaded;
function open(html){
 const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 return new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){
  w.Blob=Blob;w.URL.createObjectURL=b=>{downloaded=b;return 'blob:test'};w.URL.revokeObjectURL=()=>{};
  w.HTMLAnchorElement.prototype.click=function(){};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
  w.HTMLDialogElement.prototype.close=function(){this.open=false};
  w.HTMLElement.prototype.scrollIntoView=function(){};
 }});
}
(async()=>{
 const dom=open(fs.readFileSync(process.argv[1],'utf8')),w=dom.window,d=w.document;
 assert.equal(d.querySelectorAll('.row').length,1);
 d.querySelector('#save-json').click();
 const untouched=JSON.parse(await downloaded.text());
 assert.deepEqual(untouched.cases[0].bundle,untouched.cases[0].baseline);
 const input=d.querySelector('textarea');input.value='人工修正 </script><img src=x>';
 input.dispatchEvent(new w.Event('input',{bubbles:true}));
 d.querySelector('.sources button').click();
 assert.equal(d.querySelector('#source-dialog').open,true);
 assert.ok(d.querySelector('#source-content .source-highlight'));
 assert.equal(d.querySelector('#source-content img'),null);
 d.querySelector('#save-html').click();
 const saved=await downloaded.text(),reopened=open(saved);
 assert.equal(reopened.window.document.querySelector('textarea').value,input.value);
 assert.equal(reopened.window.document.querySelectorAll('.row').length,1);
 assert.equal(reopened.window.document.querySelector('#source-dialog').open,false);
 reopened.window.document.querySelector('#save-json').click();
 const payload=JSON.parse(await downloaded.text());
 assert.equal(payload.cases[0].bundle.channels.E.concerns[0].condition,input.value);
 assert.equal(errors.length,0,errors.join('\n'));
 dom.window.close();reopened.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run(
        ["node", "-e", script, str(path), str(jsdom)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_offline_pending_confirmation_and_cross_row_match(store, tmp_path):
    root = ROOT
    jsdom = root / "frontend/node_modules/jsdom/lib/api.js"
    assert shutil.which("node"), "完整开发验收需要 Node.js；Windows 离线包只运行 tests/portable"
    assert jsdom.is_file(), "请先运行 npm ci --prefix frontend 安装离线 HTML 验收依赖"
    view = store.cases["UC-001"]
    bundle = view["bundle"]
    bundle["registry"] = {"definitions": {"data.range": {"label": "范围"}}}
    deferred = {
        "id": "deferred",
        "status": "pending",
        "condition": "待确认超时",
        "source_refs": [],
        "step_id": "step-1",
        "target": "receiver",
        "key": "data.range",
    }
    bundle["channels"]["GT"]["pending"] = [deferred]
    rows = view["comparison"]["scenarios"]
    for channel, condition in (("G", "条件A"), ("GT", "不同描述A")):
        record = {
            "id": "s-" + channel,
            "condition": condition,
            "expected": "失败",
            "status": "active",
            "step_id": "step-1",
            "target": "data",
            "key": "data.range",
            "concern_ids": [f"UC-001-{channel}"],
            "source_refs": [],
        }
        bundle["channels"][channel]["scenarios"] = [record]
        rows.append(
            {
                "id": record["id"],
                "step_id": "step-1",
                "target": "data",
                "key": "data.range",
                "cells": {ch: [record] if ch == channel else [] for ch in ("E", "G", "GT")},
                "status": "single",
                "reason": "语义待核对",
            }
        )
    rows.append(
        {
            "id": "pending-row",
            "step_id": "step-1",
            "target": "receiver",
            "key": "data.range",
            "status": "pending",
            "cells": {"E": [], "G": [], "GT": [deferred]},
            "reason": "待确认",
        }
    )
    path = tmp_path / "review.html"
    path.write_text(review.export_html(None, {"case_ids": ["UC-001"]}), encoding="utf-8")
    script = r"""
const {JSDOM,VirtualConsole}=require(process.argv[2]),fs=require('node:fs'),assert=require('node:assert/strict');
let downloaded,alerts=0;const errors=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
const dom=new JSDOM(fs.readFileSync(process.argv[1],'utf8'),{runScripts:'dangerously',virtualConsole:vc,beforeParse(w){w.Blob=Blob;w.URL.createObjectURL=b=>{downloaded=b;return 'blob:test'};w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){};w.alert=()=>alerts++;}});
(async()=>{const w=dom.window,d=w.document;
 let card=d.querySelector('.row:last-child');
 const confirm=()=>Array.from(card.querySelectorAll('button')).find(b=>b.textContent==='确认为异常');
 assert.ok(confirm());confirm().click();assert.equal(alerts,1);
 const expected=card.querySelectorAll('textarea')[1];expected.value='返回超时错误';expected.dispatchEvent(new w.Event('input',{bubbles:true}));confirm().click();
 d.querySelector('#save-json').click();let data=JSON.parse(await downloaded.text()).cases[0].bundle;
 assert.equal(data.channels.GT.pending.length,0);
 const fixed=data.channels.GT.scenarios.find(s=>s.id==='deferred');assert.equal(fixed.status,'active');
 assert.ok(data.channels.GT.concerns.find(c=>c.id===fixed.concern_ids[0]&&c.step_id==='step-1'&&c.target==='receiver'));
 const detail=d.querySelectorAll('.row')[1].querySelector('details');assert.ok(detail);
 const selects=detail.querySelectorAll('select');assert.equal(selects.length,3);
 for(const select of selects){const value=select.options[1].value;select.value=value;select.dispatchEvent(new w.Event('change',{bubbles:true}));}
 detail.querySelector('button').click();d.querySelector('#save-json').click();data=JSON.parse(await downloaded.text()).cases[0].bundle;
 assert.ok(data.decisions.find(x=>x.pair==='GT_G'&&x.left_id==='s-GT'&&x.right_id==='s-G'&&x.status==='full'));
 assert.equal(errors.length,0,errors.join('\n'));dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run(
        ["node", "-e", script, str(path), str(jsdom)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stdout + result.stderr
