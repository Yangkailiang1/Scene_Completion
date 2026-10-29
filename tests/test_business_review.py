"""Offline, cross-directory business handoff and two-layer human GT checks."""
from pathlib import Path
from copy import deepcopy
import io,json,zipfile,sqlite3
import pytest
from fastapi.testclient import TestClient
from scene_completion.workbench import create_app
from scene_completion.storage import read_json,write_json,fingerprint
from scene_completion.contracts import PROTOCOL,packet
from scene_completion.review_questions import report,answer,impact,apply_answers,materials
from scene_completion.project_review import pending_items,pending_view
from scene_completion.review_handoff import project_archive,export_feedback,import_feedback,source_documents,source_view,windows_package
from scene_completion.pattern_settings import feedback,history
from scene_completion.business_truth import snapshot
from scene_completion.concern_alignment import compare
from scene_completion.exception_comparison import compare_report
from scene_completion.recommendation import rank,evaluate
from tests.test_scenario_patterns import positive,applicability,accepted
from tests.test_model_accounts_cli import source,FakeAPI
from scene_completion.workbench_cli import main


def project(tmp_path):
 root=tmp_path/'developer';client=TestClient(create_app(root));rid=client.post('/api/projects',json=source()).json()['id'];p=root/rid
 doc=source_documents(p)[0];ref={'source_id':doc['source_id'],'line_start':1,'line_end':1,'quote':doc['lines'][0]['text']}
 outputs={'C:normal-rules--part-a':('normal-rules',{'rules':[],'pending':[{'interaction_id':'req','reason':'categoryId有效性具体规则未知','source_refs':[ref]}]}),'C:later':('enriched-view',{}),'api-map':('api-map',{'services':[]})}
 nodes=[];state={}
 for key,(stage,payload) in outputs.items():
  file='task_outputs/'+fingerprint(key)+'.json';value={'protocol':PROTOCOL,'task':stage,'payload':payload,'metadata':{}}
  write_json(p/'run'/file,value);state[key]={'status':'passed','case':'C' if key.startswith('C:') else 'shared','stage':stage,'output_file':file,'output_hash':fingerprint(value),'identity':fingerprint(key)}
  nodes.append({'id':key,'stage':stage,'case':state[key]['case'],'role':'modeler','deps':['C:normal-rules--part-a'] if key=='C:later' else [],'expected_files':[]})
 write_json(p/'run/workflow_tasks.json',{'tasks':state});write_json(p/'run/workflow_graph.json',{'nodes':nodes});write_json(p/'run/run_manifest.json',{'protocol':PROTOCOL,'complete':True})
 return client,rid,p


def first(p):return next(i for i in pending_items(p) if i['origins']==['C:normal-rules--part-a'])

def test_missing_rule_asks_for_rule_not_exception_and_answers_do_not_execute(tmp_path):
 client,rid,p=project(tmp_path);q=first(p);assert q['question_type']=='rule_completion'
 assert '校验' in q['required_answer'] and 'anomaly' not in q['answer_spec']['choices']
 baseline=(p/'run/workflow_tasks.json').read_bytes()
 body={'choice':'provide_rule','answer':'分类必须存在且启用，由商城入口校验。','reviewer':'业务甲','revision':0}
 r=client.post(f'/api/projects/{rid}/pending/{q["id"]}',json=body);assert r.status_code==200,r.text
 assert materials(p,q['origins'][0])==[] and (p/'run/workflow_tasks.json').read_bytes()==baseline
 plan=impact(p);assert plan['roots']==q['origins'] and set(plan['affected'])=={'C:normal-rules--part-a','C:later'}
 apply_answers(p,plan['plan_id']);docs=materials(p,q['origins'][0]);assert docs and docs[0]['channel']=='normal'
 assert '分类必须存在且启用' in str(docs) and not materials(p,'api-map')
 assert impact(p)['roots']==[]
 assert client.post(f'/api/projects/{rid}/pending/{q["id"]}',json=body).status_code==400
 assert client.get(f'/api/projects/{rid}/pending/{q["id"]}/history').json()['items'][0]['reviewer']=='业务甲'
 withdraw={**body,'choice':'withdraw','revision':1}
 assert client.post(f'/api/projects/{rid}/pending/{q["id"]}',json=withdraw).status_code==200
 plan=impact(p);assert plan['roots'];apply_answers(p,plan['plan_id']);assert not materials(p,q['origins'][0])


