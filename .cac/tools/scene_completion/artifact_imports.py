"""Versioned colleague artifacts. Original bytes and derived citations stay local."""
from pathlib import Path
from copy import deepcopy
from threading import RLock
import json,re,time,base64
from .storage import read_json,write_json,fingerprint
from .contracts import schema,validate,PROTOCOL
from .source_documents import normal_projection

LOCK=RLock()
TASKS={'components','api-map','api-parameters','rr-ssd','sr-ssd','fused-ssd','object-operations','business-entities'}
ROOTS={'components':{'components','relations'},'api-map':{'services'},'api-parameters':{'apis'},'rr-ssd':{'interactions'},'sr-ssd':{'interactions'},'fused-ssd':{'interactions','rr_sr_links','pending'},'object-operations':{'objects'},'business-entities':{'entities','pending'}}


def provenance_label(value):
 # Historical stored values stay intact; normalize only their visible label.
 return {'同事产物导入':'已有文件输入','同事产物合并':'已有文件输入（补充合并）'}.get(value,value)


def load(project):
 p=Path(project)/'imports/index.json'
 return read_json(p) if p.exists() else {'version':'artifact-imports-v1','revision':0,'items':{},'history':[]}


def save(project,index):
 index['revision']+=1;write_json(Path(project)/'imports/index.json',index)


def purpose(row):
 if row.get('behavior_product'):return row['behavior_product']['label']
 if row.get('behavior_error'):return '行为建模结果（格式待修正，原流程兜底）'
 if row.get('structure_model'):return row['structure_model']['layer']+'原始文本结构化提取结果'
 kind=row.get('colleague_product',{}).get('format')
 if kind=='api_extraction':return 'API提取结果'
 if kind=='function_tree':return '功能树：业务实体与接口属性'
 return {'test':'测试逆向需求场景结果','RR':'RR原始需求文档','SR':'SR原始设计文档','artifact':'结构化分析结果'}.get(row.get('role'),'待归类')


def view(project,item=None):
 index=load(project)
 if item:
  if item not in index['items']:raise ValueError('未知导入文件')
  row=read_json(Path(project)/index['items'][item]['record'])|{'index_revision':index['revision']}
  usage=read_json(Path(project)/'imports/usage.json') if (Path(project)/'imports/usage.json').exists() else {}
  row['usage']=[v for v in usage.values() if v['file_id']==item]
  meta_path=Path(project)/'project.json'
  if meta_path.exists() and row.get('role') in {'RR','SR','test'}:
   meta=read_json(meta_path);sources=meta.get('sources',{}).get(row['role'],[])
   if any(s.get('path')==row['original'] for s in sources):
    row['status']='source_active'
    tasks_path=Path(project)/'run/workflow_tasks.json'
    tasks=read_json(tasks_path).get('tasks',{}) if tasks_path.exists() else {}
    from .source_documents import read_project_documents
    source_ids={d['source_id'] for d in read_project_documents(Path(project),[s for s in sources if s.get('path')==row['original']],'test' if row['role']=='test' else 'existing')}
    def references(value):
     if isinstance(value,dict):return value.get('source_id') in source_ids or any(references(v) for v in value.values())
     if isinstance(value,list):return any(references(v) for v in value)
     return False
    for key,value in tasks.items():
     output=Path(project)/'run'/value['output_file'] if value.get('output_file') else None
     if output and output.is_file() and references(read_json(output)):
      row['usage'].append({'node':key,'status':value.get('status'),'file_id':item,'source':row['original'],'revision':row['revision']})
    row['source_registered']=True
  for a in row['artifacts']:
   if any(v['artifact_id']==a['id'] and v['revision']==row['revision'] for v in row['usage']):a['status']='active'
  return {**row,'purpose':purpose(row)}
 return {**index,'items':[{**v,'id':k,'purpose':v.get('purpose') or purpose(read_json(Path(project)/v['record']))} for k,v in index['items'].items()]}


