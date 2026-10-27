from copy import deepcopy
import base64,io,zipfile,json
import pytest
from scene_completion.test_sources import records,exception_documents,preview,xlsx_documents
from scene_completion.test_supplement import mechanical_tests,positive_inputs,to_truth,combine_truth
from scene_completion.scenario_types import filter_scenarios,filter_branches
from scene_completion.contracts import packet,registry
from scene_completion.validation import validate_result
from tests.test_workflow import memory_inputs,scenario,exchange

def docs():
 return [{'source_id':'test','name':'test.md','channel':'test','lines':[{'number':1,'text':'| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |'}]+[{'number':n,'text':f'| TEST-X-{n} | 异常这个词不代表类型 | {kind} | 服务可用 | 输入错误 | UC-X | check | reject | spec |'} for n,kind in enumerate(['异常','正常','可选',''],2)]}]

def workbook(rows,formula=False):
 from xml.sax.saxutils import escape
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w') as z:
  z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="测试" sheetId="1" r:id="rId1"/></sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
  xml='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
  for n,row in enumerate(rows,1):
   xml+=f'<row r="{n}">'+''.join(f'<c r="{chr(65+c)}{n}" t="inlineStr">'+('<f>1+1</f>' if formula and n==2 and c==0 else '')+f'<is><t>{escape(v)}</t></is></c>' for c,v in enumerate(row))+'</row>'
  z.writestr('xl/worksheets/sheet1.xml',xml+'</sheetData></worksheet>')
 return stream.getvalue()

def test_type_is_exact_column_not_words_anywhere_and_unknown_is_retained():
 d=docs();assert preview(d)['counts']=={'exception':1,'normal':1,'optional':1,'pending':1}
 assert [r['id'] for r in records(exception_documents(d))]==['TEST-X-2']
 assert preview(d)['issues'][0]['reason'].startswith('场景类型')

def test_excel_chinese_multiline_coordinates_and_markdown_equivalence():
 from scene_completion.test_sources import cells
 d=docs();rows=[cells(r['text']) for r in d[0]['lines']]
 rows[1][4]='line1\nline2'
 x=xlsx_documents(workbook(rows),'sample.xlsx','original')
 p=preview(x)
 assert p['counts']==preview(d)['counts']
 assert p['records'][0]['触发条件']=='line1\nline2' and p['records'][0]['row']==2
 assert x[0]['name']=='sample.xlsx#测试'
 assert p['records'][0]['source_refs'][0]['line_start']==2
 with pytest.raises(ValueError,match='公式'):xlsx_documents(workbook(rows,True),'bad.xlsx','id')

def test_preview_rejects_duplicate_ids_and_missing_fields():
 d=docs();d[0]['lines'].append(deepcopy(d[0]['lines'][1]));assert not preview(d)['valid']
 assert any('重复' in x['reason'] for x in preview(d)['issues'])

def test_excel_upload_and_version_restore_keep_original_file(tmp_path):
 from fastapi.testclient import TestClient
 from scene_completion.workbench import create_app
 from scene_completion.test_sources import cells
 client=TestClient(create_app(tmp_path));source={'name':'tests.xlsx','content_base64':base64.b64encode(workbook([cells(x['text']) for x in docs()[0]['lines'][:2]])).decode()}
 assert client.post('/api/test-sources/preview',json={'sources':[source]}).json()['counts']['exception']==1
 body={'name':'X','sources':{'RR':[{'name':'r.md','content':'RR'}],'SR':[{'name':'s.md','content':'SR'}],'test':[source]}}
 rid=client.post('/api/projects',json=body).json()['id'];first=client.get(f'/api/projects/{rid}/test-sources').json()
 assert (tmp_path/rid/'sources/test-0.xlsx').read_bytes()==base64.b64decode(source['content_base64'])
 second=client.put(f'/api/projects/{rid}/test-sources',json={'expected_version':first['version'],'sources':[{'name':'new.md','content':docs()[0]['lines'][0]['text']+'\n'+docs()[0]['lines'][1]['text']}]}).json()
 assert second['version']!=first['version'] and len(second['versions'])==2
 assert client.put(f'/api/projects/{rid}/test-sources',json={'expected_version':second['version'],'version':first['version']}).json()['version']==first['version']

