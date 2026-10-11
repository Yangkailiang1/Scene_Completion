from copy import deepcopy
import pytest
from scene_completion.interaction_scope import assessment_base,select_cases,selected_use_case_ids,comparison_verification_enabled
from scene_completion.semantic_backend import write_json
from scene_completion.interaction_baseline import import_baseline,verify_import
from tests.test_interaction_baseline import original


def test_representative_selection_keeps_full_baseline_and_rejects_unknown_or_duplicate_cases():
    base={'use_cases':[{'use_case_id':'ClinicRead'},{'use_case_id':'VisitBook'}],'system_composition':{'nodes':[]}}
    original=deepcopy(base)
    assert assessment_base(base,['VisitBook'])['use_cases']==[{'use_case_id':'VisitBook'}]
    assert select_cases([{'use_case_id':'ClinicRead','id':'C1'},{'use_case_id':'VisitBook','id':'C2'}],['VisitBook'])==[{'use_case_id':'VisitBook','id':'C2'}]
    assert base==original
    for selected in (['Unknown'],['VisitBook','VisitBook']):
        with pytest.raises(ValueError,match='unique known'):
            assessment_base(base,selected)


def test_scope_and_actual_verification_strategy_survive_saved_resume(tmp_path):
    write_json(tmp_path/'run_manifest.json',{'evaluation_scope':{'kind':'representative','use_case_ids':['ClinicRead']},
        'comparison_verification':'final-review'})
    assert selected_use_case_ids(tmp_path)==['ClinicRead']
    assert comparison_verification_enabled(tmp_path) is False


def test_explicit_interaction_scope_retains_every_mount_and_defaults_to_full():
    from scene_completion.interaction_scope import scope_mounts
    ssd = {'exchanges': [{'local_id':'rr','exchange_id':'R','use_case_id':'Clinic','requirement_layer':'RR'},
        {'local_id':'sr','exchange_id':'S','use_case_id':'Clinic','requirement_layer':'SR','parent_exchange_id':'R'},
        {'local_id':'resource','exchange_id':'D','use_case_id':'Clinic','requirement_layer':'SR','parent_exchange_id':'R','parent_sr_exchange_id':'S'}]}
    mounts = [{'exchange_id':'R','mount_id':'m1'}, {'exchange_id':'S','mount_id':'m2'},
        {'exchange_id':'S','mount_id':'m3'}, {'exchange_id':'D','mount_id':'m4'}]
    before = deepcopy((ssd, mounts))
    assert scope_mounts(ssd,mounts) is mounts
    assert scope_mounts(ssd,mounts,['rr','sr']) == mounts[:3]
    assert (ssd,mounts) == before
    for selected in (['sr'], ['rr','resource'], ['rr','sr','sr'], ['rr','unknown']):
        with pytest.raises(ValueError):
            scope_mounts(ssd,mounts,selected)


def test_reviewed_checker_reuse_preserves_original_skill_and_execution_after_report_prose_changes(tmp_path,monkeypatch):
    root,index,base,frozen=original(tmp_path)
    target=tmp_path/'reuse'
    from scene_completion import interaction_batches as b
    previous=b.role_skill
    monkeypatch.setattr(b,'role_skill',lambda name: previous(name).replace(
        'RR、SR分别如实报告，合计单独报告，空分母为null。当前只验流程，不设置漏报率通过阈值。',
        'RR、SR各自须≤5%且各自C非空，合计单独报告。'))
    result=import_baseline(root/'existing_scenarios.json',target,index,base,retain_source_packets=True)
    assert result['retained_source_packets'] is True
    assert verify_import(target,index)==frozen


def test_checker_skill_semantic_change_cannot_reuse_old_baseline(tmp_path,monkeypatch):
    root,index,base,_=original(tmp_path)
    from scene_completion import interaction_batches as b
    previous=b.role_skill
    monkeypatch.setattr(b,'role_skill',lambda name: previous(name)+'\nCount success preconditions as exceptions.\n')
    with pytest.raises(ValueError,match='extraction rules'):
        import_baseline(root/'existing_scenarios.json',tmp_path/'reuse',index,base,retain_source_packets=True)


def test_acceptance_report_uses_scoped_checker_without_changing_full_baseline(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from scene_completion.role_cli import run_evaluate
    from scene_completion.semantic_backend import read_json
    write_json(tmp_path/'run_manifest.json',{'protocol':'rr-sr-ssd-identification-v1',
        'evaluation_scope':{'kind':'representative','use_case_ids':['Clinic']}})
    checked=[{'use_case_id':'Clinic','scenario_id':'C1'},{'use_case_id':'Imaging','scenario_id':'C2'}]
    write_json(tmp_path/'existing_scenarios.json',{'scenarios':checked})
    for name,value in {'generated_scenarios':{'scenarios':[]},'scenario_matches':{'pairs':[]},
            'metrics':{},'recommendations':{'items':[]},'adoption':{},'coverage_diagnosis':[],
            'concern_mounts':[]}.items():
        write_json(tmp_path/(name+'.json'),value)
    monkeypatch.setattr('scene_completion.interaction_replay.evaluate',lambda root:{'accepted':True})
    def report(root, generated, existing, *args, **kwargs):
        assert existing == checked[:1]
    monkeypatch.setattr('scene_completion.interaction_reports.export',report)
    monkeypatch.setattr('scene_completion.interaction_audit.run_check',lambda args:None)
    assert run_evaluate(SimpleNamespace(output_dir=str(tmp_path)))[1] == 0
    assert read_json(tmp_path/'existing_scenarios.json')['scenarios'] == checked


def test_retained_checker_reuse_cannot_change_source_assignment(tmp_path):
    root,index,base,_=original(tmp_path)
    changed=deepcopy(base)
    changed['use_cases']=[]
    with pytest.raises(ValueError,match='assignment count changed'):
        import_baseline(root/'existing_scenarios.json',tmp_path/'reuse',index,changed,retain_source_packets=True)


@pytest.mark.parametrize('backend,rerank',[('embedding',False),('agent',True)])
def test_deferred_backend_is_rejected_before_any_source_or_model_call(backend,rerank):
    from types import SimpleNamespace
    from scene_completion.interaction_cli import run
    with pytest.raises(ValueError,match='requires agent backends'):
        run(SimpleNamespace(match_backend=backend,recommend_backend='agent',rerank=rerank))
