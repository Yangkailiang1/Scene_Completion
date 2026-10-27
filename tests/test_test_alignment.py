from copy import deepcopy
import pytest
from scene_completion.test_alignment import known_catalogue,exact_alignment,scoped_tests,as_records
from scene_completion.contracts import packet
from scene_completion.validation import validate_result
from scene_completion.storage import read_json
from scene_completion.workflow import Execution,build_pipeline
from scene_completion.recommendation import evaluate,aggregate_comparison
from tests.test_test_sources import recovered_document
from tests.test_workflow import fake_pipeline


def test_different_test_case_number_is_semantically_aligned_without_answer_leakage(tmp_path):
 rr,sr,_,m=fake_pipeline(tmp_path);doc=recovered_document();cat=known_catalogue([doc])
 assert cat['cases'][0]['name']=='查询资源' and cat['tests'][1]['id']=='SC@TC-INVALID'
 calls=[]
 def align(p):
  calls.append(p);assert p['input']['test-inventory']['tests']==[]
  c=p['input']['test-inventory']['cases'][0];g=p['input']['case-groups']['groups'][0]
  assert not {'G','E','GT','exception-generate','existing-extract'}&set(p['input'])
  return {'matches':[{'test_case_id':c['id'],'case_group_id':g['id'],'status':'confirmed','basis':'fixture: test goal corresponds to requirement goal, different identifier retained','source_refs':c['source_refs']}]}
 m['test-case-align']=align
 ex=Execution(tmp_path/'run',mocks=m);build_pipeline(ex,rr,sr,[doc]);result=ex.finish()
 assert result['complete'] and len(calls)==1
 assert read_json(tmp_path/'run/test_catalogues/UC-X.json')['records'][1]['id']=='SC@TC-INVALID'
 assert result['test_case_correspondence'][0]['case_group_id']=='UC-X'
 record=ex.scheduler.state['tasks']['UC-X:test-concerns']
 assert record['status']=='passed'


def test_unmatched_tests_remain_visible_and_cannot_be_counted_as_complete(tmp_path):
 rr,sr,_,m=fake_pipeline(tmp_path);d=recovered_document()
 m['test-case-align']=lambda p:{'matches':[{'test_case_id':c['id'],'case_group_id':None,'status':'pending','basis':'业务目标无法确定','source_refs':c['source_refs']} for c in p['input']['test-inventory']['cases']]}
 ex=Execution(tmp_path/'run',mocks=m);build_pipeline(ex,rr,sr,[d]);out=ex.finish()
 assert not out['complete'] and out['test_case_correspondence'][0]['status']=='pending'
 assert out['analysis_complete']
 from scene_completion.project_review import pending_items
 assert any(x['category']=='测试用例对应' and x['source_channel']=='test_gt' for x in pending_items(tmp_path))


def test_catalogue_validation_rejects_type_changes_and_cross_channel_inputs():
 d=recovered_document();value=known_catalogue([d]);changed=deepcopy(value);changed['tests'][2]['scenario_type']='exception'
 with pytest.raises(ValueError,match='类型'):validate_result('test-inventory',changed,{'test-documents':[d]})
 with pytest.raises(ValueError):packet('test-inventory',{'test-documents':[d],'G':[]})
 foreign={**d,'channel':'normal'}
 with pytest.raises(ValueError):packet('test-inventory',{'test-documents':[foreign]})


def test_unknown_markdown_has_semantic_inventory_path_not_silent_empty_result():
 d={'source_id':'x','name':'freeform.md','channel':'test','lines':[{'number':1,'text':'## 测试说明\n用户查询时后端超时，应拒绝本次查询'}]}
 assert known_catalogue([d]) is None
 with pytest.raises(ValueError,match='静默丢弃'):validate_result('test-inventory',{'cases':[],'tests':[],'pending':[]},{'test-documents':[d]})
 assert packet('test-inventory',{'test-documents':[d]})['skill']=='scene-test-inventory'