def test_independent_memory_tests_cover_eight_rules_without_reading_G_or_E():
 x=memory_inputs();i=x['sr-ssd']['interactions'][0];inputs=positive_inputs({'interactions':[i]},x['api-parameters'],{'rules':[],'pending':[]},[],registry())
 value=mechanical_tests(inputs);assert len([t for t in value['tests'] if t['field']])==8
 packet('test-supplement',inputs)
 assert all('未提供' not in t['trigger'] for t in value['tests'] if t['field'] in {'memoryType','page','pageSize'})
 validate_result('test-supplement',value,inputs)
 assert len(to_truth(value,inputs)['scenarios'])==9
 assert not {'G','E','GT','exception-generate','existing-extract'}&set(inputs)
 with pytest.raises(ValueError):packet('test-supplement',{**inputs,'G':[]})

def test_optional_and_normal_never_reach_scores_or_matchers():
 d=docs();s=scenario('test');s['source_refs']=records(d)[2]['source_refs']
 out=filter_scenarios({'scenarios':[s]},{'test-documents':d},'test-ground-truth')
 assert out['scenarios']==[] and out['excluded'][0]['scenario_type']=='optional'
 b={'id':'b','case_hint':'x','description':'无符合条件商品，返回空列表 total=0','operation_hint':'query','party_hint':'Shop','source_refs':s['source_refs']}
 assert not filter_branches({'branches':[b]})['branches']
 b['description']='查询不存在的指定实例，HTTP 404';assert filter_branches({'branches':[b]})['branches']
 s['cause']='no_matching_records';s['interaction_id']='query'
 assert not filter_scenarios({'scenarios':[s]}, {},'exception-generate')['scenarios']
 assert filter_scenarios({'scenarios':[s]}, {'normal-rules':{'rules':[{'interaction_id':'query','condition':'结果必须非空'}]}},'exception-generate')['scenarios']

def test_supplement_merge_reuses_original_truth_ids_without_duplicate_scoring():
 a=scenario('original');b=deepcopy(a);b['id']='additional'
 result=combine_truth({'scenarios':[a],'pending':[]},{'scenarios':[b],'pending':[]},[{'left_id':'additional','right_id':'original','status':'full','reason':'same failure'}])
 assert [s['id'] for s in result['scenarios']]==['original'] and result['merged_test_ids'][0]['supplement_id']=='additional'

def test_external_branch_output_is_filtered_after_the_model_and_raw_response_reused(tmp_path):
 from scene_completion.workflow import Execution
 class Client:
  config={}
  calls=0
  def model(self,*args):return 'offline-fixture'
  def agent(self,p):self.calls+=1;return {'branches':[]}
 client=Client();inputs={'existing-documents':[]}
 for version in [0,1]:
  ex=Execution(tmp_path,mode='external',client=client);ex.add('branches'+str(version),'existing-branches',static=inputs)
  assert ex.finish()['complete']
 assert client.calls==1  # only tool/display node identity changed

def test_rule_signature_matches_only_same_scope_field_and_independent_constraint():
 from scene_completion.comparison_batches import exact_failure_signature
 a=scenario('a');a.update(field='page',scope='interface',data_location='query',failure_rule={'kind':'minimum','value':1})
 b=deepcopy(a);b.update(id='b',cause='another wording')
 assert exact_failure_signature(a)==exact_failure_signature(b)
 b['failure_rule']['kind']='maximum';assert exact_failure_signature(a)!=exact_failure_signature(b)
 b=deepcopy(a);b['data_location']='response';assert exact_failure_signature(a)!=exact_failure_signature(b)

def test_xlsx_partition_retains_custom_headers_for_type_and_trigger_mapping():
 from scene_completion.task_partitions import split_task
 from scene_completion.test_sources import markdown_row
 rows=[['测试ID','用例ID／名称','场景类型','交互／接口','测试名称','前置条件','触发条件','测试数据','测试步骤','预期结果'],['TEST-X-1','UC-X','异常','API-1','bad id','ready','id is invalid','bad','1. run','reject']]
 d={'source_id':'excel','name':'file.xlsx#测试','channel':'test','lines':[{'number':n,'text':markdown_row(row)} for n,row in enumerate(rows,1)]}
 units=split_task('test-ground-truth',{'test-documents':[d]})
 assert records(units[0][1]['test-documents'])[0]['触发条件']=='id is invalid'