def role_hint(name,text):
 name=name.lower()
 if Path(name).suffix.lower()=='.json':
  from .recovered_tests import json_cases
  try:json_cases(text);return 'test'
  except (ValueError,IndexError,RecursionError):pass
 # A recovery/test body is stronger evidence than an arbitrary file name.
 if re.search(r'测试逆向|测试逆向恢复|^\s*[-*]\s+(?:exception|alternative_success|undetermined)〔SC@',text,re.M):return 'test'
 if re.search(r'(^|[_. -])test(?:[_ -]?(?:spec|cases?|scenarios?))?([_. -]|$)|测试|逆向|recovered',name):return 'test'
 from .test_sources import is_test_header,cells
 if any(is_test_header(cells(line)) for line in text.splitlines() if line.lstrip().startswith('|')):return 'test'
 if re.search(r'ssd|系统组成|对象操作|接口映射|接口参数|api[-_ ]?(?:map|parameters)',name):return 'artifact'
 if re.search(r'rr.?spec|系统需求|需求_spec',name):return 'RR'
 if re.search(r'sr.?spec|功能设计|设计_spec',name):return 'SR'
 return 'artifact'


def _infer(value):
 if not isinstance(value,dict):return None
 for task in ('fused-ssd','components','api-map','api-parameters','object-operations'):
  if ROOTS[task]<=set(value):return task
 rows=value.get('interactions')
 if isinstance(rows,list) and rows:
  layers={r.get('layer') for r in rows if isinstance(r,dict)}
  if layers=={'RR'}:return 'rr-ssd'
  if layers=={'SR'}:return 'sr-ssd'
 return None


def _tables(text):
 from .test_sources import cells
 header=None
 for line in text.splitlines():
  if not line.lstrip().startswith('|'):header=None;continue
  parts=cells(line)
  if all(re.fullmatch(r':?-{2,}:?',x.strip()) for x in parts):continue
  if header is None:header=parts;continue
  yield dict(zip(header,parts))


def deterministic(text,name):
 """Return envelopes; free prose is handled by the scoped conversion agent."""
 try:value=json.loads(text)
 except ValueError:
  blocks=re.findall(r'```(?:json)?\s*\n([\s\S]*?)```',text,re.I);value=None
  for block in blocks:
   try:
    candidate=json.loads(block)
    if _infer(candidate) or isinstance(candidate,dict) and candidate.get('task') in TASKS:value=candidate;break
   except ValueError:pass
 if isinstance(value,dict):
  if isinstance(value.get('artifacts'),list):return value['artifacts']
  task=value.get('task') or _infer(value)
  if task in TASKS:
   payload=value.get('payload',value)
   hint=value.get('case_id') or (payload.get('interactions',[{}])[0].get('case_id') if payload.get('interactions') else None)
   return [{'task':task,'case_hint':hint,'coverage':value.get('coverage','complete' if value.get('protocol')==PROTOCOL else 'partial'),'payload':payload}]
 services={}
 for row in _tables(text):
  pick=lambda *keys:next((row[k].strip('` ') for k in keys if row.get(k)),None)
  svc=pick('服务名称','服务','Service');method=pick('HTTP方法','请求方法','方法','method');path=pick('接口地址','路径','path','URL')
  name_=pick('API名称','接口名称','名称','API')
  if svc and (path or name_):
   services.setdefault(svc,[]).append({'id':pick('API编号','接口编号','id') or 'api-'+fingerprint([svc,method,path,name_])[:16],'name':name_ or path,'method':method.upper() if method else None,'address':path,'source_refs':[]})
 if services:return [{'task':'api-map','case_hint':None,'coverage':'partial','payload':{'services':[{'name':k,'interfaces':v,'source_refs':[]} for k,v in services.items()]}}]
 return []


