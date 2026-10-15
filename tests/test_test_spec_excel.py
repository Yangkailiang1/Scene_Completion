from openpyxl import Workbook
import pytest
from scene_completion.document_extract import extract_document
from scene_completion.sources import index_sources,validate_refs
from scene_completion.assessment import extract_reference_test_scenarios
from scene_completion.interaction_batches import test_packets as make_test_packets


def test_six_columns_excel_and_markdown_share_independent_test_channel(tmp_path):
    book=Workbook();sheet=book.active;sheet.title='订单测试'
    sheet.append(['用例编号','用例名称','前提条件','测试步骤','预期结果','对应需求'])
    sheet.append(['0001','重复提交订单','顾客已登录','1. 提交订单\n2. 使用同一幂等键重复提交','返回已有订单，不重复创建','UC-1'])
    path=tmp_path/'test_spec.xlsx';book.save(path);book.close()
    document=extract_document(path)
    parsed=extract_reference_test_scenarios(document['text'])
    assert parsed['valid'],parsed['errors']
    record=parsed['scenarios'][0]
    assert record['scenario_type']=='unspecified' and record['test_scenario_id']=='0001'
    assert '重复提交' in record['test_steps'] and record['requirements']=='UC-1'
    index=index_sources([str(path)]);index['documents'][0]['requirement_layer']='TEST'
    line=record['source_heading_line']
    ref=validate_refs([{'document':path.name,'line_start':line,'line_end':line}],index)[0]
    assert ref['worksheet_locations'][0]['sheet']=='订单测试' and ref['worksheet_locations'][0]['row']==2
    make_test_packets({'use_cases':[{'use_case_id':'UC-1'}]},index,tmp_path/'packets')
    assert '场景类型' not in document['text']  # extraction never guesses the label
    markdown='''# 测试
### 0001：重复提交订单
- 前提条件：顾客已登录
- 测试步骤：1. 提交订单
2. 使用同一幂等键重复提交
- 预期结果：返回已有订单，不重复创建
- 对应需求：UC-1
'''
    md=extract_reference_test_scenarios(markdown)
    assert md['valid'],md['errors']
    assert md['scenarios'][0]['test_steps']==record['test_steps']


def test_excel_formulas_are_not_executed_or_silently_read_as_empty(tmp_path):
    book=Workbook();sheet=book.active
    sheet.append(['用例编号','用例名称','前提条件','测试步骤','预期结果','对应需求'])
    sheet.append(['T-1','例子','无','=1+1','正常返回','UC-1'])
    path=tmp_path/'formulas.xlsx';book.save(path);book.close()
    with pytest.raises(ValueError,match='formula requires explicit values'):extract_document(path)


def test_reference_cli_reads_excel_and_markdown_examples_and_validates(tmp_path):
    import importlib.util
    from pathlib import Path
    from scene_completion.semantic_backend import read_json
    entry=Path(__file__).resolve().parents[1]/'.cac/tools/scene_completion.py'
    spec=importlib.util.spec_from_file_location('reference_cli',entry)
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    outputs=[]
    for suffix in ('xlsx','md'):
        result=tmp_path/(suffix+'.json')
        assert cli._main_impl(['extract-test-scenarios','--input',str(entry.parents[2]/'examples'/('test_spec.example.'+suffix)),
            '--output',str(result)])==0
        assert cli._main_impl(['validate-test-scenarios','--input',str(result)])==0
        outputs.append(read_json(result))
    fields=['test_scenario_id','name','preconditions','test_steps','expected_result','requirements','scenario_type']
    assert [{k:r[k] for k in fields} for r in outputs[0]['scenarios']]==[{k:r[k] for k in fields} for r in outputs[1]['scenarios']]
    assert outputs[0]['scenarios'][0]['source_positions'][0]['row']==2


def test_same_excel_and_markdown_merge_sources_but_conflicting_ids_are_rejected(tmp_path):
    from pathlib import Path
    from scene_completion.semantic_backend import read_json
    examples=Path(__file__).resolve().parents[1]/'examples'
    paths=[str(examples/('test_spec.example.'+suffix)) for suffix in ('md','xlsx')]
    index=index_sources(paths)
    manifest=make_test_packets({'use_cases':[{'use_case_id':'UCG-004-UC001'}]},index,tmp_path/'combined')
    packet=read_json(tmp_path/'combined'/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    assert len(packet['input']['records'])==5
    assert all(len(r['source_refs'])==2 for r in packet['input']['records'])
    conflict=tmp_path/'different.md'
    conflict.write_text((examples/'test_spec.example.md').read_text(encoding='utf8').replace('返回 productId 和草稿状态','创建失败'),encoding='utf8')
    with pytest.raises(ValueError,match='conflicting test definitions'):
        make_test_packets({'use_cases':[{'use_case_id':'UCG-004-UC001'}]},index_sources([paths[1],str(conflict)]),tmp_path/'conflict')