def test_recommendation_before_M_and_after_Q_share_truth_and_reassign_full_pairs():
 g=[{'id':i,'scenario_type':'exception'} for i in ('a','b','c')];truth=[{'id':'t1'},{'id':'t2'}]
 report={'G':g,'GT':truth,'M':g,'metrics':{},'full_matches':{'GT_G':[{'checker_scenario_id':'t1','generated_scenario_id':'a'},{'checker_scenario_id':'t2','generated_scenario_id':'b'}],'GT_E':[]},'full_candidate_pairs_GT_G':[{'left_id':'t1','right_id':'a','status':'full'},{'left_id':'t2','right_id':'b','status':'full'},{'left_id':'t1','right_id':'c','status':'full'}]}
 out=evaluate(report,{'enabled':True,'Q':[g[2]]});comparison=out['recommendation_comparison']
 assert comparison['baseline']['metrics']['recommendation_adoption']['numerator']==2
 assert comparison['baseline']['metrics']['recommendation_adoption']['denominator']==3
 assert comparison['recommended']['metrics']['recommendation_adoption']['value']==100
 assert comparison['recommended']['metrics']['recommendation_false_positive']['denominator']==2
 merged=aggregate_comparison([comparison,comparison]);assert merged['baseline']['metrics']['recommendation_adoption']['numerator']==4 and merged['baseline']['metrics']['recommendation_adoption']['denominator']==6
 assert report['metrics']=={}  # keep prior saved report unchanged
 with pytest.raises(ValueError,match='子集'):evaluate(report,{'enabled':True,'Q':[{'id':'foreign'}]})


def test_historical_recommendation_from_another_snapshot_does_not_crash_view():
 from scene_completion.recommendation import comparison_for_view
 report={'GT':[{'id':'t'}],'M':[{'id':'m'}],'metrics':{},'full_matches':{'GT_G':[],'GT_E':[]}}
 before=deepcopy(report)
 value=comparison_for_view(report,{'enabled':True,'Q':[{'id':'old'}]})
 assert value['baseline']['candidate_count']==1 and value['recommended']['status']=='版本不一致，待重算'
 assert report==before


def test_custom_table_identifiers_are_preserved_and_only_exceptions_are_partitioned():
 from scene_completion.test_sources import preview
 from scene_completion.task_partitions import split_task
 text='| 测试ID | 测试名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 预期结果 |\n|---|---|---|---|---|---|---|\n| T001 | 查询失败 | 异常 | 已进入页面 | 超时 | UC-X | 拒绝 |\n| T002 | 正常浏览 | 正常 | 已进入页面 | 查询 | UC-X | 列表 |'
 doc={'source_id':'t','name':'cases.md','channel':'test','lines':[{'number':n,'text':t} for n,t in enumerate(text.splitlines(),1)]}
 cat=known_catalogue([doc]);assert preview([doc])['valid']
 units=split_task('test-concerns',{'test-documents':[doc],'test-inventory':cat})
 assert len(units)==1 and units[0][1]['test-inventory']['tests'][0]['id']=='T001'
 assert '正常浏览' not in str(units[0][1]['test-documents'])


def test_unstructured_test_pending_is_not_a_successful_empty_gt_run(tmp_path):
 rr,sr,_,m=fake_pipeline(tmp_path)
 doc={'source_id':'unknown','name':'unknown.md','channel':'test','lines':[{'number':1,'text':'此处测试含义暂未写清。'}]}
 ref=[{'source_id':'unknown','line_start':1,'line_end':1,'quote':doc['lines'][0]['text']}]
 m['test-inventory']={'cases':[],'tests':[],'pending':[{'reason':'测试信息不足，需补充场景类型和业务目标','source_refs':ref}]}
 ex=Execution(tmp_path/'run',mocks=m);build_pipeline(ex,rr,sr,[doc]);out=ex.finish()
 assert not out['complete'] and out['test_import_pending_count']==1 and out['analysis_complete']


def test_inventory_keeps_original_test_data_and_steps_in_normalized_records():
 from scene_completion.test_sources import markdown_row
 names=['测试ID','测试名称','类型','前置条件','触发条件','关联需求','预期结果','测试数据','测试步骤']
 row=['T001','范围错误','异常','服务可用','超出上界','UC-X','拒绝','pageSize=101','1.进入页面\n2.提交查询']
 doc={'source_id':'table','name':'cases.md','channel':'test','lines':[{'number':n,'text':markdown_row(r)} for n,r in enumerate([names,row],1)]}
 value=known_catalogue([doc]);record=as_records(value,[doc])[0]
 assert record['测试数据']=='pageSize=101' and record['测试步骤']=='1.进入页面\n2.提交查询'
 validate_result('test-inventory',value,{'test-documents':[doc]})