def cited_payload(payload,task,file_id,name):
 """Cite an inspectable normalized JSONL view, never invent RR/SR references."""
 lines=[];sid='import-'+file_id+'-'+fingerprint(payload)[:12]
 def visit(value):
  if isinstance(value,list):return [visit(x) for x in value]
  if not isinstance(value,dict):return deepcopy(value)
  clean={k:visit(v) for k,v in value.items() if k!='source_refs'}
  quote=json.dumps({k:v for k,v in clean.items() if k!='source_refs'},ensure_ascii=False,separators=(',',':'))
  if 'source_refs' in value:
   lines.append({'number':len(lines)+1,'text':quote})
   clean['source_refs']=[{'source_id':sid,'line_start':len(lines),'line_end':len(lines),'quote':quote}]
  return clean
 # Fill required citation containers only, leaving all factual unknowns intact.
 def fill(value,spec):
  if isinstance(value,dict):
   if 'source_refs' in spec.get('properties',{}):value.setdefault('source_refs',[])
   for k,v in value.items():fill(v,spec.get('properties',{}).get(k,{}))
  elif isinstance(value,list):
   for v in value:fill(v,spec.get('items',{}))
 value=deepcopy(payload);fill(value,schema(task));value=visit(value)
 return value,{'source_id':sid,'name':name+' · 规范化事实（原文件可查看）','channel':'normal','lines':lines}


