from types import SimpleNamespace
import pytest
from scene_completion.semantic_backend import read_json,write_json
from scene_completion.concern_gap_history import verify_binding,copy_vectors,load
from scene_completion.sources import fingerprint
from scene_completion.concern_gap_ranking import scene_text


def test_history_proof_change_is_rejected(tmp_path):
    path=tmp_path/'proof.json';write_json(path,{'actual':'original'})
    binding={'proofs':{str(path):fingerprint(read_json(path))}}
    verify_binding(binding)
    write_json(path,{'actual':'changed'})
    with pytest.raises(ValueError,match='proof changed'):verify_binding(binding)


def test_vector_reuse_requires_same_model_endpoint_and_text(tmp_path):
    old=tmp_path/'old';cache=old/'.embedding_cache';cache.mkdir(parents=True)
    unit={'exception_object':'product','operation':'create','failure_mechanism':'duplicate','trigger_condition':'same name','necessary_conditions':[]}
    key=fingerprint(['https://embedding.invalid/v1','vector-A',scene_text(unit)])
    write_json(cache/(key+'.json'),[1.,0.])
    corpus={'binding':{'run':str(old)},'history':[unit]}
    class Client:
        config={'cache_dir':str(tmp_path/'new')}
        base_url='https://embedding.invalid/v1'
        def model(self,kind):return 'vector-A'
    client=Client()
    assert copy_vectors(corpus,client)==1 and copy_vectors(corpus,client)==0
    client.base_url='https://different.invalid/v1'
    assert copy_vectors(corpus,client)==0
    client.base_url='https://embedding.invalid/v1';client.model=lambda kind:'vector-B'
    assert copy_vectors(corpus,client)==0


def test_incomplete_history_does_not_initiate_any_project_work(tmp_path):
    write_json(tmp_path/'run_manifest.json',{'complete':False})
    with pytest.raises(ValueError,match='incomplete'):load(tmp_path,{},set(),set())


def test_stale_source_fails_before_reading_any_execution(tmp_path,monkeypatch):
    from scene_completion import concern_gap_history as h
    write_json(tmp_path/'run_manifest.json',{'complete':True})
    write_json(tmp_path/'result_bundle.json',{'source_index':{'documents':[{'document':'RR','text':'old'}]}})
    monkeypatch.setattr(h,'verify_bundle',lambda b:None)
    with pytest.raises(ValueError,match='source documents changed'):
        load(tmp_path,{'documents':[{'document':'RR','text':'new'}]},set(),set())
