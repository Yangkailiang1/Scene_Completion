from scene_completion.sources import index_sources,validate_refs
from scene_completion.inline_ar import from_sr


def test_inline_ar_keeps_original_file_and_line_but_does_not_promote_sr(tmp_path):
    path=tmp_path/'design.md'
    path.write_text('# Design\n## SR\nServiceA sends a request.\n## AR：ServiceA implementation\nImplementationA uses a library.\n### APIs\nPOST /implementation/a\n## SR continuation\nServiceB receives a request.\n',encoding='utf8')
    index=index_sources([str(path)]);index['documents'][0]['requirement_layer']='SR'
    derived=from_sr(index);doc=derived['documents'][0]
    assert index['documents'][0]['requirement_layer']=='SR'
    assert doc['requirement_layer']=='AR' and doc['embedded_ar']
    assert 'ServiceA sends' not in doc['text'] and 'ServiceB receives' not in doc['text']
    assert doc['text'].splitlines()[4]=='ImplementationA uses a library.'
    refs=validate_refs([{'document':'design.md','line_start':5,'line_end':5}],derived)
    assert refs[0]['heading_path'][-1]=='AR：ServiceA implementation'
    assert {c['title'] for c in doc['chapters']}=={'AR：ServiceA implementation','APIs'}


def test_absent_ar_or_rr_document_does_not_add_an_ar_model_call(tmp_path):
    path=tmp_path/'rr.md';path.write_text('# AR: named in RR\nSome implementation\n',encoding='utf8')
    index=index_sources([str(path)]);index['documents'][0]['requirement_layer']='RR'
    assert from_sr(index)['documents']==[]
    index['documents'][0]['requirement_layer']='SR';index['documents'][0]['chapters'][0]['title']='System architecture'
    assert from_sr(index)['documents']==[]