def test_unknown_and_technical_are_not_fabricated_exceptions(tmp_path):
 client,rid,p=project(tmp_path);q=first(p)
 assert client.post(f'/api/projects/{rid}/pending/{q["id"]}',json={'choice':'anomaly','answer':'yes','reviewer':'A','revision':0}).status_code==400
 answer(p,q,{'choice':'needs_info','answer':'暂时无法确认','reviewer':'A','revision':0})
 assert not impact(p)['roots'] and not materials(p,q['origins'][0])
 assert client.get(f'/api/projects/{rid}/execution-status').json()['unresolved_questions']>0
 with pytest.raises(ValueError):report(p,q['origins'][0],'normal-rules','C',{'question':'q','required_answer':'d','source_refs':[{'source_id':'fake','line_start':9,'line_end':9,'quote':'fake'}]},inputs={'normal-documents':source_documents(p)})


def test_nonblocking_questions_are_parallel_safe_and_preserve_source_channels(tmp_path):
 from concurrent.futures import ThreadPoolExecutor
 client,rid,p=project(tmp_path)
 def add(n):return report(p,'api-map','api-map','shared',{'question':f'未知{n}','required_answer':'请确认','question_type':'general_clarification'})
 with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(add,range(12)))
 stored=read_json(p/'business_questions.json')['items'];assert len(stored)==12
 assert all(r['nonblocking'] for r in stored.values())
 # A business response from inverse E is not legal positive-task evidence.
 doc={'source_id':'business-x','name':'answer','channel':'existing','review_item_id':'x','review_revision':1,'lines':[{'number':1,'text':'E side answer'}]}
 with pytest.raises(ValueError,match='独立通道'):packet('api-map',{'SR':[],'review-documents':[doc]})


def test_handoff_roundtrip_offline_source_ids_feedback_and_no_automatic_run(tmp_path):
 client,rid,p=project(tmp_path);q=first(p)
 write_json(p/'model.local.json',{'api_key':'DO_NOT_SHIP','agent_model':'private'})
 (p/'run/agent_traces').mkdir();write_json(p/'run/agent_traces/private.json',{'private':'THOUGHT'})
 from scene_completion.node_conversations import Conversations
 conv=Conversations(p/'run');conv.append('api-map','assistant','THOUGHT')
 blob,snap=project_archive(p)
 business_root=tmp_path/'different Windows path';business=business_root/rid;business.mkdir(parents=True)
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  assert not any('model.local' in n or 'agent_traces' in n for n in z.namelist());assert b'DO_NOT_SHIP' not in b''.join(z.read(n) for n in z.namelist())
  z.extractall(business)
 write_json(business_root/'.review-mode.json',{'review_only':True})
 ui=TestClient(create_app(business_root));assert ui.get(f'/api/projects/{rid}').json()['review_only']
 for endpoint in ('run','rerun-node','config','feedback/import'):
  assert ui.post(f'/api/projects/{rid}/{endpoint}',json={}).status_code==403
 assert ui.put(f'/api/projects/{rid}/config',json={}).status_code==403
 ref=q['source_refs'][0];original=ui.get(f'/api/projects/{rid}/sources/{ref["source_id"]}',params={'start':1,'end':1}).json();assert original['lines'][0]['text']==ref['quote']
 r=ui.post(f'/api/projects/{rid}/pending/{q["id"]}',json={'revision':0,'reviewer':'离线业务','choice':'provide_rule','answer':'分类必须存在且启用。'});assert r.status_code==200,r.text
 result=ui.get(f'/api/projects/{rid}/feedback/export');assert result.status_code==200,result.text
 feedback_doc=result.json();before=(p/'run/workflow_tasks.json').read_bytes()
 preview=import_feedback(p,feedback_doc,dry_run=True);assert preview['ready_count']==1 and not preview['conflicts'] and not (p/'pending_decisions.json').exists()
 applied=import_feedback(p,feedback_doc,dry_run=False);assert applied['saved'] and applied['impact']['roots']==q['origins']
 assert (p/'run/workflow_tasks.json').read_bytes()==before and not materials(p,q['origins'][0])
 assert import_feedback(p,feedback_doc,dry_run=False)['duplicate']
 assert b'THOUGHT' not in (business/'run/execution_events.sqlite3').read_bytes()


