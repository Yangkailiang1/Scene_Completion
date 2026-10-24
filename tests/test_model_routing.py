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
