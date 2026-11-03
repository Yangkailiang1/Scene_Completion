"""Display-only taxonomy: interaction scope/four levels and global dependencies.

Stable definition IDs, applicability and scoring are unchanged by these paths.
"""
FUNCTIONS={'display_interaction':'展示交互型','analysis_generation':'分析生成型','release_activation':'发布生效型'}
BASE=['交互级关注点','Service关注点','单个Service内部']
CRUD={'query_retrieval':'R：查询检索','create':'C：创建','update':'U：更新','delete':'D：删除'}

def paths(key,definitions,direction=None):
    d=definitions.get(key,{})
    layer,group=d.get('layer'),d.get('group')
    if key=='service.resource_mutation.idempotency':return [BASE+['第二层：业务实体CRUD关注点',CRUD[group]] for group in ('query_retrieval','update','delete')]
    if layer=='human':return [['交互级关注点','人类Actor关注点']]
    if layer=='global':return [['全局业务依赖级关注点','用例与业务实体依赖']]
    if layer=='relation':return [['交互级关注点','Service之间']]
    if layer=='base':
        name='输入数据' if key=='service.base.request_data' else '输出数据' if key=='service.base.response_contract' else '业务实体属性约束' if group=='business_attribute' else '外部Service调用'
        return [BASE+['第一层：基础关注点',name]]
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
    if layer=='functional' and group in CRUD:return [BASE+['第二层：业务实体CRUD关注点',CRUD[group]]]
    if layer=='functional' and group in FUNCTIONS:return [BASE+['第三层：业务关注点',FUNCTIONS[group]]]
    if layer=='technology' and group in {'database','llm'}:return [BASE+['第四层：技术扩展关注点',{'database':'数据库','llm':'LLM'}[group]]]
    return [['待归类']]

def presentation(definitions):return {'version':'four-level-interaction-and-global-v1','paths':{key:paths(key,definitions) for key in definitions},'unit':'稳定定义ID；输入/输出及CRUD可引用同一ID，路径不重复计分'}
