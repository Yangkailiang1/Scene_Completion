from pathlib import Path
import json
from .storage import write_json,fingerprint
from .contracts import PROTOCOL

def export_task(root,task,payload,artifact_name=None):
    file_stem=artifact_name or task
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    write_json(root/(file_stem+'.json'),{'protocol':PROTOCOL,'task':task,'payload':payload})
    def show(x):return '待确认' if x is None else str(x)
    rows=[]; headers=[]
    if task=='test-catalogue':headers=['测试用例','场景编号','场景名称','类型','触发条件','预期结果'];rows=[[t['case_id'],t['id'],t['name'],t['scenario_type'],t['trigger'],t['expected_result']] for t in payload['tests']]
    elif task=='test-case-align':headers=['测试用例','RR/SR用例组','状态','对应依据'];rows=[[m['test_case_id'],m['case_group_id'],m['status'],m['basis']] for m in payload['matches']]
    elif task=='components':headers=['名称','系统组成'];rows=[[x['name'],x['composition_type']] for x in payload['components']]
    elif task=='object-operations':headers=['名称','支持的操作'];rows=[[x['name'],'、'.join(o['name'] for o in x['supported_operations'])] for x in payload['objects']]
    elif task=='api-map':headers=['服务名称','对应接口列表'];rows=[[s['name'],'；'.join(' '.join(filter(None,[i['id'],i['method'],i['address']])) for i in s['interfaces'])] for s in payload['services']]
    elif task=='api-parameters':
        headers=['API名称','接口地址','数据方向','参数位置','参数','数据类型','可选/必填','默认值','约束条件']
        rows=[[a['name'],show(a['address']),'输出' if p['location']=='response' else '输入',p['location'],p['name'],show(p['data_type']),'必填' if p['required'] is True else '可选' if p['required'] is False else '待确认',show(p['default']),'; '.join(r['kind']+'='+show(r['value']) if r['status']=='explicit' else r['kind']+'待确认' for r in p['constraints'])] for a in payload['apis'] for p in a['parameters']]
    elif task=='business-entities':
        headers=['业务实体','属性','适用操作','数据类型','必填','约束','来源']
        rows=[[e['name'],a['name'],a['operation'],show(a['data_type']),show(a['required']),
               '；'.join(c['kind']+'='+show(c['value']) for c in a['constraints']),
               '；'.join(r['source_id']+':'+str(r['line_start']) for r in a['source_refs'])]
              for e in payload['entities'] for a in e['attributes']]
        rows += [[e['name'],'业务规则 '+r['id'],r['operation'],'','',r['condition'],
                  '；'.join(ref['source_id']+':'+str(ref['line_start']) for ref in r['source_refs'])]
                 for e in payload['entities'] for r in e['business_rules']]
    elif task=='business-crud':
        headers=['用例','交互','业务实体','Service','CRUD','API','依据']
        rows=[[r['case_id'],r['interaction_id'],r['entity_id'],r['service'],r['operation'],show(r['api_id']),r['basis']] for r in payload['rows']]
    elif task=='business-attribute-map':
        headers=['API','方向','位置','完整字段路径','业务实体','属性','对应依据']
        rows=[[r[k] for k in ('api_id','direction','location','field_path','entity_id','attribute','basis')] for r in payload['mappings']]
    elif task=='data-dependencies':
        headers=['数据实体','字段','服务/实体关系','交互','来源']
        rows=[[e['name'],'、'.join(e['fields']),'','',''] for e in payload['entities']]
        rows += [[r['from_entity_id'],'、'.join(r['fields']),r['relation']+' → '+r['to_entity_id'],'',''] for r in payload['relations']]
        rows += [[r['entity_id'],'、'.join(r['fields']),r['producer_service']+' → '+r['consumer_service'],r['interaction_id'],''] for r in payload['flows']]
    elif task=='business-dependencies':
        headers=['前置用例','后续用例','前置业务实体','后续业务实体','依赖类型','适用条件','清理义务','级联组']
        rows=[[r['from_case_id'],r['to_case_id'],r['from_entity_id'],r['to_entity_id'],
               r['dependency_type'],r['condition'],r['obligation'],show(r['cascade_group'])] for r in payload['dependencies']]
    elif task in {'global-concerns','global-existing-concerns','global-test-concerns'}:
        headers=['全局依赖','对象','关注点','识别依据'];rows=[[r['dependency_id'],r['object'],r['concern_key'],r['basis']] for r in payload['matches']]
    elif task in {'global-scenarios','global-existing-scenarios','global-test-scenarios'}:
        headers=['全局依赖','对象','关注点','独立失败原因','条件','精度'];rows=[[r['dependency_id'],r['object'],r['concern_key'],r['cause'],'；'.join(r['conditions']),r['resolution']] for r in payload['scenarios']]
    elif task in {'rr-ssd','sr-ssd'}:
        headers=['顺序','发送方','操作','数据','接收方'];rows=[[i['sequence'],i['sender']['name'],i['operation']['name'],'、'.join(p['name'] for p in i['data']['sequence']),i['receiver']['name']] for i in payload['interactions']]
    elif task in {'concern-match','existing-concerns','test-concerns','test-additional-concerns'}:
        from .contracts import registry
        defs=registry()['definitions'];headers=['交互','Service','系统组成/数据','关注点','状态','继承路径','规则或待确认原因'];rows=[[m['interaction_id'],m.get('service') or '',m['object'],defs[m['concern_key']]['label'],{'applicable':'适用','pending':'待确认','not_applicable':'不适用'}.get(m.get('status'),m.get('status','待确认')),'；'.join(' → '.join(defs[k]['label'] for k in path) for path in m.get('inheritance_paths',[])),m.get('concrete_rule') or m.get('status_reason','')] for m in payload['matches']]
    if task in {'concern-compare','concern-evaluation'}:
        headers=['交互','方向','四要素','具体对象','关注点','E_c','G_c','GT_c','匹配依据']
        rows=[[r['anchor'].get(k,'') for k in ('interaction_id','direction','target','object','concern_key')]+[bool(r['cells'][ch]) for ch in ('E','G','GT')]+[r['reason']] for r in payload['rows']]
    if task=='pattern-applicability':
        headers=['关注点','模式','交互','失败条件','证据分级','适用结论','风险']
        rows=[[x['scenario']['concern_key'],x['pattern_id'],x['scenario']['interaction_id'],'；'.join(x['scenario']['conditions']),x['scenario']['confidence']['score'],x['status'],x['scenario']['risk']['level']] for x in payload['instances']]
    if task=='gap-recommend' and payload.get('enabled'):
        headers=['序号','场景','模式','优先分','风险R','历史H','纳入Q','排序/保底原因']
        rows=[[r['rank'],r['scenario_id'],r['pattern_id'],r['priority'],r['risk']['score'],r['history_score'],r['selected'],r['reason']] for r in payload['ranked']]
    if task=='normal-rules':
        headers=['规则ID','交互','所属服务','关注点','正常条件','异常条件','精度','待确认'];rows=[[r[k] for k in ('id','interaction_id','owner_service','concern_key','condition','violation','resolution','pending_details')] for r in payload['rules']]
    if task=='existing-branches':headers=['原分支ID','用例提示','原文异常','操作提示','参与方提示'];rows=[[b[k] for k in ('id','case_hint','description','operation_hint','party_hint')] for b in payload['branches']]
    elif task=='test-supplement':
        headers=['交互','关注点','字段','前置条件','触发条件','测试数据','测试步骤','预期结果','可执行','待确认'];rows=[[t['interaction_id'],t['concern_key'],t['field'] or '',t['preconditions'],t['trigger'],t['test_data'],t['steps'],t['expected_result'],t['executable'],t['pending_details']] for t in payload['tests']]
    elif task=='existing-bind':headers=['原分支','具体融合交互','状态','绑定依据'];rows=[[b[k] for k in ('branch_id','interaction_id','status','basis')] for b in payload['bindings']]
    elif task in {'existing-extract','test-ground-truth','exception-generate'}:
        from .contracts import registry
        defs=registry()['definitions'];headers=['具体交互','对象或字段','关注点','异常原因','原分支','覆盖范围','来源性质','细化依据']
        rows=[[s['interaction_id'],s['object'],defs[s['concern_key']]['label'],s['cause'],s.get('original_branch_id') or '',s.get('coverage_kind','exact'),s['source_status'],s['derivation']] for s in payload['scenarios']]
    if headers:
        safe=lambda x:str(x).replace('|','\\|').replace('\n','<br>')
        text='| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'
        text+='\n'.join('| '+' | '.join(map(safe,r))+' |' for r in rows)
        if task in {'concern-compare','concern-evaluation'}:
            text='# 关注点层对照\n\n计分单位：用例＋实际交互＋方向＋四要素对象＋关注点。具体场景另行计数。\n\n'+text
        if payload.get('pending'):
            text+='\n\n## 未计分的待确认项\n'+'\n'.join('- '+p.get('interaction_id','')+'：'+p['reason'] for p in payload['pending'])
        (root/(file_stem+'.md')).write_text(text+'\n',encoding='utf8')
    if task=='fused-ssd':
        from .ssd_drawing import render_fused_ssd
        render_fused_ssd(payload,root/(file_stem+'.svg'))
    if task in {'data-dependencies','business-dependencies'}:
        from .domain_model import dependency_svg
        lines=payload['flows']+payload['relations'] if task=='data-dependencies' else payload['dependencies']
        (root/(file_stem+'.svg')).write_text(dependency_svg(lines,'数据实体关系与跨服务依赖' if task=='data-dependencies' else '用例与业务实体依赖'),encoding='utf8')
    if task=='components':
        from .composition_drawing import render_composition
        render_composition(payload,root/(file_stem+'.svg'))
        from .bdd_drawing import export_bdd
        export_bdd(payload,root)
    if task in {'components','rr-ssd','sr-ssd'}:
        # Native vector text/shapes; source .dot is also supplied for editing.
        if task=='components':
            nodes=[(c['id'],c['name'],c['composition_type']=='用例') for c in payload['components']]
            edges=[(r['from_id'],r['to_id'],r['relation']) for r in payload['relations']]
        else:
            names=list(dict.fromkeys(p['name'] for i in payload['interactions'] for p in (i['sender'],i['receiver'])))
            nodes=[(n,n,False) for n in names];edges=[(i['sender']['name'],i['receiver']['name'],str(i['sequence'])+' '+i['operation']['name']) for i in payload['interactions']]
        q=lambda s:json.dumps(s,ensure_ascii=False)
        dot='digraph model { rankdir=LR;\n'+''.join(f'{q(i)} [label={q(n)}, shape={"ellipse" if usecase else "box"}];\n' for i,n,usecase in nodes)
        dot+=''.join(f'{q(a)} -> {q(b)} [label={q(label)}];\n' for a,b,label in edges)+'}\n'
        (root/(file_stem+'.dot')).write_text(dot,encoding='utf8')
        # Graphviz is optional; JSON, Markdown and DOT always export.
        import shutil,subprocess
        if task!='components' and shutil.which('dot'):
            try:subprocess.run(['dot','-Tsvg',str(root/(file_stem+'.dot')),'-o',str(root/(file_stem+'.svg'))],check=True,capture_output=True)
            except (OSError,subprocess.CalledProcessError):
                (root/(file_stem+'.render-warning.txt')).write_text('Graphviz rendering failed; editable JSON/Markdown/DOT retained.',encoding='utf8')
        if task in {'rr-ssd','sr-ssd'}:export_sequence_svg(root,task,payload)