def receive(project,files):
 project=Path(project);out=[]
 from .behavior_imports import format_of as behavior_format,context_for
 batch=[]
 for f in files:
  try:
   raw=base64.b64decode(f['content_base64'],validate=True) if f.get('content_base64') else str(f.get('content','')).encode('utf8')
   if len(raw)>20*1024*1024:continue
   value=json.loads(raw.decode('utf-8-sig'))
   if behavior_format(value):batch.append({'path':f.get('relative_path') or f.get('name',''),'value':value})
  except (ValueError,UnicodeError):pass
 with LOCK:
  index=load(project)
  for f in files:
   name=Path(str(f.get('name','')).replace('\\','/')).name
   if not name or name.startswith('.') or any(x in name.lower() for x in ('.local.','api-key','api_key','credential','token-budget','ledger')) or Path(name).suffix.lower() not in {'.md','.markdown','.json','.xlsx'}:continue
   raw=base64.b64decode(f['content_base64'],validate=True) if f.get('content_base64') else str(f.get('content','')).encode('utf8')
   if len(raw)>20*1024*1024:raise ValueError('导入文件超过20MB，请按章节拆分')
   from .behavior_imports import format_of as behavior_format,compile_product as compile_behavior
   try:behavior_kind=behavior_format(json.loads(raw.decode('utf-8-sig'))) if Path(name).suffix.lower()=='.json' else None
   except (ValueError,UnicodeError):behavior_kind=None
   behavior_context=f.get('behavior_context') or context_for(f.get('relative_path') or name,batch) if behavior_kind else {}
   digest=fingerprint([raw.hex(),behavior_context]) if behavior_kind else fingerprint(raw.hex());iid=digest[:24]
   if iid in index['items']:out.append({'id':iid,'duplicate':True});continue
   folder=project/'imports/files'/iid;folder.mkdir(parents=True,exist_ok=True)
   (folder/'original').mkdir(exist_ok=True)
   (folder/'original'/name).write_bytes(raw)
   text=raw.decode('utf-8-sig') if Path(name).suffix.lower()!='.xlsx' else ''
   role=f.get('role') or role_hint(name,text)
   from .structure_models import compile_model
   structured=compile_model(text,name) if Path(name).suffix.lower()=='.json' else None
   if structured or behavior_kind:role='artifact'
   meta=read_json(project/'project.json') if (project/'project.json').exists() else {'sources':{}}
   bound=[r for r,files in meta['sources'].items() for source in files if (project/source['path']).is_file() and (project/source['path']).read_bytes()==raw]
   if len(set(bound))==1:role=bound[0]
   if role not in {'RR','SR','test','artifact','unknown'}:raise ValueError('未知文件用途')
   positive=normal_projection([{'source_id':'raw','name':name,'lines':[{'number':i,'text':v} for i,v in enumerate(text.splitlines(),1)]}])[0]
   parse_text='\n'.join(v['text'] for v in positive['lines']) if Path(name).suffix.lower() in {'.md','.markdown'} else text
   from .colleague_formats import convert as convert_colleague
   product=convert_colleague(json.loads(text),iid,name) if Path(name).suffix.lower()=='.json' and role=='artifact' and not structured and not behavior_kind else None
   behavior=behavior_error=None
   if behavior_kind:
    try:behavior=compile_behavior(json.loads(text),iid,name,behavior_context)
    except ValueError as e:behavior_error=str(e)
   artifacts=product['artifacts'] if product else deterministic(parse_text,name) if role=='artifact' and not behavior_kind else []
   row={'id':iid,'name':name,'hash':digest,'role':role,'status':'converted' if artifacts else 'needs_conversion' if role=='artifact' else 'source_pending','artifacts':[],'created_at':time.time(),'revision':0,'original':str((folder/'original'/name).relative_to(project)),'history':[]}
   if structured:
    row.update(structure_model=structured,structure_enabled=True,status='converted')
   if product:row.update(colleague_product={k:v for k,v in product.items() if k!='artifacts'},status='converted')
   if behavior:row.update(behavior_product=behavior,behavior_enabled=False,status='converted',relative_path=f.get('relative_path'))
   if behavior_error:row.update(behavior_error=behavior_error,status='invalid_behavior',relative_path=f.get('relative_path'))
   row['recognition']={'role':role,'reason':'正文含明确测试场景/恢复结构' if role=='test' and re.search(r'SC@|测试逆向',text) else '格式结构与文件用途识别','source_file':name,'source_hash':digest}
   if role=='test':
    from .test_sources import preview
    documents=[{'source_id':'import-raw-'+iid,'name':name,'channel':'test','lines':[{'number':i,'text':line} for i,line in enumerate(text.splitlines(),1)]}]
    if Path(name).suffix.lower()=='.xlsx':
     from .test_sources import xlsx_documents
     documents=xlsx_documents(raw,name,iid)
    row['test_preview']=preview(documents)
    row['target_nodes']=['test-inventory','test-case-align','<用例>:test-concerns','<用例>:test-ground-truth','<用例>:concern-evaluation','<用例>:exception-evaluation']
   else:row['target_nodes']=[a['task'] for a in row['artifacts']]
   if bound:row['status']='source_active'
   _targets(row,artifacts,prepared=bool(product))
   row['target_nodes']=(['rr-use-cases' if structured['layer']=='RR' else 'sr-use-cases','<用例>:existing-branches'] if structured else [a['task'] for a in row['artifacts']]) if role=='artifact' else row.get('target_nodes',[])
   row['target_nodes']=list(dict.fromkeys(row['target_nodes']))
   if product and product['format']=='function_tree':row['target_nodes']+=['<用例>:business-crud（提供实体范围）','business-attribute-map（提供属性依据）','<用例>:interaction-enrich（精确字段补充）']
   if behavior:row['target_nodes']=behavior['target_nodes']
   from .artifact_parsers import mermaid_sequences
   row['literal_structure']={'mermaid':mermaid_sequences(parse_text)}
   # A mixed artifact file requires conversion of remaining structures too.
   if role=='artifact' and not structured and not product and (row['literal_structure']['mermaid'] or artifacts and re.search(r'请求参数|数据类型|参数名称|支持的操作|系统组成',parse_text)):
    row['status']='needs_conversion'
   record=str((folder/'record.json').relative_to(project));write_json(project/record,row)
   index['items'][iid]={'name':name,'role':role,'purpose':purpose(row),'status':row['status'],'record':record,'created_at':row['created_at']}
   out.append({'id':iid,'duplicate':False})
  save(project,index)
 return {'received':out,'revision':index['revision']}


def archive(project,row):
 write_json(Path(project)/'imports/versions'/row['id']/(str(row['revision'])+'-'+fingerprint(row)[:12]+'.json'),row)


