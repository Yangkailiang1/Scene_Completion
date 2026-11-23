"""Three-section report with frozen evidence and only G-only adoption controls."""

from scene_completion.review.offline._adoption_template import TEMPLATE as BASE

REPORT_JS = r"""
let reportSection='covered';
function referenceEntry(entry){const excluded=new Set(entry.reference_excluded_ids||[]);return {...entry,bundle:{...entry.bundle,channels:Object.fromEntries(Object.entries(entry.bundle.channels).map(([c,data])=>[c,Object.fromEntries(Object.entries(data).map(([kind,rows])=>[kind,Array.isArray(rows)?rows.filter(r=>!excluded.has(r.id)):rows]))]))}};}
const reportNames={covered:'第一项：G ∩ 测试逆向',g_only:'第二项：G有，测试逆向没有',gt_only:'第三项：G没有，测试逆向有'};
function updateProgress(){const p=document.getElementById('adoption-progress');if(p)p.textContent='已采纳 '+state.decisions.filter(d=>d.adopted).length+' 条（保存文件后回导应用）';}
function caseLink(cid){const a=el('a',cid);a.href='#report-case-'+cid;a.onclick=()=>{if(itemId){itemId='';render();}const section=document.getElementById('report-case-'+cid);if(section)section.open=true;};return a;}
function callMembers(entry,row,parent){
 const source=row.cells.G[0]||row.cells.GT[0];if(!source?.members?.length)return;
 const d=el('details',undefined,'analysis');d.append(el('summary','涉及调用与各自处理预期（'+source.members.length+'）'));
 for(const member of source.members){const box=el('div',undefined,'record');box.append(el('p',(member.case_id||'历史架构结果')+(member.step_id?' · '+member.step_id:''),'condition'));if(member.case_id)box.append(caseLink(member.case_id));if(member.condition)box.append(el('p',member.condition));if(member.expected)box.append(el('p','预期：'+member.expected,'expected'));if(member.analysis)box.append(el('p',member.analysis));box.append(sources(entry,member));d.append(box);}parent.append(d);
}
function reportTable(entry,rows){
 const previous=mode;mode=reportSection==='g_only'?'review':'reference';const result=table(entry,rows);mode=previous;
 for(const row of rows){const line=[...result.querySelectorAll('tbody tr')].find(t=>t.dataset.rowId===row.id);if(!line)continue;
  const g=line.cells[line.cells.length-2];callMembers(entry,row,g);
  if(row.links?.length){const d=el('details',undefined,'coverage-links');d.append(el('summary','匹配判定及依据'));for(const link of row.links)d.append(el('p',(binaryReview(entry)?'匹配':link.status==='partial'?'部分覆盖':'完整覆盖')+'：'+link.reason));line.lastElementChild.append(d);}
 }return result;
}
function reportDetails(entry,rows){
 const groups=new Map();for(const row of rows){const id=row.anchor_id||'';if(!groups.has(id))groups.set(id,new Map());const exemplar=row.cells.G[0]||row.cells.GT[0];const key=binding(exemplar);const concerns=groups.get(id);if(!concerns.has(key))concerns.set(key,[]);concerns.get(key).push(row);}
 const wrap=el('div');for(const [id,concerns]of groups){const section=contextSection(entry,id);for(const values of concerns.values()){const group=el('div',undefined,'concern-group');const exemplar=values[0].cells.G[0]||values[0].cells.GT[0];const heading=el('div',undefined,'concern-heading');heading.append(el('h4',definition(entry,exemplar)),el('span',objectLabel(entry,exemplar),'binding'),el('span',values.length+' 种场景','badge'));group.dataset.binding=binding(exemplar);group.append(heading,reportTable(entry,values));section.append(group);}wrap.append(section);}return wrap;
}
function render(){
 const ref=mode==='reference';document.getElementById('review-mode').value=mode;document.getElementById('reference-kind-label').hidden=!ref;
 document.querySelector('.brand h1').textContent=state.report.title;
 const tabs=document.getElementById('tabs');tabs.replaceChildren();for(const [key,name]of Object.entries(reportNames)){const b=el('button',name+' · '+state.report.counts[key].total+' 条');b.setAttribute('role','tab');b.setAttribute('aria-selected',String(key===reportSection));b.onclick=()=>{reportSection=key;render();};tabs.append(b);}
 const select=document.getElementById('item-select');select.replaceChildren();const all=el('option','全部用例与共用服务');all.value='';select.append(all);for(const i of state.items){const o=el('option',i.name);o.value=i.id;select.append(o);}select.value=itemId;select.onchange=()=>{itemId=select.value;render();};
 const grain=state.items.some(binaryReview);
 document.getElementById('mode-description').textContent='一共是 '+state.report.case_count+' 个 use case · '+(grain?'按匹配与不匹配统计，历史项目沿用冻结口径。':'full、partial 均算覆盖。')+' E 作为依据。';
 const excluded=state.items.reduce((n,i)=>n+(i.report_excluded||[]).length,0);document.getElementById('counts').textContent='待核对／未完成 '+excluded+' 条，不混入已确认分类。';
 app.replaceChildren();const heading=el('div',undefined,'entry-title');heading.append(el('h2',ref?'完整参考（只读）':reportNames[reportSection]+'：共 '+state.report.counts[reportSection].total+' 条'));const progress=el('span');progress.id='adoption-progress';heading.append(progress);app.append(heading);updateProgress();
 if(!ref){const total=state.report.counts[reportSection];app.append(el('p','用例合计 '+total.cases+' 条 ＋ 共用外部服务 '+total.shared_services+' 条 ＝ '+total.total+' 条','report-equation'));}
 const entries=state.items.filter(i=>!itemId||i.id===itemId);
 for(const [index,info]of (state.report.case_details_included===false?[]:state.report.cases).entries()){
  const entry=entries.find(i=>i.scope==='interaction'&&i.key===info.id);if(itemId&&!entry)continue;
  const rows=entry?.categories?.[reportSection]||[];const details=el('details',undefined,'report-case');details.id='report-case-'+info.id;
  const summary=el('summary');summary.append(el('strong','用例 '+(index+1)+' · '+info.name),el('span',(ref?'完整参考':rows.length+' 条')+(!info.complete?' · 部分结果':''),'badge'));if(rows.length||ref){const a=el('a','查看明细／依据');a.href='#'+details.id;a.onclick=()=>{details.open=true;};summary.append(a);}details.append(summary);
  if(!entry)details.append(el('p','本用例尚未发布结果，不作为零场景或完整评测。','muted'));
  else if(ref){const holder=app;const temp=el('div');
   const before=holder.childNodes.length;renderGroups(referenceEntry(entry));while(holder.childNodes.length>before)temp.append(holder.childNodes[before]);details.append(temp);
  }else if(rows.length)details.append(reportDetails(entry,rows));else details.append(el('p','此用例无该类已确认场景。','muted'));
  if(entry?.report_excluded?.length){const pending=el('details',undefined,'report-pending');pending.append(el('summary','待核对／未完成（'+entry.report_excluded.length+'）'));for(const r of entry.report_excluded)pending.append(el('p',r.channel+' · '+r.id+' · '+r.reason));details.append(pending);}app.append(details);
 }
 for(const entry of entries.filter(i=>i.scope==='shared_services')){const rows=entry.categories[reportSection];const d=el('details',undefined,'report-case report-shared');d.id='report-shared';const s=el('summary');s.append(el('strong','共用外部服务（跨用例合并）'),el('span',rows.length+' 条，仅计一次','badge'));d.append(s);if(ref){const before=app.childNodes.length;const temp=el('div');renderGroups(referenceEntry(entry));while(app.childNodes.length>before)temp.append(app.childNodes[before]);d.append(temp);}else if(rows.length)d.append(reportDetails(entry,rows));else d.append(el('p','无此类共用服务场景。','muted'));app.append(d);}
}
const originalSaveHTML=document.getElementById('save-html').onclick;
document.getElementById('save-html').onclick=()=>{originalSaveHTML();document.getElementById('save-status').textContent='已生成含修改的 HTML 下载，请保留下载文件，重开可继续审核。';};
render();
"""