def test_supplement_business_requires_own_positive_rule_and_no_invented_data_contract():
 x=memory_inputs();i=x['sr-ssd']['interactions'][0]
 inputs=positive_inputs({'interactions':[i]},x['api-parameters'],{'rules':[],'pending':[]},[],registry())
 ref=i['source_refs'];key='service.query_retrieval.resource_existence'
 inputs['normal-rules']['rules']=[{'id':'r1','interaction_id':i['id'],'concern_key':key,'resolution':'explicit','source_refs':ref}]
 t={**mechanical_tests(inputs)['tests'][-1],'concern_key':key,'normal_rule_id':'r1','trigger':'指定资源不存在'}
 validate_result('test-supplement',{'tests':[t]},inputs)
 for override in ({'normal_rule_id':'invented'},{'field':'memoryType'},{'executable':True,'normal_rule_id':None}):
  with pytest.raises(ValueError):validate_result('test-supplement',{'tests':[{**t,**override}]},inputs)
 inputs['normal-rules']['rules'][0]['resolution']='conditional'
 with pytest.raises(ValueError,match='条件级'):validate_result('test-supplement',{'tests':[t]},inputs)


def test_supplement_dedup_requires_full_clique_not_transitive_bridge():
 from scene_completion.test_supplement import deduplicate_truth
 rows=[{**scenario(k),'id':k} for k in 'abc']
 pairs=[{'left_id':a,'right_id':b,'status':'full','reason':'same failure'} for a,b in [('a','b'),('b','c')]]
 value=deduplicate_truth({'scenarios':rows,'pending':[]},pairs)
 assert [s['id'] for s in value['scenarios']]==['a','c']
 assert value['merged_supplement_ids'][0]['duplicate_id']=='b'

def test_excel_header_order_and_invalid_ids_are_not_silently_ignored():
 from scene_completion.test_sources import cells
 values=[cells(x['text']) for x in docs()[0]['lines'][:2]]
 values=[v[1:]+v[:1] for v in values]
 parsed=xlsx_documents(workbook(values),'reordered.xlsx','id')
 assert preview(parsed)['counts']['exception']==1
 values[1][-1]=''
 bad=preview(xlsx_documents(workbook(values),'bad-id.xlsx','id'))
 assert not bad['valid'] and any('格式无效' in x['reason'] for x in bad['issues'])

def test_compact_supplement_schema_restores_only_selected_rule_metadata():
 from scene_completion.indexed_context import EvidenceContext
 x=memory_inputs();i=x['sr-ssd']['interactions'][0]
 rule={'id':'r1','interaction_id':i['id'],'concern_key':'service.query_retrieval.resource_existence','resolution':'explicit','source_refs':i['source_refs'],'functional_kinds':['query'],'condition':'指定实例必须存在'}
 inputs=positive_inputs({'interactions':[i]},x['api-parameters'],{'rules':[rule],'pending':[]},[],registry())
 ctx=EvidenceContext(packet('test-supplement',inputs))
 props=ctx.packet['output_schema']['properties']['tests']['items']['properties']
 assert 'source_refs' not in props and 'interaction_id' not in props
 item={**mechanical_tests(inputs)['tests'][-1],'normal_rule_id':'r1','trigger':'指定实例不存在'}
 raw=ctx.encode_output({'tests':[item]})
 assert 'source_refs' not in raw['tests'][0]
 restored=ctx.expand(raw)['tests'][0]
 assert restored['source_refs']==rule['source_refs'] and restored['interaction_id']==i['id'] and restored['concern_key']==rule['concern_key']
 validate_result('test-supplement',{'tests':[restored]},inputs)

def test_gt_partition_retains_custom_nine_column_header():
 from scene_completion.test_sources import cells,markdown_row
 from scene_completion.task_partitions import split_task
 d=docs()[0];d['lines']=d['lines'][:2]
 for row in d['lines']:
  v=cells(row['text']);row['text']=markdown_row(v[1:]+v[:1])
 units=split_task('test-ground-truth',{'test-documents':[d]})
 parsed=records(units[0][1]['test-documents'])
 assert len(parsed)==1 and parsed[0]['id']=='TEST-X-2' and parsed[0]['scenario_type']=='exception'

def test_rejected_supplement_is_quarantined_not_counted_as_truth():
 from scene_completion.test_supplement import quarantine_invalid_tests
 x=memory_inputs();i=x['sr-ssd']['interactions'][0];inputs=positive_inputs({'interactions':[i]},x['api-parameters'],{'rules':[],'pending':[]},[],registry())
 valid=mechanical_tests(inputs)['tests'][0];bad={**valid,'trigger':'未知字段违反未知阈值','normal_rule_id':'invented'}
 out=quarantine_invalid_tests({'tests':[valid,bad]},inputs)
 validate_result('test-supplement',out,inputs)
 assert len(out['tests'])==1 and len(out['pending'])==1
 assert len(to_truth(out,inputs)['scenarios'])==1 and to_truth(out,inputs)['pending']==out['pending']