def _targets(row,artifacts,prepared=False):
 for n,a in enumerate(artifacts):
  if not isinstance(a,dict) or a.get('task') not in TASKS:raise ValueError('导入目标不在支持的正向任务范围')
  if prepared:
   value,doc=deepcopy(a['payload']),deepcopy(a['document'])
   from .source_documents import validate_evidence
   if doc['source_id']!='import-'+row['id']+'-facts-v1' or doc['channel']!='normal':raise ValueError('结构转换的来源身份无效')
   validate_evidence(value,[doc])
  else:value,doc=cited_payload(a.get('payload'),a['task'],row['id']+'-'+str(n),row['name'])
  try:validate(a['task'],value);error=None
  except ValueError as e:error=str(e)
  row['artifacts'].append({'id':row['id']+':'+str(n),'task':a['task'],'case_hint':a.get('case_hint'),'coverage':a.get('coverage','partial'),'payload':value,'document':doc,'status':'needs_confirmation' if a.get('coverage')!='complete' or error else 'candidate','error':error,'accepted_partial':False,'source_layer':a.get('source_layer'),'conversion_source_refs':a.get('source_refs',[])})
  if prepared:row['artifacts'][-1].update(json_locations=a.get('json_locations',[]),coverage_details=a.get('coverage_details',{}),literal_adapter=a.get('literal_adapter'))


def convert(project,iid,client):
 from .contracts import packet
 from .execution_events import EventStore,bind,emit
 project=Path(project);row=view(project,iid)
 if row['status'] not in {'needs_conversion','conversion_failed'}:return row
 path=project/row['original'];text=path.read_text(encoding='utf-8-sig')
 doc={'source_id':'import-raw-'+iid,'name':row['name'],'channel':'normal','lines':[{'number':n,'text':s} for n,s in enumerate(text.splitlines(),1)]}
 # Conversion never consumes the project's G/E/GT or private files. Prose
 # sections labelled tests/exceptions are excluded from positive candidates.
 docs=normal_projection([doc]);chunks=[];chunk=[];size=0
 for line in docs[0]['lines']:
  cost=len(line['text'].encode())
  if cost>32000:raise ValueError('单行过大，请先拆分为可定位段落')
  if size+cost>32000 and chunk:chunks.append(chunk);chunk=[];size=0
  chunk.append(line);size+=cost
 if chunk:chunks.append(chunk)
 artifacts=[];roles=set()
 catalogue=case_catalogue(project)
 try:
  for n,lines in enumerate(chunks):
   p=packet('artifact-convert',{'documents':[{**doc,'lines':lines}],'file_name':row['name'],'case-catalogue':catalogue,'target_schemas':json.dumps({t:schema(t) for t in TASKS},ensure_ascii=False)});p['node_key']='imports:'+iid
   p['skill_text']=(Path(__file__).resolve().parents[2]/'skills/scene-artifact-import/SKILL.md').read_text()
   with bind(EventStore(project/'run'),task_key=p['node_key'],role='modeler',case='shared',attempt=n+1):
    emit('import_conversion_started',file_id=iid,chunk=n+1,total_chunks=len(chunks))
    value=client.agent(p);roles.add(value['source_role'])
    if value['source_role']=='artifact':
     for a in value['artifacts']:
      if len(chunks)>1:a['coverage']='partial'
      artifacts.append(a)
  with LOCK:
   index=load(project);current=read_json(project/index['items'][iid]['record'])
   if current['revision']!=row['revision']:raise ValueError('文件转换期间版本已变化')
   if roles!={'artifact'}:
    current['role']=next(iter(roles)) if len(roles)==1 else 'unknown';artifacts=[]
   archive(project,current)
   current['artifacts']=[]
   _targets(current,artifacts);current.update(status='converted' if artifacts else 'source_pending' if current['role'] in {'RR','SR','test'} else 'unclassified',revision=row['revision']+1)
   current['history'].append({'action':'converted','at':time.time(),'chunks':len(chunks)})
   write_json(project/index['items'][iid]['record'],current);index['items'][iid].update(status=current['status'],role=current['role']);save(project,index)
   return current
 except Exception as e:
  with LOCK:
   index=load(project);current=read_json(project/index['items'][iid]['record']);current.update(status='conversion_failed',error=str(e),revision=current['revision']+1)
   write_json(project/index['items'][iid]['record'],current);index['items'][iid]['status']=current['status'];save(project,index)
  raise


