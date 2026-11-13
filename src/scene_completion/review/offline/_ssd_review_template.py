"""Self-contained offline review UI; embedded as package code for wheel installs."""

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SSD 差异校对</title>
<style>
:root{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;color:#193047;background:#f3f6f8;font-size:15px}*{box-sizing:border-box}body{margin:0}header{position:sticky;top:0;background:#fff;border-bottom:1px solid #d6e0e8;padding:16px 24px;z-index:2;display:flex;gap:12px;align-items:center;flex-wrap:wrap}h1{font-size:22px;margin:0 auto 0 0}button,select{font:inherit;border:1px solid #aebdca;border-radius:6px;background:#fff;padding:7px 10px;color:#193047;cursor:pointer}button.primary{background:#1b5f8f;color:white;border-color:#1b5f8f}button:hover{filter:brightness(.96)}main{max-width:1500px;margin:24px auto;padding:0 20px}.muted{color:#607588;font-size:13px}.status{margin:8px 0;color:#256447}.case{margin:25px 0}.case h2{font-size:20px}.row{background:white;border:1px solid #d6e0e8;border-radius:10px;margin:18px 0;overflow:hidden}.row-head{padding:16px 18px;background:#eaf1f6}.row-head h3{margin:0 0 7px;font-size:16px}.reason{color:#8c4a13;white-space:pre-wrap;margin-top:8px}.channels{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}.channel{padding:16px;border-right:1px solid #e1e8ee}.channel:last-child{border:0}.channel h4{margin:0 0 12px}.record{border-top:1px solid #e1e8ee;padding-top:12px;margin-top:12px}.record:first-of-type{border-top:0;padding-top:0}.record-id{overflow-wrap:anywhere;font-size:11px;color:#607588}label{display:block;margin:8px 0;font-size:13px}input,textarea{display:block;width:100%;font:inherit;padding:8px;border:1px solid #bac9d5;border-radius:5px;background:#fff;line-height:1.5}textarea{resize:vertical;min-height:65px}.sources{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.sources button{font-size:12px}.judgments{padding:14px 18px;border-top:1px solid #d6e0e8}.judgment{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}.judgment span{font-size:12px}.judgment input{flex:1;min-width:180px}.judgment select{font-size:13px}.empty{background:#fff;padding:25px;border:1px dashed #b5c5d1;border-radius:8px}dialog{width:min(1100px,94vw);max-height:88vh;border:1px solid #bac9d5;border-radius:10px;padding:0;box-shadow:0 15px 80px #112b4455}dialog::backdrop{background:#152c4566}.dialog-bar{position:sticky;top:0;background:white;border-bottom:1px solid #d6e0e8;padding:12px 18px;display:flex;align-items:center;gap:12px;z-index:1}.dialog-bar strong{flex:1}.document{padding:22px 30px;line-height:1.75;overflow-wrap:anywhere}.document h1{font-size:24px}.document h2{font-size:21px}.document h3{font-size:18px}.document p{margin:10px 0}.document table{border-collapse:collapse;width:100%;margin:15px 0}.document th,.document td{border:1px solid #ccd7e0;padding:7px 10px;text-align:left}.document th{background:#edf2f6}.document pre{white-space:pre-wrap;background:#f0f3f6;padding:14px;border-radius:5px}.document code{background:#edf1f5;padding:2px 4px;border-radius:3px}.document blockquote{border-left:4px solid #b1c4d4;padding-left:15px;margin:14px 0;color:#405d72}.source-highlight{background:#fff0aa!important;box-shadow:inset 3px 0 #ce9e14}.line{display:block}.source-meta{font-size:13px;color:#607588;margin:0 0 16px}.quote{white-space:pre-wrap;margin:12px 0;padding:12px;background:#fff6cd;border-left:3px solid #cba337}@media(max-width:900px){.channels{grid-template-columns:1fr}.channel{border-right:0;border-bottom:1px solid #e1e8ee}header{padding:12px}main{padding:0 12px}}
</style></head><body>
<header><h1>SSD 差异校对</h1><button id="save-html" class="primary">保存含修改的 HTML</button><button id="save-json">导出校对 JSON</button></header>
<main><p class="muted">仅展示导出时存在差异的记录。点击出处查看原文；修改后请保存 HTML 或导出 JSON，再回到工作台预览并应用。此页面可离线使用。</p><p id="save-status" class="status" role="status"></p><div id="app"></div></main>
<dialog id="source-dialog"><div class="dialog-bar"><strong id="source-title"></strong><button id="source-close">关闭</button></div><article class="document" id="source-content"></article></dialog>
<script type="application/json" id="ssd-review-data">__SSD_REVIEW_JSON__</script>
<script>
'use strict';
const state=JSON.parse(document.getElementById('ssd-review-data').textContent);
const channelNames={G:'方法生成',E:'原文已有',GT:'测试逆向'};
const targetNames={sender:'发送方',data:'数据',receiver:'接收方'};
const app=document.getElementById('app');
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function changed(){document.getElementById('save-status').textContent='有未导出的修改，请保存 HTML 或导出 JSON。';}
function esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function inline(text){return esc(text).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/\*([^*]+)\*/g,'<em>$1</em>');}
function markdown(text,start,end){
 const lines=String(text).split('\n'),out=[];let i=0;
 const hit=n=>n>=start&&n<=end;
 const attrs=n=>' data-line="'+n+'"'+(hit(n)?' class="source-highlight"':'');
 const span=(s,n)=>'<span class="line'+(hit(n)?' source-highlight':'')+'" data-line="'+n+'">'+inline(s)+'</span>';
 while(i<lines.length){const s=lines[i],n=i+1;
  if(/^\s*```/.test(s)){const b=[];i++;while(i<lines.length&&!/^\s*```/.test(lines[i])){b.push('<span class="line'+(hit(i+1)?' source-highlight':'')+'" data-line="'+(i+1)+'">'+esc(lines[i])+'</span>');i++;}out.push('<pre><code>'+b.join('')+'</code></pre>');i++;continue;}
  if(!s.trim()){i++;continue;}
  const heading=s.match(/^(#{1,6})\s+(.*)$/);if(heading){out.push('<h'+heading[1].length+attrs(n)+'>'+inline(heading[2])+'</h'+heading[1].length+'>');i++;continue;}
  if(i+1<lines.length&&s.includes('|')&&/^\s*\|?\s*:?-{3,}.*\|/.test(lines[i+1])){const cells=x=>x.trim().replace(/^\||\|$/g,'').split('|');out.push('<table><thead><tr'+attrs(n)+'>'+cells(s).map(c=>'<th>'+inline(c.trim())+'</th>').join('')+'</tr></thead><tbody>');i+=2;while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){out.push('<tr'+attrs(i+1)+'>'+cells(lines[i]).map(c=>'<td>'+inline(c.trim())+'</td>').join('')+'</tr>');i++;}out.push('</tbody></table>');continue;}
  if(/^\s*[-*+]\s/.test(s)||/^\s*\d+[.)]\s/.test(s)){const ordered=/^\s*\d+[.)]\s/.test(s),tag=ordered?'ol':'ul',pat=ordered?/^\s*\d+[.)]\s+/:/^\s*[-*+]\s+/;out.push('<'+tag+'>');while(i<lines.length&&pat.test(lines[i])){out.push('<li'+attrs(i+1)+'>'+inline(lines[i].replace(pat,''))+'</li>');i++;}out.push('</'+tag+'>');continue;}
  if(/^>\s?/.test(s)){out.push('<blockquote'+attrs(n)+'>'+inline(s.replace(/^>\s?/,''))+'</blockquote>');i++;continue;}
  if(/^\s*(---+|___+)\s*$/.test(s)){out.push('<hr>');i++;continue;}
  out.push('<p>'+span(s,n)+'</p>');i++;
 }
 return out.join('');
}
function showSource(entry,ref){
 const docs=entry.bundle.documents||[],doc=docs.find(d=>d.id===ref.document_id);
 const content=document.getElementById('source-content');content.replaceChildren();
 document.getElementById('source-title').textContent=(doc?doc.name:ref.document_id||'来源')+' · '+(ref.start_line||'?')+'–'+(ref.end_line||ref.start_line||'?');
 content.append(el('p',ref.json_pointer||'原文行号高亮','source-meta'));
 if(ref.quote)content.append(el('div',ref.quote,'quote'));
 const body=el('div');
 if(doc){body.innerHTML=markdown(doc.content,Number(ref.start_line||0),Number(ref.end_line||ref.start_line||0));}
 else body.textContent='此出处的原始文档未随本次导出提供；可按上方引用回到工作台查找。';
 content.append(body);document.getElementById('source-dialog').showModal();
 requestAnimationFrame(()=>{const line=body.querySelector('.source-highlight');if(line)line.scrollIntoView({block:'center'});});
}
document.getElementById('source-close').onclick=()=>document.getElementById('source-dialog').close();
function sources(entry,record){const wrap=el('div',undefined,'sources');(record.source_refs||[]).forEach((ref,i)=>{const doc=(entry.bundle.documents||[]).find(d=>d.id===ref.document_id);const b=el('button',(doc?doc.name:ref.document_id||'出处')+(ref.start_line?' L'+ref.start_line:''));b.type='button';b.onclick=()=>showSource(entry,ref);wrap.append(b);});if(!(record.source_refs||[]).length)wrap.append(el('span','无直接出处','muted'));return wrap;}
function field(parent,title,record,key,multiline=true){const label=el('label',title),control=el(multiline?'textarea':'input');control.value=record[key]||'';control.oninput=()=>{record[key]=control.value;changed();};label.append(control);parent.append(label);}
function records(entry,row,channel){const name=row.level==='concern'?'concerns':'scenarios';const ids=new Set((row.cells[channel]||[]).map(r=>r.id));const data=entry.bundle.channels[channel];return[...(data[name]||[]),...(row.level==='scenario'?(data.pending||[]):[])].filter(r=>ids.has(r.id));}
function pick(parent,title,values,current,change){const l=el('label',title),s=el('select');for(const[v,t]of[['','请选择'],...values]){const o=el('option',t);o.value=v;s.append(o);}s.value=current||'';s.onchange=()=>{change(s.value);changed();};l.append(s);parent.append(l);return s;}
function pendingEditor(entry,row,channel,record,parent){
 const data=entry.bundle.channels[channel],steps=entry.bundle.steps||[],definitions=entry.bundle.registry?.definitions||{};
 const bindings=el('div');parent.append(bindings);
 pick(bindings,'归属交互',steps.map(s=>[s.id,s.id+' '+(s.sender?.name||'')+' → '+(s.receiver?.name||'')]),record.step_id,v=>{record.step_id=v;record.field_id=null;render();});
 pick(bindings,'交互对象',Object.entries(targetNames),record.target,v=>{record.target=v;render();});
 const step=steps.find(s=>s.id===record.step_id);
 if(record.target==='data')pick(bindings,'字段（整体数据可留空）',(step?.data||[]).map(f=>[f.id,f.name]),record.field_id,v=>{record.field_id=v||null;});
 const options=Object.entries(definitions).map(([key,value])=>[key,value.label+' · '+key]);
 if(!options.length&&row.key)options.push([row.key,row.key]);
 pick(bindings,'关注点分类',options,record.key,v=>{record.key=v;});
 const b=el('button','确认为异常');b.onclick=()=>{
  if(!steps.some(s=>s.id===record.step_id)||!targetNames[record.target]||!record.key||!record.condition?.trim()||!record.expected?.trim()){window.alert('请先补齐交互、对象、关注点分类、触发条件和预期结果。');return;}
  let concern=data.concerns.find(c=>c.step_id===record.step_id&&c.target===record.target&&c.key===record.key&&(c.field_id||null)===(record.field_id||null));
  if(!concern){concern={id:'manual-concern-'+record.id,step_id:record.step_id,target:record.target,key:record.key,label:definitions[record.key]?.label||record.key,condition:record.condition,field_id:record.field_id||null,status:'active',source_refs:record.source_refs||[]};data.concerns.push(concern);}
  else concern.status='active';
  record.concern_ids=[concern.id];record.status='active';delete record.binding_issue;
  data.pending=data.pending.filter(p=>p.id!==record.id);data.scenarios.push(record);
  row.step_id=record.step_id;row.target=record.target;row.key=record.key;row.field_id=record.field_id;
  changed();render();
 };bindings.append(b);
}
function newRecord(entry,row,channel){
 const id='manual-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9);
 const record={id,step_id:row.step_id,target:row.target,key:row.key,field_id:row.field_id||null,condition:'',status:'active',source_refs:[]};
 if(row.level==='concern')record.label=row.key;else{const data=entry.bundle.channels[channel];let concern=data.concerns.find(c=>c.step_id===row.step_id&&c.target===row.target&&c.key===row.key&&(c.field_id||null)===(row.field_id||null));if(!concern){concern={...record,id:'concern-'+id,label:entry.bundle.registry?.definitions?.[row.key]?.label||row.key};data.concerns.push(concern);}record.concern_ids=[concern.id];record.expected='';}
 const collection=row.level==='concern'?'concerns':'scenarios';entry.bundle.channels[channel][collection].push(record);row.cells[channel].push(record);changed();render();
}
function judgments(entry,row,parent){
 const wrap=el('div',undefined,'judgments');wrap.append(el('strong','匹配判断与校对意见'));
 for(const [pair,left,right]of[['G_E','G','E'],['GT_G','GT','G'],['GT_E','GT','E']]){
  for(const a of records(entry,row,left))for(const b of records(entry,row,right)){
   const decisions=entry.bundle.decisions||[];
   let decision=decisions.find(d=>d.level===row.level&&d.pair===pair&&d.left_id===a.id&&d.right_id===b.id);
   const d=el('div',undefined,'judgment');d.append(el('span',channelNames[left]+' ↔ '+channelNames[right]+' · '+a.id+' / '+b.id));
   const select=el('select');[['','保留当前判断'],['full','一致'],['partial','部分一致'],['none','不匹配']].forEach(([value,text])=>{const o=el('option',text);o.value=value;select.append(o);});select.value=decision?.status||'';
   const reason=el('input');reason.placeholder='判断理由';reason.value=decision?.reason||'';
   function save(){if(!select.value)return;if(!decision){decision={id:'manual-'+row.id+'-'+pair+'-'+a.id+'-'+b.id,level:row.level,pair,left_id:a.id,right_id:b.id};decisions.push(decision);entry.bundle.decisions=decisions;}decision.status=select.value;decision.reason=reason.value;decision.origin='manual';changed();}
   select.onchange=save;reason.oninput=save;d.append(select,reason);wrap.append(d);
  }
 }
 if(row.level==='scenario'&&row.key){
  const details=el('details');details.append(el('summary','关联同一交互关注点下的其他场景'));
  for(const[pair,left,right]of[['G_E','G','E'],['GT_G','GT','G'],['GT_E','GT','E']]){
   const compatible=r=>r.status==='active'&&r.step_id===row.step_id&&r.target===row.target&&r.key===row.key&&(r.field_id||null)===(row.field_id||null);
   const a=(entry.bundle.channels[left].scenarios||[]).filter(compatible),b=(entry.bundle.channels[right].scenarios||[]).filter(compatible);
   if(!a.length||!b.length)continue;
   const box=el('div',undefined,'record'),draft={left:records(entry,row,left)[0]?.id,right:records(entry,row,right)[0]?.id,status:'',reason:''};
   pick(box,channelNames[left],a.map(r=>[r.id,r.condition+' · '+r.id]),draft.left,v=>{draft.left=v;});
   pick(box,channelNames[right],b.map(r=>[r.id,r.condition+' · '+r.id]),draft.right,v=>{draft.right=v;});
   pick(box,'判断',[['full','一致'],['partial','部分一致'],['none','不匹配']],'',v=>{draft.status=v;});field(box,'判断理由',draft,'reason');
   const button=el('button','保存此配对判断');button.onclick=()=>{if(!draft.left||!draft.right||!draft.status){window.alert('请选择两方场景及匹配判断。');return;}const decisions=entry.bundle.decisions||(entry.bundle.decisions=[]);let d=decisions.find(d=>d.level==='scenario'&&d.pair===pair&&d.left_id===draft.left&&d.right_id===draft.right);if(!d){d={id:'manual-scenario-'+pair+'-'+draft.left+'-'+draft.right,level:'scenario',pair,left_id:draft.left,right_id:draft.right};decisions.push(d);}d.status=draft.status;d.reason=draft.reason;d.origin='manual';changed();button.textContent='已保存此配对判断';};box.append(button);details.append(box);
  }
  wrap.append(details);
 }
 const notes=entry.bundle.review_notes||[];
 let note=notes.find(n=>n.row_id===row.id&&n.level===row.level);
 const label=el('label','此行校对意见'),input=el('textarea');input.value=note?.note||'';
 input.oninput=()=>{if(!note){note={row_id:row.id,level:row.level,note:''};notes.push(note);entry.bundle.review_notes=notes;}note.note=input.value;changed();};label.append(input);wrap.append(label);parent.append(wrap);
}
function render(){
 app.replaceChildren();
 if(!state.cases.length){app.append(el('div','所选范围没有需要校对的差异记录。','empty'));return;}
 for(const entry of state.cases){const section=el('section',undefined,'case');section.append(el('h2',entry.name+' · '+entry.case_id),el('p','导出版本：'+entry.base_revision+' · '+entry.rows.length+' 行差异','muted'));
  for(const row of entry.rows){const card=el('section',undefined,'row'),head=el('div',undefined,'row-head'),step=(entry.bundle.steps||[]).find(s=>s.id===row.step_id);
   head.append(el('h3',(row.level==='concern'?'关注点':'场景')+' · '+row.key+' · '+(targetNames[row.target]||row.target)+(row.field_id?' · '+row.field_id:'')));
   head.append(el('div',step?step.id+'  '+(step.sender?.name||'')+' → '+(step.receiver?.name||'')+'  '+(step.operation?.name||''):row.step_id,'muted'));
   head.append(el('div',row.reason||'三方记录存在差异','reason'));if(step)head.append(sources(entry,step));card.append(head);
   const grid=el('div',undefined,'channels');
   for(const channel of ['E','G','GT']){const col=el('div',undefined,'channel');col.append(el('h4',channelNames[channel]));const items=records(entry,row,channel);
    if(!items.length)col.append(el('p','此方暂无对应记录','muted'));
    for(const record of items){const block=el('div',undefined,'record');block.append(el('div',record.id,'record-id'));if(row.level==='concern')field(block,'关注点名称',record,'label',false);field(block,'触发条件／内容',record,'condition');if(row.level==='scenario')field(block,'预期结果',record,'expected');
     if((entry.bundle.channels[channel].pending||[]).some(r=>r.id===record.id)){block.append(el('p',record.reason||'待确认：补齐定位与分类后可确认为异常。','muted'));pendingEditor(entry,row,channel,record,block);}
     else{const l=el('label','记录状态'),select=el('select');[['active','参与匹配'],['pending','待修正'],['unbound','未绑定']].forEach(([v,t])=>{const o=el('option',t);o.value=v;select.append(o);});select.value=record.status||'active';select.onchange=()=>{record.status=select.value;changed();};l.append(select);block.append(l);}
     block.append(sources(entry,record));col.append(block);
    }
    const add=el('button','＋ 补充记录');add.onclick=()=>newRecord(entry,row,channel);col.append(add);grid.append(col);
   }
   card.append(grid);judgments(entry,row,card);section.append(card);
  }
  app.append(section);
 }
}
function safeJSON(value){return JSON.stringify(value).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');}
function download(content,type,name){const url=URL.createObjectURL(new Blob([content],{type})),a=el('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById('save-status').textContent='已导出，请使用下载的文件继续校对或回导工作台。';}
document.getElementById('save-json').onclick=()=>download(JSON.stringify(state,null,2),'application/json;charset=utf-8','SSD差异校对.json');
document.getElementById('save-html').onclick=()=>{const clone=document.documentElement.cloneNode(true);clone.querySelector('#ssd-review-data').textContent=safeJSON(state);clone.querySelector('#app').replaceChildren();clone.querySelector('#save-status').textContent='';clone.querySelector('#source-dialog').removeAttribute('open');clone.querySelector('#source-content').replaceChildren();download('<!doctype html>\n'+clone.outerHTML,'text/html;charset=utf-8','SSD差异校对-已修改.html');};
render();
</script></body></html>"""