def export_sequence_svg(root,task,payload):
    """Editable SVG lifelines/messages; no legacy graph representation."""
    from html import escape
    for cid in dict.fromkeys(i['case_id'] for i in payload['interactions']):
        rows=sorted((i for i in payload['interactions'] if i['case_id']==cid),key=lambda i:i['sequence'])
        names=list(dict.fromkeys(p['name'] for i in rows for p in (i['sender'],i['receiver'])))
        width=max(720,len(names)*260);height=150+len(rows)*95
        x={n:120+j*260 for j,n in enumerate(names)}
        svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3z" fill="#3970c6"/></marker></defs>',
        '<rect width="100%" height="100%" fill="white"/>']
        for n in names:
            svg.extend([f'<rect x="{x[n]-100}" y="20" width="200" height="45" rx="8" fill="#edf4ff" stroke="#3970c6"/>',f'<text x="{x[n]}" y="47" text-anchor="middle" font-size="15">{escape(n)}</text>',f'<line x1="{x[n]}" y1="65" x2="{x[n]}" y2="{height-20}" stroke="#3970c6" stroke-dasharray="5 4"/>'])
        for j,i in enumerate(rows):
            y=125+j*95;a=x[i['sender']['name']];b=x[i['receiver']['name']]
            label=escape(str(i['sequence'])+' '+i['operation']['name'])
            svg.extend([f'<line x1="{a}" y1="{y}" x2="{b}" y2="{y}" stroke="#3970c6" marker-end="url(#arrow)"'+(' stroke-dasharray="5 4"' if i['direction']=='return' else '')+'/>',f'<text x="{(a+b)/2}" y="{y-12}" font-size="14" text-anchor="middle">{label}</text>'])
        svg.append('</svg>');(Path(root)/(task+'-'+fingerprint(cid)[:12]+'.svg')).write_text('\n'.join(svg),encoding='utf8')