def decide(project,iid,body):
 with LOCK:
  index=load(project);row=view(project,iid)
  if body.get('expected_revision')!=row['revision']:raise ValueError('文件版本已变化，请刷新')
  if body.get('action') in {'enable_behavior','disable_behavior'}:
   if not row.get('behavior_product'):raise ValueError('本文件不是有效行为建模格式')
   if body.get('dry_run'):return {'valid':True,'saved':False}
   archive(project,row)
   if body.get('case_id'):
    row['behavior_product']['case_ids']=list(dict.fromkeys(row['behavior_product']['case_ids']+[body['case_id']]))
   if body['action']=='enable_behavior' and not (row['behavior_product'].get('case_name') or row['behavior_product']['case_ids']):raise ValueError('请先确认行为文件对应的用例')
   row['behavior_enabled']=body['action']=='enable_behavior';row['revision']+=1
   row['history'].append({'action':body['action'],'at':time.time()})
   write_json(Path(project)/index['items'][iid]['record'],row);save(project,index)
   return {'saved':True,'revision':row['revision']}
  if body.get('action') in {'enable_structure','disable_structure'}:
   if not row.get('structure_model'):raise ValueError('本文件不是RR/SR结构模型')
   if body.get('dry_run'):return {'valid':True,'saved':False}
   archive(project,row);row['structure_enabled']=body['action']=='enable_structure';row['revision']+=1
   row['history'].append({'action':body['action'],'at':time.time()})
   write_json(Path(project)/index['items'][iid]['record'],row);save(project,index)
   return {'saved':True,'revision':row['revision']}
  aid=body.get('artifact_id');a=next((a for a in row['artifacts'] if a['id']==aid),None)
  if a is None:raise ValueError('未知目标产物')
  if body.get('action') not in {'accept','reject'}:raise ValueError('请选择接受或拒绝')
  updated=deepcopy(a)
  if 'payload' in body and body['action']=='accept' and body['payload']!=a['payload']:
   updated['payload'],updated['document']=cited_payload(body['payload'],a['task'],iid+'-'+aid.split(':')[-1],row['name'])
   updated.pop('json_locations',None);updated.pop('literal_adapter',None)
  if body.get('case_id'):updated['case_hint']=body['case_id']
  if body.get('coverage') is not None:
   if body['coverage'] not in {'complete','partial'}:raise ValueError('覆盖范围必须明确为完整或部分')
   updated['coverage']=body['coverage']
  if body['action']=='accept':validate(a['task'],updated['payload'])
  updated.update(status='accepted' if body['action']=='accept' else 'rejected',accepted_partial=updated['coverage']!='complete',replacement_approved=bool(body.get('replace')),error=None)
  if body.get('dry_run'):return {'valid':True,'saved':False,'artifact':updated}
  archive(project,row)
  a.update(updated);row['revision']+=1;row['history'].append({'action':body['action'],'artifact_id':aid,'at':time.time(),'note':body.get('note','')})
  write_json(Path(project)/index['items'][iid]['record'],{k:v for k,v in row.items() if k!='version'});save(project,index)
  return {'saved':True,'revision':row['revision']}


def snapshot(project):
 return [read_json(Path(project)/r['record']) for r in load(project)['items'].values()]


def selections(project,task,case=None,frozen=None):
 if task not in TASKS:return []
 out=[]
 for row in snapshot(project) if frozen is None else frozen:
  for a in row['artifacts']:
   if a['task']!=task or a['status'] not in {'candidate','accepted','active'}:continue
   hint=a.get('case_hint')
   if case and resolve_case(project,hint)!=case:continue
   if not case and hint:continue
   if a['coverage']!='complete' and not a['accepted_partial']:continue
   out.append({**a,'file_id':row['id'],'file_revision':row['revision'],'file_name':row['name']})
 return out


def identity(project,task,case=None):
 return fingerprint([{k:a[k] for k in ('id','payload','coverage','file_revision')} for a in selections(project,task,case)]) if task in TASKS else None


def documents(project,task,case=None):return [a['document'] for a in selections(project,task,case)]