def recovered_document():
 text='''# 恢复测试用例
| 变更类型 | 用例编号 | 用例名称 | 用例描述 |
| --- | --- | --- | --- |
| 未提供 | RUC-001 | 查询资源 | 正常及异常分支 |

### RUC-001：查询资源
1. Actor：开发者
2. 前置条件：
   系统可访问。
3. 后置条件：返回结果。
5. 主成功路径：〔SC@SPEC-MAIN〕
   ① 开发者查询。
6. 扩展路径：
- EXT：exception：参数不合法〔SC@TC-INVALID〕 → 拒绝请求
- EXT：alternative_success：异常后重新查询成功〔SC@TC-RECOVER〕 → 返回结果
- EXT：undetermined：未明确的降级〔SC@TC-PENDING〕 → 处理方式待确认
'''
 return {'source_id':'recovered','name':'recovered.md','channel':'test','lines':[{'number':n,'text':t} for n,t in enumerate(text.splitlines(),1)]}


def test_recovered_usecase_overview_is_not_a_test_table_and_types_are_explicit():
 d=recovered_document();p=preview([d])
 assert p['valid'] and p['counts']=={'exception':1,'normal':2,'optional':0,'pending':1}
 assert not any('ID缺少' in x['reason'] for x in p['issues'])
 assert next(r for r in p['records'] if r['id']=='SC@TC-INVALID')['关联需求']=='RUC-001：查询资源'
 assert all(r['source_refs'][0]['quote']==d['lines'][r['row']-1]['text'] for r in p['records'])


def test_recovered_exception_projection_partition_and_gt_type_filter_use_original_ids():
 from scene_completion.task_partitions import split_task
 d=recovered_document();selected=exception_documents([d])
 assert [r['id'] for r in records(selected)]==['SC@TC-INVALID']
 units=split_task('test-ground-truth',{'test-documents':[d]})
 assert len(units)==1
 parsed=records(units[0][1]['test-documents']);assert parsed[0]['前置条件']=='系统可访问。'
 m={'interaction_id':'req','target':'receiver','object':'Platform','concern_key':'service.base.availability','status':'applicable','binding_id':'b','source_unit_ids':['SC@TC-INVALID'],'source_refs':parsed[0]['source_refs']}
 units=split_task('test-ground-truth',{'test-documents':[d],'identified-concerns':{'matches':[m],'pending':[]}})
 assert units[0][1]['identified-concerns']['matches']==[m]
 for sid,kind in [('SC@TC-INVALID','exception'),('SC@TC-RECOVER','normal'),('SC@TC-PENDING','pending')]:
  record=next(r for r in records([d]) if r['id']==sid);s=scenario('test');s['source_refs']=record['source_refs']
  filtered=filter_scenarios({'scenarios':[s]},{'test-documents':[d]},'test-ground-truth')
  assert bool(filtered['scenarios'])==(kind=='exception')


def test_markdown_test_header_does_not_leak_to_unrelated_tables_or_code_examples():
 d=docs()[0];d['lines']=d['lines'][:2]
 extra=['','## 接口说明','| 字段 | 描述 |','| --- | --- |','| page | 页码 |','```markdown',d['lines'][0]['text'],'| bad | example |','```']
 d['lines'] += [{'number':n,'text':v} for n,v in enumerate(extra,3)]
 assert preview([d])['valid'] and len(records([d]))==1


def test_create_recovered_markdown_preserves_original_and_detailed_errors_leave_no_project(tmp_path):
 from fastapi.testclient import TestClient
 from scene_completion.workbench import create_app
 c=TestClient(create_app(tmp_path));d=recovered_document();text='\n'.join(r['text'] for r in d['lines'])
 body={'name':'导入测试','sources':{'RR':[{'name':'rr.md','content':'RR'}],'SR':[{'name':'sr.md','content':'SR'}],'test':[{'name':'recovered.md','content':text}]}}
 created=c.post('/api/projects',json=body);assert created.status_code==200
 rid=created.json()['id'];assert (tmp_path/rid/'sources/test-0.md').read_text()==text
 assert c.get(f'/api/projects/{rid}/test-sources').json()['preview']['counts']['exception']==1
 body['sources']['test'][0]['content']=text+'\n'+d['lines'][-3]['text']
 failed=c.post('/api/projects',json=body);assert failed.status_code==400
 error=failed.json();assert 'recovered.md 第' in error['detail'] and error['import_preview']['valid'] is False
 assert len(list(tmp_path.glob('*/sources')))==1


def test_recovered_duplicate_scene_ids_are_still_blocking():
 d=recovered_document();d['lines'].append({**d['lines'][-3],'number':99})
 assert not preview([d])['valid'] and any('重复' in x['reason'] for x in preview([d])['issues'])
