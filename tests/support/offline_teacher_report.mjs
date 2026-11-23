import fs from "node:fs";
import { pathToFileURL } from "node:url";
import assert from "node:assert/strict";

const [htmlPath, jsdomPath] = process.argv.slice(2);
const { JSDOM } = await import(pathToFileURL(jsdomPath).href);
const downloads = [];
function open(html) {
  return new JSDOM(html, {
    runScripts: "dangerously",
    pretendToBeVisual: true,
    beforeParse(w) {
      w.Blob = class {
        constructor(parts) {
          this.parts = parts;
        }
      };
      w.URL.createObjectURL = (blob) => {
        downloads.push(blob.parts.join(""));
        return "blob:offline";
      };
      w.URL.revokeObjectURL = () => {};
      w.HTMLAnchorElement.prototype.click = () => {};
      w.HTMLDialogElement.prototype.showModal = function () {
        this.setAttribute("open", "");
      };
      w.HTMLDialogElement.prototype.close = function () {
        this.removeAttribute("open");
      };
    },
  });
}

const first = open(fs.readFileSync(htmlPath, "utf8"));
const d = first.window.document;
const payload = (doc) => JSON.parse(doc.querySelector("#ssd-business-report-data").textContent);
const original = payload(d);
const mainCase = 'tbody[data-group-id="interaction:case"]';
const common = 'tbody[data-group-id="shared_services:project"]';
const edit = (control, value, type = "input") => {
  control.value = value;
  control.dispatchEvent(new control.ownerDocument.defaultView.Event(type, { bubbles: true }));
};
const headings = () => Array.from(d.querySelectorAll("#report-grid th"), (node) => node.textContent);
const group = () => d.querySelector(mainCase);
const choose = (select, label) => {
  const option = [...select.options].find((item) => item.textContent === label);
  assert.ok(option, label);
  edit(select, option.value, "change");
};

const defaultTitle = "异常场景完整性补全识别结果";
const editedTitle = "场景补全评审 <记录> & </script>";
assert.equal(d.querySelector("h1").textContent, defaultTitle);
assert.equal(d.title, defaultTitle);
d.querySelector("#edit-title").click();
edit(d.querySelector("#title-input"), "取消的标题");
d.querySelector("#cancel-title").click();
assert.equal(d.title, defaultTitle);
d.querySelector("#edit-title").click();
edit(d.querySelector("#title-input"), editedTitle);
d.querySelector("#title-form").dispatchEvent(new first.window.Event("submit", { cancelable: true }));
assert.equal(d.querySelector("h1").textContent, editedTitle);
assert.equal(d.title, editedTitle);
assert.match(d.querySelector("#case-count").textContent, /共 4 个用例.*3 个用例尚未完整/);
assert.equal(d.querySelectorAll('[role="tab"]').length, 3);
assert.deepEqual(headings(), ["用例", "异常场景", "异常场景数量"]);
assert.equal(group().rows.length, 1);
assert.equal(group().querySelectorAll('[data-field="text"]').length, 2);
assert.match(group().querySelector('[data-field="text"]').value, /^关联步骤 · 顾客发送商品查询\n具体异常 · /);
assert.match(group().querySelector(".quantity").textContent, /^2 项$/);
assert.ok(!d.querySelector("#report-toolbar select"));
edit(group().querySelector('[data-field="name"]'), "浏览商品（修改）");
edit(group().querySelector('[data-field="text"]'), "第一项场景编辑");

d.querySelector("#tab-g_only").click();
assert.deepEqual(headings(), [
  "用例", "异常场景", "异常场景数量", "异常关注点", "理由", "问题归因", "解决方案",
]);
assert.equal(group().rows.length, 3);
assert.equal(group().querySelector(".case-cell").rowSpan, 3);
assert.equal(group().querySelector(".quantity-cell").rowSpan, 3);
assert.equal(d.querySelector(common).querySelector(".quantity").textContent, "1 项");
const members = d.querySelector(common).querySelectorAll(".case-members b");
assert.deepEqual([...new Set([...members].map((item) => item.textContent))].sort(), ["用例 A", "用例 B"]);
const commonScene = d.querySelector(common + " .scene-edit");
assert.match(commonScene.querySelector('[data-field="text"]').value, /用例 A · 执行 A.*另有 1 个调用/);
assert.match(commonScene.querySelector(".scene-evidence").textContent, /用例 B · 执行 B/);
const reportTotal = d.querySelector("#tab-g_only").textContent;
choose(d.querySelector("#report-toolbar select"), "身份认证");
assert.equal(group().rows.length, 2);
assert.equal(group().querySelector(".quantity").textContent, "2 项");
assert.match(d.querySelector("#report-toolbar").textContent, /当前显示 2 项/);
assert.ok(!d.querySelector(common));
assert.equal(d.querySelector("#tab-g_only").textContent, reportTotal);

const auth = group().querySelector("[data-scene-id]");
assert.equal(auth.querySelector('[data-field="text"]').value,
  "关联步骤 · 顾客发送商品查询\n具体异常 · 凭证格式错误");