def candidate(project,task,case,inputs,existing=None,parts=None):
 from .validation import validate_result
 from .execution_events import emit
 values=[p for p in parts or selections(project,task,case) if p['task']==task]
 if not values:return None
 # Conflicting full artifacts are not resolved by timestamp or filename.
 full=[v for v in values if v['coverage']=='complete']
 def facts(v):
  if isinstance(v,dict):return {k:facts(x) for k,x in v.items() if k!='source_refs'}
  if isinstance(v,list):return [facts(x) for x in v]
  return v
 if len({fingerprint(facts(v['payload'])) for v in full})>1:
  emit('import_blocked',reason='多个完整产物冲突，需选择当前版本');return None
 if not full:return None
 selected=deepcopy(full[-1])
 if task=='api-parameters' and inputs.get('interface'):
  selected['payload']['apis']=[a for a in selected['payload']['apis'] if a['id']==inputs['interface']['id']]
  if not selected['payload']['apis']:return None
 if existing and not selected.get('replacement_approved'):
  emit('import_blocked',reason='已有成功产物，替换需确认');return None
 check=deepcopy(inputs)
 for layer in ('RR','SR'):
  if layer in check:check[layer]+= [v['document'] for v in values]
 check['import-documents']=[v['document'] for v in values]
 try:validate_result(task,selected['payload'],check)
 except ValueError as e:
  emit('import_blocked',file_id=selected['file_id'],reason=str(e));return None
 emit('result_reused',provider='colleague_import',file_id=selected['file_id'],artifact_id=selected['id'])
 return deepcopy(selected['payload']),{'provider':'colleague_import','file_id':selected['file_id'],'artifact_id':selected['id'],'revision':selected['file_revision'],'file_name':selected['file_name']}


def resolve_case(project,hint):
 if not hint:return None
 root=Path(project)/'run';state=read_json(root/'workflow_tasks.json').get('tasks',{}) if (root/'workflow_tasks.json').exists() else {}
 def get(key):
  r=state.get(key,{})
  return read_json(root/r['output_file'])['payload'] if r.get('status')=='passed' and r.get('output_file') else {}
 groups=get('use-case-align').get('groups',[])
 names={c['id']:c['name'] for k in ('rr-use-cases','sr-use-cases') for c in get(k).get('cases',[])}
 hits=[g['id'] for g in groups if hint==g['id'] or hint in g['rr_ids']+g['sr_ids'] or any(hint==names.get(i) for i in g['rr_ids']+g['sr_ids'])]
 return hits[0] if len(hits)==1 else hint if not groups else None


def fragments_for(project,task,case=None,frozen=None):
 tasks=[task]+(['rr-ssd','sr-ssd'] if task=='fused-ssd' else [])
 rows=[a for t in tasks for a in selections(project,t,case,frozen)]
 if task=='fused-ssd' and case:
  for row in rows:
   row['payload']=deepcopy(row['payload'])
   for i in row['payload'].get('interactions',[]):i['case_id']=case
 return rows