def test_feedback_conflicts_and_tampering_do_not_overwrite(tmp_path):
 _,_,p=project(tmp_path);q=first(p);blob,snap=project_archive(p)
 b=tmp_path/'business';b.mkdir()
 with zipfile.ZipFile(io.BytesIO(blob)) as z:z.extractall(b)
 answer(b,first(b),{'choice':'provide_rule','answer':'业务回答','reviewer':'B','revision':0})
 doc=export_feedback(b)
 answer(p,q,{'choice':'not_required','answer':'研发已确认无需校验','reviewer':'D','revision':0})
 before=(p/'pending_decisions.json').read_bytes();assert import_feedback(p,doc)['conflicts']
 with pytest.raises(ValueError,match='冲突'):import_feedback(p,doc,dry_run=False)
 assert before==(p/'pending_decisions.json').read_bytes()
 bad=deepcopy(doc);bad['answers'][0]['answer']='tamper'
 with pytest.raises(ValueError,match='哈希'):import_feedback(p,bad)


def scoring_project(tmp_path):
 _,rid,p=project(tmp_path);x=positive();matrix=applicability(x);g=accepted(matrix);q=rank(g,matrix,case_id='C',run_id='frozen-run');r=compare_report(g,[],[],[],[],[])
 c=compare(x['concern-match'],{'matches':[]},{'matches':[]});r['concern_level']=c;r['metrics'].update(c['metrics']);r=evaluate(r,q)
 state=read_json(p/'run/workflow_tasks.json');graph=read_json(p/'run/workflow_graph.json')
 for stage,value in [('exception-evaluation',r),('concern-evaluation',c),('gap-recommend',q),('exception-generate',{'scenarios':g}),('missing-report',r)]:
  key='C:'+stage;file='task_outputs/'+fingerprint(key)+'.json';row={'protocol':PROTOCOL,'task':stage,'payload':value}
  write_json(p/'run'/file,row);state['tasks'][key]={'status':'passed','case':'C','stage':stage,'output_file':file,'output_hash':fingerprint(row),'identity':fingerprint(key)};graph['nodes'].append({'id':key,'stage':stage,'case':'C','deps':[]})
 write_json(p/'run/workflow_tasks.json',state);write_json(p/'run/workflow_graph.json',graph)
 return rid,p,q,g,c


def test_adoption_updates_human_gt_two_layers_and_retraction_preserves_baseline(tmp_path):
 rid,p,q,g,c=scoring_project(tmp_path);base=(p/'run/workflow_tasks.json').read_bytes();before=snapshot(p,'C');assert before['evaluation']['GT']==[]
 s=q['Q'][0];body={'revision':0,'case_id':'C','settings_hash':q['settings_hash'],'scenario_id':s['id'],'choice':'adopt','reviewer':'业务甲','note':'确认为应覆盖异常'}
 feedback(p,body,q);after=snapshot(p,'C');assert len(after['added'])==1 and after['evaluation']['recommendation_comparison']['recommended']['matched']==1
 assert set(s['concern_binding_ids'])<={m['binding_id'] for m in after['evaluation']['concern_level']['GT_c']}
 assert after['evaluation']['M']==before['evaluation']['M'] and (p/'run/workflow_tasks.json').read_bytes()==base
 feedback(p,{**body,'revision':1,'choice':'withdraw'},q);retracted=snapshot(p,'C');assert not retracted['added'] and not retracted['evaluation']['GT']
 assert (p/'business_truth_versions'/(after['version']+'.json')).exists()


