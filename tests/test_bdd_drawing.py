import json
from xml.etree import ElementTree as ET
from scene_completion.bdd_drawing import build_bdd,export_bdd
from scene_completion.result_views import ResultView
from scene_completion.storage import fingerprint,write_json


def sample():
    def node(id,name,typ,parent=None,status='explicit'):
        return dict(id=id,name=name,composition_type=typ,parent_id=parent,source_status=status,source_refs=[{'source_id':'rr','line_start':1,'line_end':1,'quote':name}])
    return {'components':[node('sys','平台','系统边界'),node('actor','开发者','外部Actor（人类）'),node('service','查询服务','内部服务','sys'),node('db','资源表','内部数据库','sys'),node('ext','外部服务','外部Actor（系统）'),node('ui','推断前端','UI/前端','sys','inferred'),node('uc','查询用例','用例','sys')],
            'relations':[{'from_id':'actor','to_id':'sys','relation':'通过UI交互','source_refs':[]},{'from_id':'sys','to_id':'ext','relation':'调用','source_refs':[]},{'from_id':'actor','to_id':'uc','relation':'参与用例','source_refs':[]}]}


def test_bdd_keeps_classification_ownership_and_external_association_separate():
    m=build_bdd(sample());edges=m['relationships']
    assert {(e['from_id'],e['to_id']) for e in edges if e['kind']=='composition'}=={('sys','service'),('sys','db')}
    assert any(e['kind']=='association' and e['from_id']=='actor' and e['to_id']=='sys' for e in edges)
    assert not any(e['kind']=='composition' and e['to_id'] in {'actor','ext','ui'} for e in edges)
    assert m['excluded_behavior'][0]['id']=='uc'
    assert not any(b['id']=='uc' for b in m['blocks'])
    types={b['id']:b for b in m['blocks'] if b['kind']=='classifier'}
    assert all(e['to_id'] in types for e in edges if e['kind']=='generalization')
    assert m['pending'][0]['component_id']=='ui'


def test_bdd_does_not_compose_unknown_parent_or_cyclic_ownership():
    p=sample();p['components'][0]['parent_id']='service';p['components'][3]['parent_id']='missing'
    m=build_bdd(p)
    assert not any(e['kind']=='composition' for e in m['relationships'])
    assert len(m['pending'])>=3


def test_exports_have_valid_svg_and_editable_relations_and_reuse_unchanged_view(tmp_path):
    p=sample();p['components'][2]['name']='Service <A> & "B"'
    export_bdd(p,tmp_path);mtime=(tmp_path/'system-bdd.svg').stat().st_mtime_ns
    svg=ET.parse(tmp_path/'system-bdd.svg').getroot()
    assert svg.attrib['aria-label']=='SysML块定义图'
    assert any(e.attrib.get('data-symbol')=='composition-diamond' for e in svg.iter())
    source=(tmp_path/'system-bdd.puml').read_text()
    assert source.startswith('@startuml') and source.endswith('@enduml\n')
    assert '<<block>>' in source and '*--' in source and '--|>' in source
    assert '参与用例' not in source
    export_bdd(p,tmp_path)
    assert (tmp_path/'system-bdd.svg').stat().st_mtime_ns==mtime
    p['components'][2]['name']='改名';export_bdd(p,tmp_path)
    assert json.loads((tmp_path/'system-bdd.json').read_text())['payload']['source_hash']==fingerprint(p)


def test_completed_results_get_bdd_without_changing_saved_task_outputs(tmp_path):
    root=tmp_path/'run';f='task_outputs/components.json'
    write_json(root/f,{'payload':sample()});write_json(root/'workflow_tasks.json',{'tasks':{'components':{'stage':'components','case':'shared','status':'passed','output_file':f}}})
    write_json(root/'workflow_graph.json',{'nodes':[{'id':'components','label':'系统组成'}]})
    folder=root/'artifacts/shared';folder.mkdir(parents=True);(folder/'components.svg').write_text('<svg/>')
    before=(root/f).read_bytes();catalog=ResultView(tmp_path).catalog();bdd=next(x for x in catalog if x['stage']=='bdd')
    assert bdd['source_task_key']=='components' and len(bdd['files'])==5
    assert all((tmp_path/f['path']).exists() for f in bdd['files'])
    assert (root/f).read_bytes()==before
