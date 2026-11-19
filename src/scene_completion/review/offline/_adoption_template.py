"""Grouped offline three-party review; all presentation state stays outside the payload."""

from scene_completion.review.offline._ssd_review_template import TEMPLATE as READER

READER_STYLE = READER.split("<style>", 1)[1].split("</style>", 1)[0]
SOURCE_JS = READER[READER.index("function esc(") : READER.index("function sources(")]
TEMPLATE = (
    r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>业务场景采纳审核</title><style>"""
    + READER_STYLE
    + r"""
:root{color:#24364c;background:#f4f7fb;font-size:14px;font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
[hidden]{display:none!important}body{height:100vh;height:100dvh;display:grid;grid-template-rows:auto auto minmax(0,1fr);overflow:hidden}
button,select,textarea{font:inherit}button{border:1px solid #d4deec;border-radius:7px;padding:6px 11px;line-height:1.4;transition:background .12s;background:#fff;color:#355073}button:hover{background:#edf3fd;filter:none}button:focus-visible,select:focus-visible,summary:focus-visible,textarea:focus-visible{outline:2px solid #789bf1;outline-offset:2px}
button.primary{background:#3864d9;border-color:#3864d9;color:#fff}button.primary:hover{background:#2e54bb}
header.page-header{position:static;display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:13px 24px;border-bottom:1px solid #e0e7f0;background:#fff;z-index:3}
.brand{display:flex;align-items:center;gap:11px;margin-right:auto}.brand-mark{width:34px;height:34px;border-radius:10px;background:#eaf0ff;display:grid;place-items:center;color:#3864d9;font-weight:750;font-size:20px}.brand h1{font-size:19px;line-height:1.4;letter-spacing:.02em}.brand p{font-size:11px;color:#8090a5;margin:2px 0 0}.header-actions{display:flex;gap:8px}.header-actions button{font-size:12px}
nav.review-navigation{position:static;z-index:2;padding:9px 24px;background:white;border-bottom:1px solid #dfe7f2;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.tabs{display:flex;gap:3px;margin:0;background:#f0f4fa;padding:3px;border-radius:8px}.tabs button{border:0;background:transparent;color:#6d7f98;padding:6px 13px;font-size:13px;white-space:nowrap}.tabs button[aria-selected=true]{background:#fff;color:#315ecb;box-shadow:0 1px 4px #253e6120;font-weight:650}
.filters{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.filters label{display:flex;align-items:center;gap:7px;margin:0;font-size:12px;color:#71839a}.select-wrap{position:relative;display:inline-flex}.select-wrap:after{content:'⌄';position:absolute;right:10px;top:4px;color:#6f86a4;pointer-events:none}select{appearance:none;-webkit-appearance:none;background:white;border:1px solid #dae3ef;min-height:31px;border-radius:6px;padding:5px 28px 5px 10px;font-size:12px;color:#385273;max-width:280px}
main.review-main{max-width:none;width:100%;margin:0;min-height:0;overflow:auto;padding:18px 24px 36px;scroll-padding-top:70px}.reading-width{max-width:1560px;min-width:760px;margin:0 auto}.intro{margin:0 0 12px;display:flex;gap:20px;align-items:center;flex-wrap:wrap;font-size:12px;color:#72839a}.intro p{margin:0}.intro details{margin-left:auto}.summary-line{display:flex;align-items:center;gap:12px;flex-wrap:wrap;color:#6f819b;font-size:12px;margin:0 0 16px}.save-status{color:#88621f;background:#fff7dd;border-radius:5px;padding:5px 9px}.save-status:empty{display:none}.entry-title{display:flex;align-items:baseline;gap:12px;margin:0 0 14px}.entry-title h2{margin:0;font-size:18px;color:#293f5e}.entry-title span{font-size:12px;color:#8191a8}
.step-section{background:white;border:1px solid #dfe7f1;border-radius:10px;margin:0 0 20px;box-shadow:0 2px 8px #2b436505}.step-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid #e9eef5}.step-heading h3{font-size:14px;font-weight:650;margin:0 auto 0 0}.badge{display:inline-flex;border-radius:5px;padding:3px 7px;background:#eef3fa;font-size:11px;color:#6b809e;white-space:nowrap}.badge.blue{background:#eef3ff;color:#3b63ba}.badge.green{background:#e8f5ee;color:#2b7953}.step-context{margin:0;padding:9px 16px;font-size:12px;color:#6e829c;border-bottom:1px solid #edf1f7}.step-context summary{cursor:pointer}.context-body{margin:10px 0 2px;display:grid;grid-template-columns:1fr 1fr;gap:10px 22px;line-height:1.65}.context-body p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.context-body b{display:block;color:#4c6587;font-size:11px;margin-bottom:3px}.context-body .wide{grid-column:1/-1}
.concern-group{padding:0 16px 16px}.concern-heading{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:13px 0 10px}.concern-heading h4{font-size:14px;margin:0;color:#304d73}.concern-heading .binding{font-size:12px;color:#7d8fa7}.concern-heading .badge{margin-left:auto}
.review-grid{width:100%;min-width:720px;border-collapse:separate;border-spacing:0;table-layout:fixed;border:1px solid #e0e7f1;border-radius:7px}.review-grid thead{position:sticky;top:0;z-index:1}.review-grid th{position:static;top:auto;padding:10px 13px;font-size:12px;text-align:left;color:#5d7494;background:#f0f5fc;border-bottom:1px solid #dce5f2}.review-grid th:nth-child(1){width:26%}.review-grid th:nth-child(2){width:39%}.review-grid th:nth-child(3){width:35%}.review-grid td{padding:13px;vertical-align:top;background:white;border-bottom:1px solid #e8edf5;overflow-wrap:anywhere}.review-grid td+td,.review-grid th+th{border-left:1px solid #e8edf5}.review-grid tr:last-child td{border-bottom:0}.review-grid .reference-cell{background:#fbfcfe}.shared-note{font-size:11px;color:#8292a8;display:block;margin-bottom:10px}.record{margin:0;padding:0;border:0;overflow-wrap:anywhere}.record+.record{border-top:1px dashed #dfe6ef;margin-top:12px;padding-top:12px}.record .condition{font-weight:650;font-size:14px;color:#2d486d;line-height:1.65;margin:0 0 7px;white-space:pre-wrap}.expected{font-size:12px;line-height:1.65;color:#5d7695;margin:7px 0;white-space:pre-wrap}.expected b{font-weight:550;color:#7a8da8}.analysis{font-size:12px;line-height:1.75;color:#647c98;margin:8px 0}.analysis summary{cursor:pointer;color:#5979ac}.analysis p{white-space:pre-wrap;margin:7px 0}.record-status{font-size:11px;color:#8392a8;margin:6px 0}.sources{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin:7px 0}.sources button{border:0;background:transparent;padding:2px 0;color:#547ab8;font-size:11px;text-align:left;max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sources button+button{margin-left:6px}.sources .extra-sources{font-size:11px;color:#8b9aae}.sources .extra-sources summary{cursor:pointer}.sources .extra-sources[open]{flex-basis:100%}.muted{font-size:12px;line-height:1.65;color:#8797ad}.sources .muted{font-size:11px}
.review-grid td.adopted{background:#f5fbf7}.decision-actions{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin-bottom:8px}.decision-actions button{font-size:12px}.adoption-hint{font-size:11px;color:#8395a9;margin:6px 0}.adoption-preview{font-size:12px;color:#54765d;margin:7px 0}.adoption-preview summary{cursor:pointer}.adoption-preview .record{margin-top:9px}.notes{margin-top:10px;font-size:12px}.notes summary{cursor:pointer;color:#6682aa;max-width:100%;overflow-wrap:anywhere}.notes label{margin:8px 0 0;font-size:11px;color:#8292a8}.notes textarea{margin-top:4px;min-height:78px;padding:9px 10px;border:1px solid #d9e3ed;border-radius:6px;background:white;font-size:12px;line-height:1.7}.test-reference{margin:0 0 12px;font-size:12px;color:#7b8fa9}.test-reference summary{cursor:pointer}.test-reference .record{margin-top:8px}.coverage-links{font-size:11px;color:#6b82a3;margin:7px 0}.coverage-links summary{cursor:pointer}.coverage-links p{line-height:1.7}
.empty{font-size:13px;line-height:1.8;border-color:#d6e0ed;color:#7287a3}.empty button{margin-left:10px;font-size:12px}dialog{font-size:14px}dialog .sources button{max-width:none}.document{font-size:14px}.document p{white-space:normal}
@media(max-width:900px){header.page-header{padding:10px 14px}.brand h1{font-size:17px}.brand p{display:none}nav.review-navigation{padding:8px 14px;gap:8px}.filters{gap:8px}.header-actions button{padding:5px 8px}.tabs button{padding:6px 10px}main.review-main{padding:12px 14px 28px}.context-body{grid-template-columns:1fr}.context-body .wide{grid-column:auto}.intro details{margin-left:0}}
</style></head><body>
<header class="page-header"><div class="brand"><div class="brand-mark" aria-hidden="true">≋</div><div><h1>业务场景采纳审核</h1><p>SCENE REVIEW · E / G / GT</p></div></div><div class="header-actions"><button id="save-html" class="primary">保存含修改的 HTML</button><button id="save-json">导出审核 JSON</button></div></header>
<nav class="review-navigation" aria-label="审核范围与查看方式"><div class="tabs" id="tabs" role="tablist" aria-label="分析范围"></div><div class="filters"><label>用例／对象<span class="select-wrap"><select id="item-select"></select></span></label><label>查看<span class="select-wrap"><select id="review-mode"><option value="review">差异审核</option><option value="reference">完整参考（只读）</option></select></span></label><label id="reference-kind-label" hidden>粒度<span class="select-wrap"><select id="reference-kind"><option value="scenarios">场景</option><option value="concerns">关注点</option></select></span></label></div></nav>
<main class="review-main"><div class="reading-width"><div class="intro"><p id="mode-description"></p><details><summary>审核说明</summary><p>三方并排与共用原文只表示参考，不代表新增匹配。仅采纳已完成且GT未覆盖的G场景；回导预览并应用后，补入“业务审核补充GT”。原文与E/G始终只读。</p></details></div><div class="summary-line"><span id="counts"></span><span id="save-status" class="save-status" role="status"></span></div><div id="app"></div></div></main>
<dialog id="source-dialog"><div class="dialog-bar"><strong id="source-title"></strong><button id="source-close">关闭</button></div><article class="document" id="source-content"></article></dialog>
<script type="application/json" id="ssd-review-data">__ADOPTION_JSON__</script><script>
'use strict';
const state=JSON.parse(document.getElementById('ssd-review-data').textContent),app=document.getElementById('app');
const scopeNames={interaction:'交互级场景',business_chain:'业务链路场景',architecture:'项目架构场景'};
let scope='interaction',itemId='',mode='review',kind='scenarios';
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function changed(){document.getElementById('save-status').textContent='有未保存的审核修改，请保存HTML或导出JSON。';}
"""
    + SOURCE_JS
    + r"""
function sourceButton(entry,ref){
 const doc=(entry.bundle.documents||[]).find(d=>d.id===ref.document_id),name=doc?.name||ref.document_id||'出处',prefix=doc?.role==='RR'?'需求':doc?.role==='SR'?'设计':doc?.role==='test'?'测试':name.split(/[\\/]/).pop();
 const locator=ref.origin?.cell_range?ref.origin.sheet+'!'+ref.origin.cell_range:ref.start_line?'L'+ref.start_line:'';
 const b=el('button',[prefix,locator].filter(Boolean).join(' '));b.type='button';b.title=[name,locator].filter(Boolean).join(' ');b.setAttribute('aria-label',b.title);b.onclick=()=>showSource(entry,ref);return b;
}
function sources(entry,record){
 const wrap=el('div',undefined,'sources'),refs=record.source_refs||[],docs=entry.bundle.documents||[],original=refs.filter(r=>['RR','SR'].includes(docs.find(d=>d.id===r.document_id)?.role)),primary=original.length?original:refs;
 for(const ref of primary.slice(0,2))wrap.append(sourceButton(entry,ref));
 const rest=refs.filter(r=>!primary.slice(0,2).includes(r));
 if(rest.length){const d=el('details',undefined,'extra-sources');d.append(el('summary',`更多出处（${rest.length}）`));for(const ref of rest)d.append(sourceButton(entry,ref));wrap.append(d);}
 for(const reason of new Set(refs.map(r=>r.origin?.match==='pending'?r.origin.reason:null).filter(Boolean)))wrap.append(el('small','原文未定位 · '+reason,'muted'));
 if(!refs.length)wrap.append(el('span','无直接出处','muted'));return wrap;
}
const anchors=entry=>entry.bundle.steps||entry.bundle.anchors||[];
const anchorId=r=>r.anchor_id||r.step_id||'';
const binding=r=>JSON.stringify([anchorId(r),r.target||'',r.field_id||'',r.entity_id||'',r.attribute||'',r.key||'',...(r.obligation_scope||[]),r.operation_unit_id||'']);
const definition=(entry,r)=>entry.bundle.registry?.definitions?.[r.key]?.label||r.label||r.key||'待归类';
function objectLabel(entry,r){
 const anchor=anchors(entry).find(a=>a.id===anchorId(r)),unit=(entry.bundle.operation_units||[]).find(u=>u.id===r.operation_unit_id);
 if(unit)return [unit.command_id,unit.name].filter(Boolean).join(' · ');
 if(r.entity_id&&r.attribute)return '实体属性 · '+r.entity_id+'.'+r.attribute;
 if(r.target==='sender')return '发送方 · '+(anchor?.sender?.name||'待定位')+(r.entity_id?' · '+r.entity_id:'');
 if(r.target==='receiver')return '接收方 · '+(anchor?.receiver?.name||'待定位')+(r.entity_id?' · '+r.entity_id:'');
 if(r.target==='data'){const field=(anchor?.data||[]).find(f=>f.id===r.field_id);return '数据 · '+(field?[field.location,field.name].filter(Boolean).join('.'):r.field_id||'待定位字段')+(r.entity_id?' · '+r.entity_id:'');}
 return (r.target==='dependency'?'业务依赖':r.target==='service'?'外部服务':r.target||'待定位')+(r.entity_id?' · '+r.entity_id:'');
}
function stepEvidence(entry,label,ids){
 const line=el('p',label+' · ','muted');
 for(const id of ids){const step=(entry.bundle.steps||[]).find(s=>s.id===id), ref=(step?.source_refs||[])[0];
  if(ref){const button=el('button',id);button.title=step.operation?.name||id;button.onclick=()=>showSource(entry,ref);line.append(button);}
  else line.append(document.createTextNode(id+' '));}
 return line;
}
function record(entry,r,parent,channel,preview=false){
 const box=el('div',undefined,'record');if(!preview){box.dataset.recordId=r.id;box.dataset.channel=channel;}
 box.append(el('p',r.condition||r.label||definition(entry,r),'condition'));
 if(r.expected){const p=el('p',undefined,'expected');p.append(el('b','预期结果  '),document.createTextNode(r.expected));box.append(p);}
 if(r.failure_step_id)box.append(stepEvidence(entry,'实际失败步骤',r.failure_step_ids||[r.failure_step_id]));
 if(r.validation_step_ids?.length)box.append(stepEvidence(entry,'校验步骤',r.validation_step_ids));
 if(r.response_step_ids?.length)box.append(stepEvidence(entry,'响应步骤',r.response_step_ids));
 if(r.call_step_id)box.append(el('p','接口调用步骤 · '+r.call_step_id,'muted'));
 if(r.identification_reason)box.append(el('p','识别依据 · '+r.identification_reason,'muted'));
 if(r.analysis){const d=el('details',undefined,'analysis');d.append(el('summary','业务分析'),el('p',r.analysis));box.append(d);}
 box.append(sources(entry,r));
 if(r.requirement_refs?.length){box.append(el('p','关联需求／设计（非测试出处）','muted'),sources(entry,{source_refs:r.requirement_refs}));}
 if(mode==='reference'&&!preview){box.append(el('p',r.status==='active'?'有效记录':r.reason||r.binding_issue||r.status||'待确认','record-status'));}
 parent.append(box);return box;
}
function contextSection(entry,id){
 const a=anchors(entry).find(a=>a.id===id),section=el('section',undefined,'step-section');section.dataset.anchorId=id;
 const header=el('div',undefined,'step-heading'),label=a?.operation?`${a.order?'步骤 '+a.order+' · ':''}${a.sender?.name||''} → ${a.receiver?.name||''}`:a?.kind==='dependency'?`${a.from_case_id} → ${a.to_case_id}`:a?.name||'待定位／待确认';
 header.append(el('h3',label),el('span',a?.layer|| (a?.kind==='dependency'?'业务依赖':'外部服务'),'badge blue'),el('span',id||'无锚点','badge'));section.append(header);
 if(a){const details=el('details',undefined,'step-context'),summary=el('summary','展开上下文、数据与原文出处'),body=el('div',undefined,'context-body');
  const field=(label,value,wide=false)=>{const p=el('p',undefined,wide?'wide':undefined);p.append(el('b',label),document.createTextNode(value||'未记录'));body.append(p);};
  if(a.operation){const entityOnly=entry.bundle.analysis_profile==='entity-interaction-v1';field('操作',a.operation.name,true);field('CRUD',(a.operation.kinds||[]).join('/')||(entityOnly&&a.operation.kinds_source!=='pending'?'无 CRUD':'未确定'));field('实体',[...new Set([...(a.entity_ids||[]),...(['command-interaction-v2','command-interaction-v3'].includes(entry.bundle.analysis_profile)?(entry.bundle.field_anchors?.units||[]).filter(u=>u.step_id===a.id).map(u=>u.entity):[])])].join('、'));if(['command-interaction-v1','command-interaction-v2','command-interaction-v3'].includes(entry.bundle.analysis_profile)){const fields=(entry.bundle.steps||[]).flatMap(s=>(s.data||[]).filter(f=>f.command_id&&(s.id===a.id||f.call_step_id===a.id)));field('SR 字段',fields.map(f=>f.location+'.'+f.name).join('、'));const bindings=Object.entries(entry.bundle.command_bindings||{}).filter(([,b])=>b.primary_step_id===a.id);if(bindings.length)field('SR 命令',bindings.map(([id,b])=>id+(b.binding_source==='step1_fallback'?'（首步回退）':'')).join('、'));else if(a.operation.command_id)field('SR 命令',[a.operation.command_id,a.operation.http_method,a.operation.http_path].filter(Boolean).join(' '));}else if(!entityOnly){field('数据',(a.data||[]).map(f=>[f.location,f.name].filter(Boolean).join('.')).join('、')||'无数据字段');field('接口',a.api_id||'未关联接口');}}
  else if(a.kind==='dependency'){field('依赖条件',a.condition);field('义务／操作',a.obligation);field('实体',(a.entity_ids||[]).join('、'));field('依赖类型',a.relation_type==='cascade'?'级联依赖':'直接依赖');}
  else{field('服务职责',a.description);field('技术类别',a.technology);field('关联接口',(a.api_ids||[]).join('、'));field('涉及用例',(a.case_ids||[]).join('、'));}
  body.append(sources(entry,a));details.append(summary,body);section.append(details);
 }
 return section;
}
function referenceRecords(entry,records,parent,channel){
 if(!records.length){parent.append(el('span','暂无对应记录','muted'));return;}
 for(const r of records)record(entry,r,parent,channel);
}
function decision(entry,g){let d=state.decisions.find(d=>d.item_id===entry.id&&d.g_id===g.id);if(!d){d={item_id:entry.id,g_id:g.id,adopted:false,comment:''};state.decisions.push(d);}return d;}
function renderDecision(entry,row,td){
 td.replaceChildren();const g=row.cells.G[0],existing=state.decisions.find(d=>d.item_id===entry.id&&d.g_id===g.id);td.classList.toggle('adopted',Boolean(existing?.adopted));
 if(row.cells.GT?.length){const refs=el('details',undefined,'test-reference');refs.append(el('summary',`已有测试参考（${row.cells.GT.length}，未覆盖本场景）`));referenceRecords(entry,row.cells.GT,refs,'GT');td.append(refs);}
 const actions=el('div',undefined,'decision-actions'),button=el('button',existing?.adopted?'撤销采纳':'采纳');button.className=existing?.adopted?'':'primary';button.dataset.gId=g.id;button.setAttribute('aria-pressed',String(Boolean(existing?.adopted)));
 button.onclick=()=>{const d=decision(entry,g);d.adopted=!d.adopted;changed();renderDecision(entry,row,td);updateProgress(entry);};actions.append(button,el('span',existing?.adopted?'已采纳 · 待回导':'GT未覆盖',existing?.adopted?'badge green':'badge'));td.append(actions);
 if(existing?.adopted){const preview=el('details',undefined,'adoption-preview');preview.append(el('summary','预览业务补充GT（内容同本行G）'));record(entry,g,preview,'GT',true);td.append(preview);}
 const notes=el('details',undefined,'notes'),summary=el('summary',existing?.comment?'审核意见 · '+existing.comment.slice(0,48)+(existing.comment.length>48?'…':''):'添加审核意见'),label=el('label','审核意见'),input=el('textarea');input.value=existing?.comment||'';input.setAttribute('aria-label','审核意见 '+g.id);input.dataset.gId=g.id;
 input.oninput=()=>{decision(entry,g).comment=input.value;summary.textContent=input.value?'审核意见 · '+input.value.slice(0,48)+(input.value.length>48?'…':''):'添加审核意见';changed();};label.append(input);notes.append(summary,label);td.append(notes);
}
function addCoverage(entry,r,td){const status=entry.review_statuses?.[r.id];if(!status)return;td.append(el('p',status.label,'record-status'));if(status.links?.length){const d=el('details',undefined,'coverage-links');d.append(el('summary',`关联GT与覆盖依据（${status.links.length}）`));for(const link of status.links){d.append(el('p',`${link.status==='partial'?'部分覆盖':'完整覆盖'}：${link.reason}`));const gt=entry.bundle.channels.GT.scenarios.find(r=>r.id===link.id);if(gt)record(entry,gt,d,'GT',true);}td.append(d);}}
function updateProgress(entry){const count=entry.rows.filter(r=>state.decisions.some(d=>d.item_id===entry.id&&d.g_id===r.cells.G[0].id&&d.adopted)).length;const p=document.getElementById('adoption-progress');if(p)p.textContent=`已采纳 ${count} / ${entry.rows.length} 条`;}
function groupedRows(entry){
 if(mode==='review')return entry.rows;
 const rows=new Map();for(const channel of['E','G','GT'])for(const r of[...(entry.bundle.channels[channel][kind]||[]),...(kind==='scenarios'?(entry.bundle.channels[channel].pending||[]):[])]){
  const key=JSON.stringify([binding(r),kind==='scenarios'?r.condition:'',kind==='scenarios'?r.expected:'',r.status==='pending'?r.id:'']);
  if(!rows.has(key))rows.set(key,{id:key,anchor_id:anchorId(r),cells:{E:[],G:[],GT:[]}});rows.get(key).cells[channel].push(r);
 }return [...rows.values()];
}
function table(entry,rows){
 const byOriginal=new Map();for(const row of rows){const key=JSON.stringify((row.cells.E||[]).map(r=>r.id).sort());if(!byOriginal.has(key))byOriginal.set(key,[]);byOriginal.get(key).push(row);}rows=[...byOriginal.values()].flat();
 const t=el('table',undefined,'review-grid'),head=el('thead'),h=el('tr');for(const label of['原文已有 E · 共用参考','方法生成 G',mode==='review'?'测试逆向 GT／业务采纳':'测试逆向 GT'])h.append(el('th',label));head.append(h);t.append(head);const body=el('tbody');
 const signatures=rows.map(r=>JSON.stringify((r.cells.E||[]).map(x=>x.id).sort()));
 for(let i=0;i<rows.length;i++){const row=rows[i],line=el('tr');line.dataset.rowId=row.id;if(mode==='review')line.dataset.gId=row.cells.G[0].id;
  if(i===0||signatures[i]!==signatures[i-1]){let end=i+1;while(end<rows.length&&signatures[end]===signatures[i])end++;const cell=el('td',undefined,'reference-cell');cell.rowSpan=end-i;
   if(end-i>1&&row.cells.E.length){cell.dataset.commonE='true';cell.append(el('span',`共用原文参考 · ${end-i} 种场景`,'shared-note'));}
   referenceRecords(entry,row.cells.E,cell,'E');line.append(cell);
  }
  const g=el('td');referenceRecords(entry,row.cells.G,g,'G');if(mode==='reference'&&kind==='scenarios')for(const r of row.cells.G)addCoverage(entry,r,g);line.append(g);
  const gt=el('td');if(mode==='review')renderDecision(entry,row,gt);else referenceRecords(entry,row.cells.GT,gt,'GT');line.append(gt);body.append(line);
 }t.append(body);return t;
}
function renderGroups(entry){
 const rows=groupedRows(entry),byAnchor=new Map();for(const row of rows){const first=[...row.cells.G,...row.cells.E,...row.cells.GT][0],id=row.anchor_id||anchorId(first);if(!byAnchor.has(id))byAnchor.set(id,new Map());const groups=byAnchor.get(id),key=binding(first);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
 const order=new Map(anchors(entry).map((a,i)=>[a.id,i]));
 for(const [id,groups]of [...byAnchor].sort((a,b)=>(order.get(a[0])??1e9)-(order.get(b[0])??1e9))){const section=contextSection(entry,id);
  for(const groupRows of groups.values()){const first=[...groupRows[0].cells.G,...groupRows[0].cells.E,...groupRows[0].cells.GT][0],group=el('div',undefined,'concern-group'),heading=el('div',undefined,'concern-heading');group.dataset.binding=binding(first);
   heading.append(el('h4',definition(entry,first)),el('span',objectLabel(entry,first),'binding'),el('span',`${groupRows.length} ${kind==='concerns'&&mode==='reference'?'条关注点':'种场景'}`,'badge'));group.append(heading,table(entry,groupRows));section.append(group);
  }app.append(section);
 }
 if(!rows.length){const empty=el('div',mode==='review'?'本对象没有可采纳的缺失场景；已覆盖与未完成内容保留在完整参考中。':'本对象在该粒度暂无记录。','empty');if(mode==='review'){const b=el('button','查看完整参考');b.onclick=()=>{mode='reference';render();};empty.append(b);}app.append(empty);}
}
function render(){
 document.getElementById('review-mode').value=mode;document.getElementById('reference-kind-label').hidden=mode!=='reference';document.getElementById('reference-kind').value=kind;document.getElementById('mode-description').textContent=mode==='review'?'按步骤与关注点审核，每种失败条件独立采纳；共用原文仅作参考。':'完整只读参考 · 按步骤、对象与关注点查看三方记录。';
 const tabs=document.getElementById('tabs');tabs.replaceChildren();for(const[k,name]of Object.entries(scopeNames)){const b=el('button',name);b.setAttribute('role','tab');b.setAttribute('aria-selected',String(k===scope));b.onclick=()=>{scope=k;itemId='';render();};tabs.append(b);}
 const entries=state.items.filter(i=>i.scope===scope),select=document.getElementById('item-select');select.replaceChildren();entries.forEach(i=>{const o=el('option',i.name);o.value=i.id;select.append(o);});if(!entries.some(i=>i.id===itemId))itemId=entries[0]?.id||'';select.value=itemId;select.onchange=()=>{itemId=select.value;render();};app.replaceChildren();
 const summary=state.excluded.by_scope?.[scope],count=document.getElementById('counts');count.textContent=summary?`本层可审核 ${summary.exported} · 已覆盖 ${summary.covered} · 未完成 ${summary.unfinished} · 挂载待修正 ${summary.inactive} · 待确认来源 ${summary.source_pending}`:`已覆盖 ${state.excluded.covered} · 未完成 ${state.excluded.unfinished} · 挂载待修正 ${state.excluded.inactive}`;
 const entry=entries.find(i=>i.id===itemId);if(!entry){app.append(el('p','本范围暂无已保存结果。','empty'));return;}
 const title=el('div',undefined,'entry-title');title.append(el('h2',entry.name),el('span',`保存版本 ${entry.base_revision}`));if(mode==='review'){const p=el('span');p.id='adoption-progress';title.append(p);}app.append(title);updateProgress(entry);renderGroups(entry);
}
document.getElementById('review-mode').onchange=e=>{mode=e.target.value;render();};document.getElementById('reference-kind').onchange=e=>{kind=e.target.value;render();};
function safeJSON(v){return JSON.stringify(v).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');}
function download(content,type,name){const url=URL.createObjectURL(new Blob([content],{type})),a=el('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
document.getElementById('save-json').onclick=()=>download(JSON.stringify(state,null,2),'application/json;charset=utf-8','业务采纳审核.json');
document.getElementById('save-html').onclick=()=>{const clone=document.documentElement.cloneNode(true);clone.querySelector('#ssd-review-data').textContent=safeJSON(state);clone.querySelector('#app').replaceChildren();clone.querySelector('#save-status').textContent='';clone.querySelector('#source-dialog').removeAttribute('open');clone.querySelector('#source-content').replaceChildren();download('<!doctype html>\n'+clone.outerHTML,'text/html;charset=utf-8','业务采纳审核-已修改.html');};
render();
</script></body></html>"""
)