def test_human_gt_duplicate_reuses_baseline_and_never_counts_twice(tmp_path):
 _,p,q,g,c=scoring_project(tmp_path);s=q['Q'][0];st=read_json(p/'run/workflow_tasks.json')['tasks']['C:exception-evaluation'];file=p/'run'/st['output_file'];raw=read_json(file);t=deepcopy(s);t['id']='existing-truth';t['source_status']='explicit';raw['payload']['GT']=[t];raw['payload']['full_candidate_pairs_GT_G']=[{'left_id':t['id'],'right_id':s['id'],'status':'full'}];raw['payload']['full_matches']['GT_G']=[{'checker_scenario_id':t['id'],'generated_scenario_id':s['id'],'status':'full'}];write_json(file,raw)
 feedback(p,{'revision':0,'settings_hash':q['settings_hash'],'scenario_id':s['id'],'choice':'adopt','reviewer':'A'},q)
 v=snapshot(p,'C');assert len(v['evaluation']['GT'])==1 and not v['added'] and len(v['confirmations'])==1


def test_real_business_rules_reach_only_originating_node_after_explicit_apply(tmp_path):
 from scene_completion.workflow import Execution
 from tests.test_workflow import memory_inputs,R
 p=tmp_path/'run-project';p.mkdir();x=memory_inputs();ref=R[0]
 docs=[{'source_id':ref['source_id'],'name':'r.md','channel':'normal','lines':[{'number':ref['line_start'],'text':ref['quote']}]}]
 static={'normal-documents':docs,'fused-ssd':{'interactions':x['sr-ssd']['interactions'],'rr_sr_links':[],'pending':[]}}
 seen=[]
 def result(packet):seen.append(packet['input']);return {'rules':[],'pending':[]}
 ex=Execution(p/'run',mocks={'normal-rules':result});ex.add('C:normal-rules','normal-rules',static=static,case='C');ex.finish()
 report(p,'C:normal-rules','normal-rules','C',{'question':'规则未知','required_answer':'请补规则','question_type':'rule_completion'},inputs=static)
 q=next(i for i in pending_items(p) if i['question_type']=='rule_completion');answer(p,q,{'choice':'provide_rule','answer':'分类必须存在并启用，由Platform校验','reviewer':'A','revision':0})
 apply_answers(p,impact(p)['plan_id'])
 ex=Execution(p/'run',mocks={'normal-rules':result});ex.add('C:normal-rules','normal-rules',static=static,case='C');ex.finish()
 assert seen[-1]['review-documents'][0]['channel']=='normal'
 assert any(d['source_id'].startswith('business-') for d in seen[-1]['normal-documents'])


def test_cli_capabilities_dry_run_answers_and_impact_share_the_web(tmp_path,capsys):
 c,rid,p=project(tmp_path);api=FakeAPI(c);q=first(p)
 assert main(['capabilities'],client=api)==0;assert 'pending' in json.loads(capsys.readouterr().out)['commands']
 f=tmp_path/'answer.json';f.write_text(json.dumps({'revision':0,'reviewer':'CLI业务','choice':'provide_rule','answer':'分类必须存在'}))
 assert main(['pending','--project',rid,'--item',q['id'],'--file',str(f),'--dry-run'],client=api)==0;assert not json.loads(capsys.readouterr().out)['saved'];assert not (p/'pending_decisions.json').exists()
 assert main(['pending','--project',rid,'--item',q['id'],'--file',str(f)],client=api)==0;capsys.readouterr()
 assert main(['impact','--project',rid],client=api)==0;v=json.loads(capsys.readouterr().out);assert v['roots']==q['origins']
 assert main(['rerun','--project',rid,'--affected','--plan-id',v['plan_id'],'--dry-run'],client=api)==0;assert not json.loads(capsys.readouterr().out)['saved']


