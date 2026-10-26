import pytest
from scene_completion.model_routing import routed_config

def test_task_override_role_and_ledger_isolation_without_mutating_base():
    c={'agent_model':'base','token_budget_limit':900000,'token_budget_ledger':'base.json','role_models':{'modeler':'qwen','checker':'glm'},'task_models':{'exception-generate':'base'},'model_profiles':{'qwen':{'token_budget_ledger':'qwen.json','extra_body':{'enable_thinking':False}},'glm':{'token_budget_ledger':'glm.json'}}}
    q=routed_config(c,'fused-ssd','modeler');g=routed_config(c,'existing-extract','checker');b=routed_config(c,'exception-generate','modeler')
    assert (q['agent_model'],q['token_budget_ledger'])==('qwen','qwen.json')
    assert (g['agent_model'],g['token_budget_ledger'])==('glm','glm.json')
    assert b['agent_model']=='base' and 'role_models' not in q
    q['extra_body']['enable_thinking']=True
    assert c['model_profiles']['qwen']['extra_body']['enable_thinking'] is False
    assert routed_config(b,'exception-generate','modeler') is None

def test_model_switch_cannot_share_spent_allowance_or_change_material_channels():
    c={'agent_model':'base','token_budget_limit':100,'role_models':{'checker':'glm'}}
    with pytest.raises(ValueError,match='independent'):routed_config(c,'existing-extract','checker')
    c['model_profiles']={'glm':{'token_budget_ledger':'glm.json','api_key':'wrong'}}
    with pytest.raises(ValueError,match='unsupported'):routed_config(c,'existing-extract','checker')


def test_invalid_model_parameter_blocks_siblings_but_corrected_config_can_run(tmp_path):
    from scene_completion.model_client import SemanticClient
    from scene_completion.model_access import ModelUnavailable
    calls=[]
    def transport(url,key,body,timeout,retries):
        calls.append(body)
        if body.get('enable_thinking') is False:
            error=ValueError('provider rejects this configuration')
            error.response_diagnostic={'http_status':400,'failure_category':'invalid_configuration','configuration_required':True,'parameter':'enable_thinking'}
            raise error
        return {'choices':[{'message':{'content':'ok'}}]}
    config={'base_url':'http://example.invalid/v1','api_key':'test-only','agent_model':'preview','cache_dir':str(tmp_path),'extra_body':{'enable_thinking':False}}
    a=SemanticClient(config,transport)
    for _ in range(2):
        with pytest.raises(ModelUnavailable):a.post('/chat/completions',{'model':'preview','enable_thinking':False})
    assert len(calls)==1  # independent sibling cannot repeat the same invalid request
    b=SemanticClient({**config,'extra_body':{'enable_thinking':True}},transport)
    assert b.post('/chat/completions',{'model':'preview','enable_thinking':True})['choices']
    assert len(calls)==2