def merge(task,generated,parts):
 """Keep imported facts; combine missing records without fuzzy ID guessing."""
 value=deepcopy(generated)
 def union(a,b):
  if a==b or b is None:return deepcopy(a)
  if a is None:return deepcopy(b)
  if isinstance(a,dict) and isinstance(b,dict):
   return {k:union(a.get(k),b.get(k)) for k in a.keys()|b.keys()}
  if isinstance(a,list) and isinstance(b,list):
   return list({fingerprint(x):deepcopy(x) for x in a+b}.values())
  raise ValueError('同一导入身份具有不同字段值，需确认：'+str(a)[:80]+' / '+str(b)[:80])
 def combine(rows,extra,key):
  found={key(r):r for r in rows}
  for r in extra:
   if key(r) in found:
    item=deepcopy(r)
    if {'kind','value','status'}<=item.keys():item['id']=found[key(r)]['id']
    found[key(r)]=union(found[key(r)],item)
   else:found[key(r)]=deepcopy(r)
  return list(found.values())
 for part in parts:
  other=part['payload']
  if task=='api-map':
   for service in other['services']:
    target=next((s for s in value['services'] if s['name']==service['name']),None)
    if target is None:value['services'].append(deepcopy(service));continue
    target['interfaces']=combine(target['interfaces'],service['interfaces'],lambda a:(a.get('method'),a.get('address')) if a.get('address') else ('id',a['id']))
    target['source_refs']=union(target['source_refs'],service['source_refs'])
  elif task=='api-parameters':
   for api in other['apis']:
    target=next((a for a in value['apis'] if a['id']==api['id']),None)
    if target is None:value['apis'].append(deepcopy(api));continue
    for k in ('name','address'):target[k]=union(target.get(k),api.get(k))
    target['source_refs']=union(target['source_refs'],api['source_refs'])
    for param in api['parameters']:
     known=next((p for p in target['parameters'] if (p['name'],p['location'])==(param['name'],param['location'])),None)
     if known is None:target['parameters'].append(deepcopy(param));continue
     for k in ('name','location','default'):known[k]=union(known.get(k),param.get(k))
     if known.get('data_type') is None:known['data_type']=param.get('data_type')
     elif param.get('data_type') is not None and known['data_type']!=param['data_type']:
      known['constraints'].append({'id':'import-type-'+fingerprint([param['name'],param['location'],param['data_type']])[:20],'kind':'type','value':param['data_type'],'status':'explicit','source_refs':param['source_refs']})
     known['required']=True if known.get('required') is True or param.get('required') is True else union(known.get('required'),param.get('required'))
     known['source_refs']=union(known['source_refs'],param['source_refs'])
     known['constraints']=combine(known['constraints'],param['constraints'],lambda c:(c['kind'],fingerprint(c['value']),c['status']))
  elif task=='fused-ssd':
   value['interactions']=combine(value['interactions'],other.get('interactions',[]),lambda x:x['id'])
   if part['task']=='fused-ssd':value['rr_sr_links']=combine(value['rr_sr_links'],other.get('rr_sr_links',[]),lambda x:x['rr_id'])
  elif task=='business-entities':
   from .domain_model import merge_entities
   value=merge_entities([value,other])
  else:
   root=next(iter(ROOTS[task])) if task not in {'components'} else 'components'
   identity_key='name' if task=='object-operations' else 'id'
   value[root]=combine(value[root],other[root],lambda x:x[identity_key])
   if task=='components':value['relations']=union(value.get('relations',[]),other.get('relations',[]))
 return value


def record_use(project,key,proof):
 if proof.get('provider') not in {'colleague_import','colleague_structure'} and not proof.get('import_sources') and not proof.get('input_sources'):return
 with LOCK:
  path=Path(project)/'imports/usage.json';data=read_json(path) if path.exists() else {}
  if proof.get('provider')=='colleague_structure':
   for source in proof.get('source_files',[]):
    data[key+'::'+source['file_id']]={'node':key,**proof,**source,'artifact_id':'structure-model','at':time.time()}
  elif proof.get('provider')=='colleague_import':data[key]={'node':key,**proof,'at':time.time()}
  for source in proof.get('import_sources',[]):
   data[key+'::'+source['artifact_id']]={'node':key,'provider':'colleague_partial',**source,'at':time.time()}
  for source in proof.get('input_sources',[]):
   data[key+'::behavior::'+source['file_id']]={'node':key,'provider':'behavior_input','mode':'basis',**source,'at':time.time()}
  write_json(path,data)


def case_catalogue(project):
 root=Path(project)/'run';state=read_json(root/'workflow_tasks.json').get('tasks',{}) if (root/'workflow_tasks.json').exists() else {}
 out={'RR':[],'SR':[],'groups':[]}
 for key,field,target in [('rr-use-cases','cases','RR'),('sr-use-cases','cases','SR'),('use-case-align','groups','groups')]:
  record=state.get(key,{})
  if record.get('status')!='passed' or not record.get('output_file'):continue
  payload=read_json(root/record['output_file'])['payload']
  keys=('id','name') if field=='cases' else ('id','rr_ids','sr_ids','status')
  out[target]=[{k:v for k,v in item.items() if k in keys} for item in payload[field]]
 return out