def test_resolved_question_history_and_prior_report_survive_rerun(tmp_path):
 _,_,p=project(tmp_path);q=first(p)
 answer(p,q,{'choice':'provide_rule','answer':'分类必须存在','reviewer':'业务','revision':0})
 before=(p/'run/run_manifest.json').read_bytes();plan=impact(p);apply_answers(p,plan['plan_id'])
 archives=list((p/'run/report_versions').glob('business-review-*'));assert len(archives)==1
 assert (archives[0]/'run_manifest.json').read_bytes()==before
 assert list((archives[0]/'outputs').glob('*.json'))
 st=read_json(p/'run/workflow_tasks.json');key=q['origins'][0];write_json(p/'run'/st['tasks'][key]['output_file'],{'payload':{'rules':[],'pending':[]}})
 (p/'pending_index.json').unlink(missing_ok=True)
 # Change the output hash to invalidate the presentation cache just as execution does.
 st['tasks'][key]['output_hash']='new';write_json(p/'run/workflow_tasks.json',st)
 v=pending_view(p,status='historical',queue='all');assert any(i['id']==q['id'] for i in v['items'])
 assert pending_view(p,queue='all')['counts']['unresolved']==0


def test_invalid_human_gt_link_is_rejected_before_history_write(tmp_path):
 _,p,q,g,c=scoring_project(tmp_path)
 with pytest.raises(ValueError,match='同定位'):
  feedback(p,{'revision':0,'settings_hash':q['settings_hash'],'scenario_id':q['Q'][0]['id'],'choice':'adopt','reviewer':'业务','truth_resolution':{'choice':'link','truth_id':'made-up'}},q)
 assert history(p)['revision']==0


def test_windows_review_package_marker_and_portable_source_mapping(tmp_path):
 _,rid,p=project(tmp_path);program=io.BytesIO()
 with zipfile.ZipFile(program,'w') as z:
  z.writestr('scene-completion-windows-x64/python/python.exe',b'portable runtime')
  z.writestr('scene-completion-windows-x64/data/old/model.local.json','DO_NOT_SHIP')
  z.writestr('scene-completion-windows-x64/.env','DO_NOT_SHIP')
 data,snap=windows_package(p,io.BytesIO(program.getvalue()))
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  assert 'scene-completion-windows-x64/python/python.exe' in z.namelist()
  marker=json.loads(z.read('scene-completion-windows-x64/data/.review-mode.json'));assert marker['review_only']
  assert 'scene-completion-windows-x64/data/'+rid+'/review_sources.json' in z.namelist()
  assert b'DO_NOT_SHIP' not in b''.join(z.read(n) for n in z.namelist())


def test_recommendation_feedback_roundtrip_adds_gt_without_touching_frozen_outputs(tmp_path):
 rid,p,q,g,c=scoring_project(tmp_path);blob,_=project_archive(p);b=tmp_path/'reviewer';b.mkdir()
 with zipfile.ZipFile(io.BytesIO(blob)) as z:z.extractall(b)
 s=q['Q'][0];feedback(b,{'revision':0,'settings_hash':q['settings_hash'],'scenario_id':s['id'],'choice':'adopt','reviewer':'审核乙','note':'确认遗漏'},q)
 document=export_feedback(b);before=(p/'run/workflow_tasks.json').read_bytes()
 assert import_feedback(p,document)['ready_count']==1
 result=import_feedback(p,document,dry_run=False);assert result['saved']
 assert snapshot(p,'C')['added'][0]['generated_source_id']==s['id']
 assert (p/'run/workflow_tasks.json').read_bytes()==before and not impact(p)['roots']


