"""Self-contained editable report with the same source reader as offline review."""

from ._adoption_template import READER_STYLE, SOURCE_JS

TITLE = "异常场景完整性补全识别结果"
TEMPLATE = (
    r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TEACHER_REPORT_TITLE__</title>
<style>"""
    + READER_STYLE
    + r"""
:root{font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:#22324c;background:#f2f5fa;font-size:14px}
[hidden]{display:none!important}
body{height:100vh;height:100dvh;display:grid;grid-template-rows:auto minmax(0,1fr);overflow:hidden}
.page-header{position:static;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px 24px;padding:20px clamp(14px,2vw,32px) 12px;border-bottom:1px solid #d8e1ef}
.report-heading{display:flex;align-items:center;flex-wrap:wrap;gap:4px 10px;margin-bottom:5px}
.page-header h1{overflow-wrap:anywhere;font-size:clamp(19px,2vw,26px);margin:0;letter-spacing:.03em}
#edit-title{padding:3px 8px;font-size:12px;color:#315baa}
.page-header p{margin:0}
.page-header .primary{background:#315baa;border-color:#315baa}
#report-tabs{grid-column:1/-1;display:flex;gap:8px;overflow:auto;padding:2px}
#report-tabs button{flex:0 0 auto;background:#f0f4fa;border-color:#d8e1ef;text-align:left}
#report-tabs [aria-selected=true]{background:#315baa;color:white;border-color:#315baa}
button:focus-visible,summary:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,.report-grid:focus-visible{outline:2px solid #4173ce;outline-offset:2px}
main.report-main{min-width:0;min-height:0;width:100%;max-width:none;margin:0;display:grid;grid-template-rows:auto minmax(0,1fr);gap:8px;padding:12px clamp(14px,2vw,32px) 16px}
.report-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;color:#55677f}
.report-toolbar p,.report-toolbar label{margin:0}
.report-toolbar select{max-width:min(240px,65vw);margin-left:6px;padding:5px 8px}
.report-toolbar button{padding:5px 9px;font-size:13px}
.report-grid{min-height:0;overflow:auto;border:1px solid #cbd7eb;border-radius:10px;background:white;overscroll-behavior:contain}
.report-table{width:100%;min-width:610px;border-spacing:0;table-layout:fixed}
.report-table.g_only{min-width:1120px}.report-table.gt_only{min-width:810px}
.report-table th{position:sticky;top:0;z-index:1;background:#315baa;color:white;text-align:left;font-weight:650;line-height:1.4}
.report-table th,.report-table td{padding:10px 12px;vertical-align:top;border-right:1px solid #d7e0ef;border-bottom:1px solid #d7e0ef}
.report-table tr>*:last-child{border-right:0}
.report-table tbody:nth-of-type(even){background:#f1f5fc}
.report-table .case-cell,.report-table .quantity-cell{background:#e9eff9}
.report-table .case-cell{border-left:3px solid #a6bbdf}
.report-table tr .scene-cell{overflow-wrap:anywhere}
.report-table textarea,.report-table input,.report-table select{background:#ffffffbf;border-color:#d0dbec;font-size:13px}
.report-table textarea{min-height:2.15em;field-sizing:content;padding:6px 8px;line-height:1.6}
.fitted-editor{display:grid;--editor-min:calc(3lh + 14px)}
.reason-editor{--editor-min:calc(6lh + 14px)}
.fitted-editor::after,.report-table .fitted-editor textarea{grid-area:1/1;min-width:0;min-height:var(--editor-min)}
.fitted-editor::after{content:attr(data-content) " ";visibility:hidden;white-space:pre-wrap;overflow-wrap:break-word;overflow:hidden;max-height:calc(14lh + 14px);padding:6px 8px;border:1px solid transparent;font:inherit;font-size:13px;line-height:1.6}
.report-table .fitted-editor textarea{field-sizing:fixed;align-self:stretch}
.report-table textarea[data-field=text]{color:#263d65}
.report-table select{width:100%;padding:6px 8px;margin-bottom:6px}
.report-table .case-name{font-weight:650}
.report-table .quantity{font-size:18px;font-weight:650;font-variant-numeric:tabular-nums;color:#315baa}
.report-table .case-state{display:block;margin-top:6px;font-size:12px;color:#685121}
.case-notes,.scene-evidence{color:#546783;font-size:12px;margin-top:7px}
.scene-evidence summary,.case-notes summary,.exclusions summary{cursor:pointer;color:#315baa}
.scene-evidence p{margin:5px 0;white-space:pre-wrap}
.scene-evidence button{font-size:12px;padding:3px 7px;text-align:left;overflow-wrap:anywhere}
.scene-evidence .case-members{margin:5px 0 5px 10px;padding-left:8px;border-left:1px solid #cbd7eb}
.scene-edit+.scene-edit{border-top:1px solid #cbd7eb;padding-top:9px;margin-top:9px}
.exclusions{font-size:12px}.exclusions ul{margin:6px 0;padding-left:20px}
.edit-dialog{width:min(415px,92vw);padding:18px}
.edit-dialog h2{font-size:17px;margin:0}
.edit-dialog .actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}
@media(max-width:550px){.page-header{grid-template-columns:1fr;gap:8px;padding-top:12px}.page-header .primary{justify-self:start}.page-header #save-status{font-size:12px}}
@media print{body{height:auto;display:block;overflow:visible}.page-header button:not([aria-selected=true]),.report-toolbar button,.report-toolbar label{display:none}.report-grid{overflow:visible}.report-table th{position:static}}
</style></head><body>
<header class="page-header">
<div>
<div class="report-heading"><h1 id="report-title">__TEACHER_REPORT_TITLE__</h1><button id="edit-title" type="button">编辑标题</button></div>
<p id="case-count" class="muted"></p>
</div>
<button id="save-html" class="primary" type="button">保存含修改的 HTML</button>
<nav id="report-tabs" role="tablist" aria-label="场景分类"></nav>
<p id="save-status" class="muted" role="status" hidden></p>
</header>
<main id="report-panel" class="report-main" role="tabpanel">
<div id="report-toolbar" class="report-toolbar"></div>
<div id="report-grid" class="report-grid" role="region" aria-label="异常场景表格" tabindex="0"></div>
</main>
<dialog id="source-dialog" aria-labelledby="source-title"><div class="dialog-bar"><strong id="source-title"></strong><button id="source-close" type="button">关闭</button></div><article class="document" id="source-content"></article></dialog>
<dialog id="title-dialog" class="edit-dialog" aria-labelledby="title-editor-heading">
<form id="title-form">
<h2 id="title-editor-heading">编辑报告标题</h2>
<label>报告标题<input id="title-input" required maxlength="160"></label>
<div class="actions"><button id="cancel-title" type="button">取消</button><button class="primary" type="submit">保存标题</button></div>
</form>
</dialog>
<dialog id="cause-dialog" class="edit-dialog" aria-labelledby="cause-title">
<form id="cause-form">
<h2 id="cause-title">新增归因类别</h2>
<label>类别名称<input id="cause-name" required maxlength="80"></label>
<div class="actions"><button id="cancel-cause" type="button">取消</button><button class="primary" type="submit">添加类别</button></div>
</form>
</dialog>
<script type="application/json" id="ssd-business-report-data">__TEACHER_REPORT_JSON__</script>
<script>
'use strict';
const state=JSON.parse(document.getElementById('ssd-business-report-data').textContent);
const report=state.report;
const sections={
 covered:{title:'方案生成的和 Ground Truth 的交集',widths:[18,64,18]},
 g_only:{title:'方案生成的有但是 Ground Truth 没有',widths:[11,22,10,12,17,13,15],
  causes:['关注点无用','前置抽取问题','需求文档漏写']},
 gt_only:{title:'方法生成没有但是 Ground Truth 有',widths:[16,39,13,15,17],
  causes:['关注点不够','前置抽取问题']}
};
const channels={E:'原文 E',G:'方案生成 G',GT:'用测试逆向做的ground truth'};
const editorFields={text:'异常场景',concern:'异常关注点',reason:'理由',cause_note:'归因说明',solution:'解决方案'};
const caseNames=new Map(report.cases.map(item=>[item.id,item.name]));
const concernLabels=new Map(Object.entries(report.concern_options));
const originalConcernLabels=new Map(report.groups.flatMap(group=>
 group.categories.g_only.map(scene=>[scene.concern_key,scene.concern])
));
const titleDialog=document.getElementById('title-dialog'),titleInput=document.getElementById('title-input');
const tabs=document.getElementById('report-tabs'),toolbar=document.getElementById('report-toolbar');
const panel=document.getElementById('report-panel'),grid=document.getElementById('report-grid');
const saveStatus=document.getElementById('save-status'),causeDialog=document.getElementById('cause-dialog');
let section='covered',concernFilter=null;
function el(tag,text,cls){
 const node=document.createElement(tag);
 if(text!==undefined)node.textContent=text;
 if(cls)node.className=cls;
 return node;
}
"""
    + SOURCE_JS
    + r"""
document.getElementById('source-close').onclick=()=>document.getElementById('source-dialog').close();
document.getElementById('case-count').textContent='共 '+report.case_count+' 个用例'+
 (report.case_details_included?'':' · 本文件仅包含共用外部服务')+
 (report.cases.some(item=>!item.complete)?' · '+report.cases.filter(item=>!item.complete).length+' 个用例尚未完整':'');
function changed(){
 saveStatus.hidden=false;
 saveStatus.textContent='有未保存的报告修改';
}
function showTitle(){
 document.title=state.edits.title??report.title;
 document.getElementById('report-title').textContent=document.title;
}
showTitle();
document.getElementById('edit-title').onclick=()=>{
 titleInput.value=document.title;
 titleDialog.showModal();
 titleInput.select();
};
document.getElementById('cancel-title').onclick=()=>titleDialog.close();
document.getElementById('title-form').onsubmit=event=>{
 event.preventDefault();
 const value=titleInput.value.trim();
 if(!value){titleInput.value='';titleInput.reportValidity();return;}
 if(value!==document.title){
  state.edits.title=value;
  showTitle();
  changed();
 }
 titleDialog.close();
};
function editKey(group,scene){
 return JSON.stringify(scene?[section,group.id,scene.id]:[section,group.id]);
}
function editValue(group,scene,field,fallback=''){
 const map=scene?state.edits.scenes:state.edits.groups;
 return map[editKey(group,scene)]?.[field]??fallback;
}
function saveEdit(group,scene,field,value){
 const map=scene?state.edits.scenes:state.edits.groups,key=editKey(group,scene);
 (map[key]??={})[field]=value;
 changed();
}
function input(group,scene,field,label,fallback='',textarea=true){
 const node=el(textarea?'textarea':'input');
 node.setAttribute('aria-label',label);
 node.dataset.field=field;
 node.value=editValue(group,scene,field,fallback);
 node.oninput=()=>saveEdit(group,scene,field,node.value);
 return node;
}
function appendSources(parent,group,refs){
 const links=el('div',undefined,'sources');
 for(const ref of refs||[]){
  const doc=group.bundle.documents.find(d=>d.id===ref.document_id);
  const origin=ref.origin;
  const exact=origin&&['exact','located'].includes(origin.match);
  const name=(exact?origin.document:doc?.name)||ref.document_id||'原文';
  const location=exact&&origin.cell_range
   ? origin.cell_range
   : ref.start_line?'L'+ref.start_line+(ref.end_line>ref.start_line?'–L'+ref.end_line:''):'';
  const button=el('button',[name.split('/').at(-1),location].filter(Boolean).join(' '));
  button.type='button';
  button.title=name;
  button.onclick=()=>showSource(group,ref);
  links.append(button);
 }
 if(links.childNodes.length)parent.append(links);
}
function recordEvidence(parent,group,record){
 if(record.condition)parent.append(el('p',record.condition));
 if(record.expected)parent.append(el('p','预期结果 · '+record.expected));
 appendSources(parent,group,record.source_refs);
 if(record.requirement_refs?.length){
  parent.append(el('p','关联需求或设计'));
  appendSources(parent,group,record.requirement_refs);
 }
}
function evidence(group,scene){
 const detail=el('details',undefined,'scene-evidence');
 detail.append(el('summary','原文与依据'),el('p',scene.classification));
 if(scene.step_evidence?.length){
  detail.append(el('strong','步骤原文与出处'));
  for(const step of scene.step_evidence){
   detail.append(el('p',step.text));
   appendSources(detail,group,step.source_refs);
  }
 }
 for(const link of scene.links){
  const status={full:'完整匹配',partial:'部分匹配'}[link.status]||'匹配依据';
  detail.append(el('p',[status,link.reason].filter(Boolean).join(' · ')));
 }
 for(const [channel,label] of Object.entries(channels)){
  if(!scene.evidence[channel]?.length)continue;
  detail.append(el('strong',label));
  for(const record of scene.evidence[channel]){
   recordEvidence(detail,group,record);
   for(const member of record.members){
    const item=el('div',undefined,'case-members');
    const name=caseNames.get(member.case_id)||member.case_id;
    if(name)item.append(el('b',name));
    recordEvidence(item,group,member);
    detail.append(item);
   }
  }
 }
 return detail;
}
function sceneEdit(group,scene){
 const wrapper=el('div',undefined,'scene-edit');
 wrapper.dataset.sceneId=scene.id;
 wrapper.append(fittedEditor(input(group,scene,'text',editorFields.text,scene.text)),evidence(group,scene));
 return wrapper;
}
function concernOf(group,scene){
 return editValue(group,scene,'concern_key',scene.concern_key);
}
function labeledOptions(entries){
 const counts=new Map();
 for(const [,label] of entries)counts.set(label,(counts.get(label)||0)+1);
 return entries.map(([key,label])=>[key,counts.get(label)>1?label+' · '+key:label])
  .sort((a,b)=>a[1].localeCompare(b[1],'zh-CN'));
}
const concernOptions=labeledOptions([...concernLabels]);
function concernCell(group,scene){
 const cell=el('td'),select=el('select');
 select.dataset.field='concern';
 select.setAttribute('aria-label',editorFields.concern);
 const current=concernOf(group,scene);
 if(!concernLabels.has(current)){
  const original=el('option',scene.concern+'（原关注点）');
  original.value=current;
  original.disabled=true;
  select.append(original);
 }
 for(const [key,label] of concernOptions){
  const option=el('option',label);
  option.value=key;
  select.append(option);
 }
 select.value=current;
 select.onchange=()=>{
  if(!concernLabels.has(select.value))return;
  const filter=concernFilter;
  saveEdit(group,scene,'concern_key',select.value);
  const filterSelect=document.getElementById('concern-filter');
  updateConcernFilter(filterSelect);
  if(filter!==null&&filter!==select.value){
   renderTable();
   filterSelect.focus();
  }
 };
 cell.append(select);
 return cell;
}
function updateConcernFilter(select){
 const values=new Map();
 for(const group of report.groups){
  for(const scene of group.categories.g_only){
   const concern=concernOf(group,scene);
   values.set(concern,(values.get(concern)||0)+1);
  }
 }
 if(concernFilter!==null&&!values.has(concernFilter))concernFilter=null;
 const options=[[null,'全部关注点'],...labeledOptions([...values.keys()].map(key=>
  [key,concernLabels.get(key)??originalConcernLabels.get(key)??key]
 ))];
 select.replaceChildren();
 for(const [value,label] of options){
  const option=el('option',label);
  option.value=value??'';
  option.selected=value===concernFilter;
  select.append(option);
 }
 select.onchange=()=>{
  concernFilter=select.value||null;
  updateConcernFilter(select);
  renderTable();
 };
 const visible=concernFilter===null?report.counts.g_only.total:values.get(concernFilter);
 document.getElementById('visible-count').textContent='当前显示 '+visible+' 项';
}
function renderToolbar(){
 toolbar.replaceChildren();
 const counts=report.counts[section];
 toolbar.append(el('p','用例合计 '+counts.cases+' 项 ＋ 共用外部服务 '+counts.shared_services+' 项 ＝ '+counts.total+' 项'));
 if(section==='g_only'){
  const label=el('label','按关注点筛选'),select=el('select'),visible=el('p',undefined,'muted');
  visible.id='visible-count';
  visible.setAttribute('aria-live','polite');
  select.id='concern-filter';
  label.append(select);
  toolbar.append(label,visible);
  updateConcernFilter(select);
 }
 if(sections[section].causes){
  const button=el('button','新增归因类别');
  button.type='button';
  button.onclick=()=>{
   document.getElementById('cause-form').reset();
   causeDialog.showModal();
  };
  toolbar.append(button);
 }
 const excluded=new Map();
 for(const group of report.groups){
  for(const item of group.excluded){
   excluded.set(item.reason,(excluded.get(item.reason)||0)+1);
  }
 }
 if(excluded.size){
  const details=el('details',undefined,'exclusions'),list=el('ul');
  details.append(el('summary','未纳入统计 '+[...excluded.values()].reduce((a,b)=>a+b,0)+' 项'));
  for(const [reason,count] of excluded)list.append(el('li',reason+' · '+count+' 项'));
  details.append(list);
  toolbar.append(details);
 }
}
function caseCell(group,span){
 const cell=el('td',undefined,'case-cell');
 cell.rowSpan=span;
 const field=input(group,null,'name','用例',group.name,false);
 field.className='case-name';
 cell.append(field);
 if(group.case_id)cell.append(el('small',group.case_id,'muted'));
 if(!group.complete)cell.append(el('span','尚未完整','case-state'));
 return cell;
}
function countCell(group,count,span){
 const cell=el('td',undefined,'quantity-cell');
 cell.rowSpan=span;
 const number=el('span',count+' 项','quantity');
 const details=el('details',undefined,'case-notes');
 const note=input(group,null,'count_note','数量备注');
 note.placeholder='填写数量备注';
 const label=el('summary',note.value?'已有数量备注':'添加数量备注');
 note.addEventListener('change',()=>{label.textContent=note.value?'已有数量备注':'添加数量备注';});
 details.append(label,note);
 cell.append(number,details);
 return cell;
}
function fieldCell(group,scene,field,fallback=''){
 const cell=el('td');
 cell.append(input(group,scene,field,editorFields[field],fallback));
 return cell;
}
function fittedEditor(field,cls=''){
 const editor=el('div',undefined,'fitted-editor'+(cls?' '+cls:''));
 editor.dataset.content=field.value;
 field.addEventListener('input',()=>{editor.dataset.content=field.value;});
 editor.append(field);
 return editor;
}
function reasonCell(group,scene){
 const cell=el('td');
 cell.append(fittedEditor(input(group,scene,'reason',editorFields.reason,scene.reason),'reason-editor'));
 return cell;
}
function fillCauseOptions(select,selected){
 select.replaceChildren();
 for(const text of ['',...sections[section].causes,...state.edits.causes[section]]){
  const option=el('option',text||'选择问题归因');
  option.value=text;
  select.append(option);
 }
 select.value=selected;
}
function causeCell(group,scene){
 const cell=el('td'),select=el('select');
 select.setAttribute('aria-label','问题归因');
 select.dataset.field='cause';
 fillCauseOptions(select,editValue(group,scene,'cause'));
 select.onchange=()=>saveEdit(group,scene,'cause',select.value);
 const note=input(group,scene,'cause_note',editorFields.cause_note);
 note.placeholder=editorFields.cause_note;
 cell.append(select,note);
 return cell;
}
function renderTable(){
 const table=el('table',undefined,'report-table '+section),columns=el('colgroup');
 table.setAttribute('aria-label',sections[section].title);
 for(const width of sections[section].widths){
  const column=el('col');
  column.style.width=width+'%';
  columns.append(column);
 }
 table.append(columns);
 const headings=['用例','异常场景','异常场景数量'];
 if(section==='g_only')headings.push('异常关注点','理由');
 if(section!=='covered')headings.push('问题归因','解决方案');
 const head=table.createTHead().insertRow();
 for(const name of headings){
  const cell=el('th',name);
  cell.scope='col';
  head.append(cell);
 }
 for(const group of report.groups){
  const records=group.categories[section].filter(
   scene=>section!=='g_only'||concernFilter===null||concernOf(group,scene)===concernFilter
  );
  if(!records.length&&concernFilter!==null&&section==='g_only')continue;
  const body=table.createTBody();
  body.dataset.groupId=group.id;
  const start=body.insertRow();
  if(section==='covered'||!records.length){
   const cell=el('td',undefined,'scene-cell');
   for(const scene of records)cell.append(sceneEdit(group,scene));
   if(!records.length)cell.append(el('span',group.complete?'本项无场景':'暂无已确认场景','muted'));
   start.append(caseCell(group,1),cell,countCell(group,records.length,1));
   for(const _heading of headings.slice(3))start.append(el('td'));
   continue;
  }
  records.forEach((scene,index)=>{
   const row=index===0?start:body.insertRow();
   const cell=el('td',undefined,'scene-cell');
   cell.append(sceneEdit(group,scene));
   if(index===0)row.append(caseCell(group,records.length));
   row.append(cell);
   if(index===0)row.append(countCell(group,records.length,records.length));
   if(section==='g_only'){
    row.append(concernCell(group,scene),reasonCell(group,scene));
   }
   row.append(causeCell(group,scene),fieldCell(group,scene,'solution'));
  });
 }
 if(!table.tBodies.length){
  const cell=table.createTBody().insertRow().insertCell();
  cell.colSpan=headings.length;
  cell.textContent='当前范围没有场景。';
 }
 grid.replaceChildren(table);
}
function setSection(next){
 section=next;
 for(const tab of tabs.children){
  const selected=tab.id==='tab-'+next;
  tab.setAttribute('aria-selected',String(selected));
  tab.tabIndex=selected?0:-1;
 }
 panel.setAttribute('aria-labelledby','tab-'+next);
 renderToolbar();
 renderTable();
 grid.scrollTop=0;
}
for(const [key,config] of Object.entries(sections)){
 const tab=el('button',config.title+' · '+report.counts[key].total+' 项');
 tab.type='button';
 tab.id='tab-'+key;
 tab.setAttribute('role','tab');
 tab.setAttribute('aria-controls','report-panel');
 tab.onclick=()=>setSection(key);
 tabs.append(tab);
}
tabs.onkeydown=event=>{
 if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
 const keys=Object.keys(sections),index=keys.indexOf(section);
 const next=event.key==='Home'?0:event.key==='End'?keys.length-1:
  (index+(event.key==='ArrowLeft'?-1:1)+keys.length)%keys.length;
 event.preventDefault();
 setSection(keys[next]);
 tabs.children[next].focus();
};
document.getElementById('cancel-cause').onclick=()=>causeDialog.close();
document.getElementById('cause-form').onsubmit=event=>{
 event.preventDefault();
 const field=document.getElementById('cause-name'),name=field.value.trim().normalize('NFC');
 if(!name){field.value='';field.reportValidity();return;}
 if(![...sections[section].causes,...state.edits.causes[section]].includes(name)){
  state.edits.causes[section].push(name);
  for(const select of grid.querySelectorAll('select[data-field=cause]')){
   fillCauseOptions(select,select.value);
  }
  changed();
 }
 causeDialog.close();
};
document.getElementById('save-html').onclick=()=>{
 const copy=document.documentElement.cloneNode(true);
 copy.querySelector('#ssd-business-report-data').textContent=JSON.stringify(state).replace(/[<>&\u2028\u2029]/g,
  c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
 for(const selector of ['#report-tabs','#report-toolbar','#report-grid','#source-content','#source-title','#save-status']){
  copy.querySelector(selector).replaceChildren();
 }
 copy.querySelector('.source-navigation')?.remove();
 copy.querySelector('#save-status').hidden=true;
 for(const dialog of copy.querySelectorAll('dialog'))dialog.removeAttribute('open');
 for(const selector of ['#cause-name','#title-input'])copy.querySelector(selector).removeAttribute('value');
 const blob=new Blob(['<!doctype html>\n'+copy.outerHTML],{type:'text/html;charset=utf-8'});
 const url=URL.createObjectURL(blob),anchor=el('a');
 anchor.href=url;
 anchor.download=report.title+'.html';
 anchor.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
 saveStatus.hidden=false;
 saveStatus.textContent='已下载含修改的报告';
};
setSection(section);
</script></body></html>
"""
).replace("__TEACHER_REPORT_TITLE__", TITLE)