TEMPLATE = (
    BASE.replace("业务场景采纳审核", "需求异常场景识别结果")
    .replace("交互级场景", "用例交互")
    .replace("业务采纳审核-已修改.html", "需求异常场景识别结果-已审核.html")
    .replace("业务采纳审核.json", "需求异常场景识别结果-审核反馈.json")
    .replace("业务链路场景", "历史业务链路")
    .replace(
        "</style>",
        r"""
.tabs{flex-wrap:wrap}.report-case{background:white;border:1px solid #dce5f2;border-radius:9px;margin:12px 0;padding:12px 16px}.report-case>summary{display:flex;align-items:center;gap:14px;cursor:pointer;flex-wrap:wrap}.report-case>summary a{margin-left:auto;font-size:12px;color:#3864d9}.report-case[open]>summary{margin-bottom:15px}.report-equation{font-size:13px;color:#617b9d}.report-pending{margin:10px 0;color:#8a713c;font-size:12px}.report-shared{border-color:#a9c4ec}.review-main .reading-width{min-width:760px}
</style>""",
        1,
    )
)
# Override only presentation. The same source dialog, save and decision functions are reused.
TEMPLATE = TEMPLATE.replace(
    "render();\n</script></body></html>", REPORT_JS + "\n</script></body></html>"
)