def export_missing_report(root,combined):
    root=Path(root);write_json(root/'missing_report.json',combined)
    from .contracts import registry
    defs=registry()['definitions'];lines=['# 缺失异常报告','', '两层计数：关注点按四要素对象绑定规则匹配，具体场景按独立失败条件匹配。推荐：'+('风险保底已启用' if combined.get('recommendation',{}).get('enabled') else '未启用')+'。','']
    def cell(v):return str(v).replace('|','\\|').replace('\n','<br>')
    for cid,report in combined['cases'].items():
        lines+=['## '+cid,'', '评测：'+combined['evaluation_status'][cid],'','### 交互及关注点','',
          '| 交互 | 发送方 | 操作 | 数据 | 接收方 |','| --- | --- | --- | --- | --- |']
        for i in report['interactions']['interactions']:
            lines.append('| '+' | '.join(cell(v) for v in (i['id'],i['sender']['name'],i['operation']['name'],'、'.join(p['name'] for p in i['data']['sequence']),i['receiver']['name']))+' |')
        lines+=['','| 交互 | Service | 对象/数据 | 关注点 | 状态 | 继承路径 | 规则或待确认原因 |','| --- | --- | --- | --- | --- | --- | --- |']
        for m in report['concerns']:lines.append('| '+' | '.join(cell(x) for x in (m['interaction_id'],m.get('service') or '',m['object'],defs[m['concern_key']]['label'],{'applicable':'适用','pending':'待确认','not_applicable':'不适用'}.get(m.get('status'),'待确认'),'；'.join(' → '.join(defs[k]['label'] for k in path) for path in m.get('inheritance_paths',[])),m.get('concrete_rule') or m.get('status_reason') or m['basis']))+' |')
        concern=report.get('concern_level',{})
        if concern:
            lines+=['','### 关注点层对照（不是场景条数）','','| 交互 | 四要素 | 对象 | 关注点 | E_c | G_c | GT_c |','| --- | --- | --- | --- | --- | --- | --- |']
            evaluation=combined.get('evaluation',{}).get(cid,{}).get('concern_level',concern)
            for r in evaluation.get('rows',[]):
                a=r['anchor'];lines.append('| '+' | '.join(cell(x) for x in (a['interaction_id'],a['target'],a['object'],a['concern_key'],bool(r['cells']['E']),bool(r['cells']['G']),bool(r['cells']['GT'])))+' |')
        missing={s['id'] for s in report['M']};existing={s['id']:s for s in report['E']}
        lines+=['','### 异常、已有覆盖及缺失原因','']
        for s in report['G']:
            links=[p['generated_scenario_id'] for p in report['full_matches'] if p['checker_scenario_id']==s['id']]
            lines+=['- **'+s['id']+'**：'+s['object']+' / '+s['cause']+'（'+defs[s['concern_key']]['label']+'）',
              '  - 正常交互：'+'；'.join(s['steps']['normal_context']), '  - 异常触发：'+s['steps']['trigger'],
              '  - 后续行为：'+('；'.join(x['action'] for x in s['steps']['documented_follow_up']) or '待确认，未补造'),
              '  - 已有覆盖：'+('；'.join(x+': '+existing[x]['cause'] for x in links) or '无完整对应'),
              '  - 缺失原因：'+('对象、操作、原因及必要条件未与已有分支完整对应' if s['id'] in missing else '已有完整对应'),
              '  - 继承来源：'+'；'.join(' → '.join(defs[k]['label'] for k in path) for path in s.get('concern_paths',[])),
              '  - 来源：'+json.dumps(s['source_refs'],ensure_ascii=False)]
        lines+=['','### 原文分支与覆盖细项','']
        for b in report.get('original_branches',[]):
            eids={s['id'] for s in report['E'] if s.get('original_branch_id')==b['id']}
            hits={p['checker_scenario_id'] for p in report['full_matches'] if p['generated_scenario_id'] in eids}
            lines.append('- '+b['id']+'：'+b['description']+'；覆盖细项：'+('、'.join(sorted(hits)) or '暂无完整覆盖'))
        lines+=['','### 文档已有异常','']
        for s in report['E']:lines.append('- '+s['id']+'：'+s['cause']+'；'+'；'.join(s['conditions']))
        lines+=['','### 待确认','']
        for x in report['pending']:lines.append('- '+x['interaction_id']+'：'+x['reason'])
        lines.append('')
    global_result=combined.get('global',{})
    if global_result:
        lines+=['## 全局业务依赖（项目级，不按关联用例重复计数）','']
        dependencies=global_result.get('business-dependencies',{}).get('dependencies',[])
        lines+=['| 依赖ID | 类型 | 前置用例 | 后续用例 | 来源实体 | 目标实体 |','| --- | --- | --- | --- | --- | --- |']
        for dep in dependencies:
            lines.append('| '+' | '.join(cell(dep.get(k,'')) for k in ('id','dependency_type','from_case_id','to_case_id','from_entity_id','to_entity_id'))+' |')
        for title,key in (('关注点层','global-concern-compare'),('场景层','global-scenario-compare')):
            result=global_result.get(key,{})
            lines+=['',f'### {title} E/G/GT 对照','','| 依赖 | 对象 | 关注点或失败条件 | E | G | GT | 缺失 |','| --- | --- | --- | --- | --- | --- | --- |']
            for row in result.get('rows',[]):
                anchor=row['anchor'];label=anchor.get('concern_key') or anchor.get('cause','')
                lines.append('| '+' | '.join(cell(x) for x in (anchor['dependency_id'],anchor['object'],label,row['cells']['E'] or '',row['cells']['G'] or '',row['cells']['GT'] or '',row['missing']))+' |')
        metrics=global_result.get('global-evaluation',{}).get('metrics',{})
        lines+=['','### 全局指标','','| 指标 | 分子 | 分母 | 结果 |','| --- | ---: | ---: | ---: |']
        for name,metric in metrics.items():
            lines.append('| '+' | '.join(cell(x) for x in (name,metric.get('numerator'),metric.get('denominator'),metric.get('value') if metric.get('value') is not None else metric.get('status','未评测')))+' |')
        lines.append('')
    (root/'missing_report.md').write_text('\n'.join(lines),encoding='utf8')