def test_decorating_large_queue_reads_task_state_once(tmp_path,monkeypatch):
 import scene_completion.review_questions as questions
 _,_,p=project(tmp_path);q=first(p);rows=[{**q,'id':str(n)} for n in range(550)];calls=[];original=questions.load
 def counted(project,name,default):
  if name=='run/workflow_tasks.json':calls.append(name)
  return original(project,name,default)
 monkeypatch.setattr(questions,'load',counted)
 assert len(questions.decorate(p,rows))==550 and len(calls)==1


def test_cli_guidance_and_account_dry_run_never_write(tmp_path,capsys):
 c,rid,p=project(tmp_path);api=FakeAPI(c)
 assert main(['guide','--project',rid,'--node','api-map','--text','仅检查已有依据','--dry-run'],client=api)==0
 assert not json.loads(capsys.readouterr().out)['saved']
 from scene_completion.node_conversations import Conversations
 assert not Conversations(p/'run').list('api-map')
 assert main(['save-account','--name','离线客户','--base-url','http://offline/v1','--model','deepseek','--api-key-env','NO_CALL_KEY','--dry-run'],client=api)==0
 assert not json.loads(capsys.readouterr().out)['saved']
 assert not (p.parent/'model-accounts.local.json').exists()


def test_explicit_ssd_ownership_diagnostics_are_engineering_not_exception_questions(tmp_path):
 from scene_completion.review_questions import decorate
 _,_,p=project(tmp_path);q=first(p);q.pop('question_type');q.pop('answer_spec')
 q['reason']='原文要求A校验，但fused-ssd中B为唯一接收方，无法确定实际执行对象'
 value=decorate(p,[q])[0]
 assert value['queue']=='structure' and value['question_type']=='binding_confirmation' and value['engineering_review']
 assert 'anomaly' not in value['answer_spec']['choices']


def test_source_markdown_document_view_retains_all_lines_and_window_compatibility(tmp_path):
 client,rid,p=project(tmp_path)
 text='# 文档标题\n\n'+'\n'.join(f'正文 {n}' for n in range(150))+'\n\n## 参数约束\n\n| 参数 | 范围 |\n| --- | --- |\n| pageSize | 1-100 |\n'
 file=p/'sources/full.md';file.write_text(text,encoding='utf-8')
 import hashlib
 rows=[{'number':n,'text':v} for n,v in enumerate(text.splitlines(),1)]
 doc={'source_id':'portable-markdown','name':'full.md','path':'sources/full.md','file_hash':hashlib.sha256(file.read_bytes()).hexdigest(),'lines':rows,'channel':'normal','role':'sr'}
 write_json(p/'review_sources.json',{'documents':[doc]})
 endpoint=f'/api/projects/{rid}/sources/portable-markdown'
 full=client.get(endpoint,params={'view':'document','start':158,'end':158,'quote':rows[157]['text']})
 assert full.status_code==200,full.text
 body=full.json();assert body['lines']==rows and body['highlight_start']==158 and body['document_format']=='markdown'
 window=client.get(endpoint,params={'start':158,'end':158,'context':2}).json()
 assert len(window['lines'])<len(rows) and window['view']=='window' and window['lines'][0]['number']==156
 assert client.get(endpoint,params={'view':'unsafe'}).status_code==400
 # Full reading retains the same snapshot integrity check as paged reading.
 file.write_text(text+'changed',encoding='utf-8')
 assert client.get(endpoint,params={'view':'document'}).status_code==400


def test_large_source_document_offers_paged_mode_without_silent_truncation(tmp_path):
 client,rid,p=project(tmp_path)
 rows=[{'number':n,'text':'中'*1000} for n in range(1,701)]
 write_json(p/'review_sources.json',{'documents':[{'source_id':'big','name':'big.md','lines':rows}]})
 endpoint=f'/api/projects/{rid}/sources/big'
 result=client.get(endpoint,params={'view':'document'})
 assert result.status_code==400 and '2MB' in result.text
 result=client.get(endpoint,params={'start':400,'end':400,'context':2})
 assert result.status_code==200 and len(result.json()['lines'])==5