assert.match(group().querySelector('[data-field="reason"]').value, /发送方 顾客 · 身份认证/);
auth.querySelector(".scene-evidence button").click();
assert.equal(d.querySelector("#source-dialog").open, true);
assert.equal(d.querySelector('#source-content .source-highlight[data-line="2"]').textContent, "凭证必须有效。");
d.querySelector("#source-close").click();
edit(auth.querySelector('[data-field="text"]'), "离线编辑 <说明> & </script>");
edit(group().querySelector('[data-field="count_note"]'), "数量说明");
const reason = group().querySelector('[data-field="reason"]');
assert.equal(reason.parentElement.dataset.content, reason.value);
edit(reason, "补充理由");
assert.equal(reason.parentElement.dataset.content, "补充理由");
edit(group().querySelector('[data-field="cause_note"]'), "诊断说明");
edit(group().querySelector('[data-field="solution"]'), "处理方案");
assert.equal(group().querySelector('[data-field="cause"]').value, "");
assert.deepEqual([...group().querySelector('[data-field="cause"]').options].slice(1).map(o => o.value),
  ["关注点无用", "前置抽取问题", "需求文档漏写"]);
d.querySelector("#report-toolbar button").click();
edit(d.querySelector("#cause-name"), "规则边界待澄清");
d.querySelector("#cause-form").dispatchEvent(new first.window.Event("submit", { cancelable: true }));
edit(group().querySelector('[data-field="cause"]'), "规则边界待澄清", "change");
choose(d.querySelector("#report-toolbar select"), "全部关注点");
const permission = Array.from(group().querySelectorAll('select[data-field="concern"]')).find(e => e.value === "human.authorization");
assert.ok(permission.selectedOptions[0].disabled);
assert.equal(permission.selectedOptions[0].textContent, "权限控制（原关注点）");
assert.ok([...permission.options].some(o => o.value === "api.data.range"));
assert.ok(![...permission.options].some(o => o.value === "global.call_order"));
assert.ok(![...permission.options].some(o => o.value === "service.base.response_contract"));
choose(permission, "项目自定义关注点");
choose(d.querySelector("#report-toolbar select"), "项目自定义关注点");
assert.equal(group().rows.length, 1);
assert.equal(group().querySelector(".quantity").textContent, "1 项");

d.querySelector("#tab-gt_only").click();
assert.deepEqual(headings(), ["用例", "异常场景", "异常场景数量", "问题归因", "解决方案"]);
assert.ok(!d.querySelector("#report-toolbar select"));
assert.equal(group().rows.length, 1);
assert.equal(group().querySelector('[data-field="text"]').value,
  "实际失败步骤 · 商城核对商品是否存在\n具体异常 · 资源不存在");
assert.match(group().querySelector(".scene-evidence").textContent, /用测试逆向做的ground truth/);
assert.deepEqual([...group().querySelector('[data-field="cause"]').options].slice(1).map(o => o.value),
  ["关注点不够", "前置抽取问题"]);
edit(group().querySelector('[data-field="cause"]'), "关注点不够", "change");
edit(group().querySelector('[data-field="solution"]'), "补充 GT 独有场景的检查项。");
group().querySelector(".scene-evidence button").click();
assert.equal(d.querySelector("#source-content table").getAttribute("aria-label"), "验证 工作表");
assert.equal(d.querySelector('#source-content [data-cell="B120"]').textContent, "资源不存在");
d.querySelector("#source-close").click();

d.querySelector("#save-html").click();
const reopened = open(downloads.at(-1)), next = reopened.window.document;
assert.deepEqual(payload(next).report, original.report);
assert.equal(next.title, editedTitle);
assert.equal(next.querySelector("h1").textContent, editedTitle);
assert.equal(next.querySelector(mainCase + ' [data-field="name"]').value, "浏览商品（修改）");
assert.equal(next.querySelector(mainCase + ' [data-field="text"]').value, "第一项场景编辑");
next.querySelector("#tab-g_only").click();
assert.equal(next.querySelector(mainCase + " .quantity").textContent, "3 项");
const edited = next.querySelector(mainCase + ' [data-field="text"]');
assert.equal(edited.value, "离线编辑 <说明> & </script>");
for (const [field, value] of Object.entries({
  count_note: "数量说明", reason: "补充理由", cause: "规则边界待澄清", cause_note: "诊断说明", solution: "处理方案",
})) {
  assert.equal(next.querySelector(mainCase + ' [data-field="' + field + '"]').value, value);
}
assert.ok(Array.from(next.querySelector("#report-toolbar select").options).some(o => o.textContent === "项目自定义关注点"));
assert.ok(Array.from(next.querySelectorAll(mainCase + ' select[data-field="concern"]')).some(select => select.value === "human.example-review"));
next.querySelector("#tab-gt_only").click();
assert.equal(next.querySelector(mainCase + ' [data-field="cause"]').value, "关注点不够");
assert.equal(next.querySelector(mainCase + ' [data-field="solution"]').value, "补充 GT 独有场景的检查项。");
assert.equal(next.querySelectorAll("[data-g-id], #save-json").length, 0);
first.window.close();
reopened.window.close();
console.log(JSON.stringify({ saved_reopened: true }));
