"""Display-only taxonomy paths. Definitions, IDs and scoring stay unchanged."""
FUNCTIONS={'display_interaction':'展示交互型','query_retrieval':'查询检索型','resource_mutation':'资源变更型','analysis_generation':'分析生成型','release_activation':'发布生效型'}
BASE=['Service关注点','单个Service内部']

def paths(key,definitions,direction=None):
    d=definitions.get(key,{})
    layer,group=d.get('layer'),d.get('group')
    if layer=='human':return [['人类Actor关注点']]
    if layer=='relation':return [['Service关注点','Service之间']]
    if layer=='base':return [BASE+['第一层：基础关注点']]
    if layer=='shared':
        roots={'service.base.request_data':'输入数据','service.base.response_contract':'输出数据'}
        found=set()
        def visit(k,seen):
            if k in seen:return
            if k in roots:found.add(k)
            for parent in definitions.get(k,{}).get('parents',[]):visit(parent,seen|{k})
        visit(key,set())
        if direction:found &= {'service.base.response_contract' if direction=='return' else 'service.base.request_data'}
        return [BASE+['第一层：基础关注点',roots[k]] for k in roots if k in found] or [['待归类']]
    if layer=='functional' and group in FUNCTIONS:return [BASE+['第二层：功能关注点',FUNCTIONS[group]]]
    if layer=='technology' and group in {'database','llm'}:return [BASE+['第三层：技术扩展',{'database':'数据库','llm':'LLM'}[group]]]
    return [['待归类']]

def presentation(definitions):return {'paths':{key:paths(key,definitions) for key in definitions},'unit':'稳定定义ID；输入/输出可引用同一ID'}
