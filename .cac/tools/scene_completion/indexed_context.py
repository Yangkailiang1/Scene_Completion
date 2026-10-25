"""Indexed model contexts; expand references from trusted inputs, never model-written quotes."""
from copy import deepcopy
import re
from .storage import fingerprint
from .source_documents import documents_in,evidence_refs
from .contracts import REF

VERSION='indexed-evidence-v1'


def markdown_index(documents):
    result=[]
    for d in documents:
        rows=d['lines'];headings=[]
        for n,row in enumerate(rows):
            m=re.match(r'^\s*(#{1,6})\s+(.+)',row['text'])
            if m:headings.append((n,len(m[1]),m[2]))
        sections=[]
        for n,level,title in headings:
            stop=next((m for m,l,_ in headings if m>n and l<=level),len(rows))
            excluded=any(m<=n<next((p for p,l,_ in headings if p>m and l<=lev),len(rows)) and ('变更前' in label or '非抽取权威' in label or '关联实现接口OpenAPI文件' in label or 'before change' in label.lower()) for m,lev,label in headings)
            sections.append({'id':'section-'+fingerprint([d['source_id'],rows[n]['number'],title])[:16],
              'title':title,'level':level,'line_start':rows[n]['number'],'line_end':rows[stop-1]['number'],'default_input':not excluded})
        result.append({'source_id':d['source_id'],'name':d['name'],'channel':d['channel'],'content_hash':fingerprint(rows),'line_count':len(rows),'sections':sections})
    return {'schema':'markdown-context-index-v1','documents':result}


def select_indexed_sections(documents,index,section_ids):
    wanted=set(section_ids);spans={};found=set()
    for d in index['documents']:
        for section in d['sections']:
            if section['id'] in wanted:
                spans.setdefault(d['source_id'],[]).append((section['line_start'],section['line_end']));found.add(section['id'])
    if wanted!=found:raise ValueError('unknown source section ID; context cannot fall back to the full document')
    out=[]
    for d in documents:
        rows=[deepcopy(r) for r in d['lines'] if any(a<=r['number']<=b for a,b in spans.get(d['source_id'],[]))]
        if rows:out.append({**d,'lines':rows})
    return out


class EvidenceContext:
    def __init__(self,packet):
        self.original=packet;self.pool={};self.components={};self.names={};self.normalizations=[]
        self.source_layers={}
        if packet['task']=='fused-ssd':
            for layer in ('RR','SR'):
                for doc in packet['input'][layer]:self.source_layers.setdefault(doc['source_id'],set()).add(layer)
        inputs=deepcopy(packet['input'])
        if 'registry' in inputs:
            if packet['task']=='existing-bind':inputs.pop('registry')
            else:
                reg=inputs['registry'];rows=inputs.get('fused-ssd',{}).get('interactions',[])
                rows+=inputs.get('rr-ssd',{}).get('interactions',[])+inputs.get('sr-ssd',{}).get('interactions',[])
                kinds={k for i in rows for k in i['operation']['kinds']}
                for rule in inputs.get('normal-rules',{}).get('rules',[]):kinds.update(rule['functional_kinds'])
                referenced={r['concern_key'] for r in inputs.get('normal-rules',{}).get('rules',[])}
                defs={k:v for k,v in reg['definitions'].items() if k in referenced or not kinds or not v['operation_kinds'] or kinds&set(v['operation_kinds'])}
                # Historical migrations and unrelated capability categories are
                # audit metadata, not model context for this actual operation.
                inputs['registry']={k:reg[k] for k in ('version','hash')}
                inputs['registry']['definitions']=defs
        from .task_context import semantic_view
        inputs=semantic_view(packet['task'],inputs)
        self.fused=packet['task']=='fused-ssd'
        if not self.fused and 'components' in inputs and ('rr-ssd' in inputs or 'fused-ssd' in inputs):
            rows=inputs.get('fused-ssd',{}).get('interactions',[])+inputs.get('rr-ssd',{}).get('interactions',[])+inputs.get('sr-ssd',{}).get('interactions',[])
            parties=[i[side] for i in rows for side in ('sender','receiver')]
            names={p['name'] for p in parties};ids={p.get('component_id') for p in parties};ids.discard(None)
            components=inputs['components']['components'];ids.update(c['id'] for c in components if c['name'] in names)
            while True:
                parents={c['parent_id'] for c in components if c['id'] in ids and c.get('parent_id')}
                if parents<=ids:break
                ids.update(parents)
            inputs['components']={'components':[c for c in components if c['id'] in ids],'relations':[r for r in inputs['components'].get('relations',[]) if r['from_id'] in ids and r['to_id'] in ids]}
        if not self.fused and 'api-map' in inputs:
            api_ids={a['id'] for a in inputs.get('api-parameters',inputs.get('normal-constraints',{})).get('apis',[])}
            inputs['api-map']={'services':[{**s,'interfaces':[a for a in s['interfaces'] if a['id'] in api_ids]} for s in inputs['api-map']['services'] if any(a['id'] in api_ids for a in s['interfaces'])]}
        if self.fused:
            inputs['case-group']={'id':inputs['case-group']['id']}
            comps=inputs['components']['components']
            self.components={c['id']:c for c in comps if c['composition_type']!='用例'}
            for c in self.components.values():self.names.setdefault(c['name'],[]).append(c['id'])
            # SSD needs identities, not the entire composition relation graph,
            # every use-case node, and their repeated evidence quotations.
            inputs['components']={'components':[{k:c[k] for k in ('id','name','composition_type','parent_id')} for c in self.components.values()]}
        self.doc_refs=set()
        for doc in documents_in(inputs):
            for row in doc['lines']:
                if not row['text'].strip():continue
                ref={'source_id':doc['source_id'],'line_start':row['number'],'line_end':row['number'],'quote':row['text']}
                rid=self.register(ref);row['evidence_id']=rid;self.doc_refs.add(rid)
        for r in evidence_refs(inputs):self.register(r)
        self.input=self.encode(inputs)
        self.input['evidence_catalog']={k:v for k,v in self.pool.items() if k not in self.doc_refs}
        self.packet=deepcopy(packet);self.packet['input']=self.input
        if 'tool_rule_coverage' in self.packet:
            keys={'interaction_id','object','concern_key','field','cause','conditions','rule_id','data_location','reason'}
            self.packet['tool_rule_coverage']={k:[{a:b for a,b in row.items() if a in keys} for row in rows] for k,rows in packet['tool_rule_coverage'].items()}
        self.packet['output_schema']=self.schema(packet['output_schema'])
        if packet['task']=='normal-rules':
            from .contracts import registry
            fields=self.packet['output_schema']['properties']['rules']['items']['properties']
            fields['concern_key']={'enum':[k for k,v in registry()['definitions'].items() if v.get('enabled',True) and v['kind']=='check']}
            fields['interaction_id']={'enum':[i['id'] for i in packet['input']['fused-ssd']['interactions'] if i['direction']=='request']}
            fields['owner_service']={'enum':list({i['receiver']['name'] for i in packet['input']['fused-ssd']['interactions'] if i['direction']=='request'})}
            fields['violation']={'type':'string','minLength':1,'pattern':r'^(?!.*(?:或|\bor\b)).+$'}
            self.packet['output_schema']['properties']['rules']['items']['allOf']=[{'if':{'properties':{'concern_key':{'pattern':r'^api\.data\.'}}},'then':{'properties':{'fields':{'type':'array','minItems':1,'maxItems':1,'items':{'type':'string'}}}}}]
            fields.pop('condition',None)
            self.packet['output_schema']['properties']['rules']['items']['required'].remove('condition')
            self.packet['instructions']+='\n不输出condition。正常条件由程序从你选择的source_refs恢复原文；只判断独立violation、责任服务、字段、关注点和功能类别。引用必须直接支持该反面条件。独立原因逐条输出，不用或连接。'
        if packet['task']=='semantic-compare' and packet['input'].get('candidate_pairs'):
            self.packet['output_schema']['properties']['decisions']['items']['anyOf']=[
              {'properties':{k:{'const':v} for k,v in pair.items()}} for pair in packet['input']['candidate_pairs']]
        if packet['task']=='concern-match':
            fields=self.packet['output_schema']['properties']['matches']['items']
            for key in ('status','status_reason','inheritance_paths','service','functional_types','technologies'):fields['properties'].pop(key,None)
        if packet['task'] in {'exception-generate','existing-extract','test-ground-truth'}:
            fields=self.packet['output_schema']['properties']['scenarios']['items']
            from .normal_rules import LOCATIONS
            fields['properties']['data_location']={'enum':sorted(LOCATIONS)+[None]}
            for key in ('concern_origins','concern_paths','canonical_interaction_id','interaction_type'):fields['properties'].pop(key,None)
            if packet['task']=='existing-extract':
                from .inverse_alignment import broad_input_branch
                branches=packet['input'].get('branches',{}).get('branches',[])
                if branches and not any(broad_input_branch(b['description']) for b in branches):
                    fields['properties']['coverage_kind']={'const':'exact'}
                    self.packet['instructions']+='\n本分支不是宽泛参数非法分支：coverage_kind只能为exact。不要把具体原因扩大为全部输入参数错误。'
            if packet['task']=='exception-generate':
                # G is always inferred from positive rules. It cannot claim an
                # original exception branch or broad E-coverage semantics.
                for key in ('source_status','original_branch_id','coverage_kind'):
                    fields['properties'].pop(key,None)
                    if key in fields['required']:fields['required'].remove(key)
                fields['properties']['derivation']={'type':'string','minLength':1}
                candidates=inputs['concern-match']['matches']
                if candidates:fields['anyOf']=[{'properties':{**{k:{'const':m[k]} for k in ('interaction_id','object','concern_key')},
                  **({'field':{'type':'null'}} if not m['concern_key'].startswith('api.data.') else {})}} for m in candidates]
                else:self.packet['output_schema']['properties']['scenarios']['maxItems']=0
        if self.fused:
            props=self.packet['output_schema']['properties']['interactions']['items']
            for k in ('sender','receiver'):props['properties'][k]={'type':'object','properties':{'component_id':{'enum':list(self.components)}},'required':['component_id'],'additionalProperties':False}
            props['properties'].pop('case_id');props['required'].remove('case_id')
            props['properties'].pop('sequence');props['required'].remove('sequence')
            props['properties']['reply_to']=props['properties'].pop('parent_id');props['required'].remove('parent_id')
            props['properties']['operation']['required']=['name']
            props['allOf']=[{'if':{'properties':{'direction':{'const':direction}}},'then':{'properties':{**({'reply_to':{'type':'null'}} if direction=='request' else {}),'data':{'properties':{'sequence':{'items':{'properties':{'location':{'enum':locations}}}}}}}}} for direction,locations in [('request',['header','path','query','body','business']),('return',['response','business'])]]
            # Data attributes that have not yet been associated by the API tool
            # are omitted, not regenerated as repeated null placeholders.
            p=props['properties']['data']['properties']['sequence']['items'];p['required']=['name','location']
            for key in ('data_type','required','default'):p['properties'].pop(key)
            link=self.packet['output_schema']['properties'].pop('rr_sr_links')
            lp=link['items'];lp['properties']['rr_message_id']=lp['properties'].pop('rr_id');lp['properties']['sr_message_ids']=lp['properties'].pop('sr_ids')
            lp['required']=['rr_message_id' if k=='rr_id' else 'sr_message_ids' if k=='sr_ids' else k for k in lp['required']]
            self.packet['output_schema']['properties']['refinements']=link
            self.packet['output_schema']['required']=['refinements' if k=='rr_sr_links' else k for k in self.packet['output_schema']['required']]
        if 'repair' in self.packet and 'candidate' in self.packet['repair']:
            candidate=self.safe_candidate(self.packet['repair']['candidate'])
            self.packet['repair']['candidate']=candidate if self.packet['repair'].get('candidate_format')=='model' else self.encode_output(candidate)
            self.input['evidence_catalog']={k:v for k,v in self.pool.items() if k not in self.doc_refs}
        self.packet['instructions']+='\n模型传输契约 '+VERSION+'：source_refs只输出给定evidence_id字符串，不能复写引文、source_id或行号；程序从原始输入恢复引用。文档行标有[evidence_id]；派生产物引用见evidence_catalog。所有事实字段仍须有依据。'
        if packet['task']=='concern-match':
            self.packet['instructions']+='\n只返回需语义理解的额外匹配依据，不输出status/status_reason/inheritance_paths/service/functional_types/technologies，这些由工具按原始正常约束确定。未知规则列pending，不能声称适用。基础继承和字段规则由工具补齐，不重复列出。'
        if packet['task']=='exception-generate':
            self.packet['instructions']+='\nG只能从正向规则推导。不要输出source_status、original_branch_id、coverage_kind，程序固定为framework_inferred、null、exact；derivation必须写明当前正常规则如何推出异常，不能留空。'
        if self.fused:
            self.packet['instructions']+='\nRR消息只使用RR-或DUAL-证据；SR消息只使用SR-或DUAL-证据；META-只作组件身份依据，不能当消息动作事实。'
            self.packet['instructions']+='\nSSD职责只限本用例交互与RR/SR消息对应。sender/receiver仅输出组件component_id，不重复名称和位置；不输出case_id，程序填当前对应组ID。数据只写本次实际传递的字段名和位置，不展开items数组内部对象字段；类型、默认值、必填性、约束由独立API参数任务及交互属性关联工具补齐。仅本用例额外明示的值/条件才在data中补充。source_refs在消息级提供一次，operation和各数据字段仅有额外不同依据时补充；程序默认使用消息依据。refinements.rr_message_id和sr_message_ids只能引用本次输出的交互消息id，不是用例编号。每条RR消息至多一个refinements项。request不输出reply_to，父调用由工具按实际端点和顺序确定；return的reply_to指向本层端点完全反向的原请求id。跨层对应只放refinements，不能放reply_to。RR和SR都保留明示的业务结果返回，不能只建RR入口请求。不要填空数组/空值占位可选属性。本地处理放入operation.sequence。'
            self.packet['instructions']+='\n按实际先后顺序输出interactions数组，层内sequence由程序编号，不要填写。request不输出reply_to；即使误填，工具也不采用此提示建立关系。request必须识别operation.kinds（read/create/update/delete/display/process/publish/external_call）；return不填写kinds，由工具继承原请求操作类别，return是方向而不是功能类别。数据字段不填写data_type/required/default，这三项由API属性关联工具补齐。'

    def register(self,ref):
        layers=self.source_layers.get(ref['source_id'],set())
        prefix=('DUAL-' if len(layers)>1 else next(iter(layers))+'-' if layers else 'META-') if self.fused else ''
        rid=prefix+'e'+fingerprint(ref)[:12]
        if rid in self.pool and self.pool[rid]!=ref:raise ValueError('evidence ID collision')
        self.pool[rid]=deepcopy(ref);return rid

    def safe_candidate(self,value):
        from .source_documents import validate_evidence
        docs=documents_in(self.original['input']);allowed={fingerprint(r) for r in evidence_refs(self.original['input'])}
        def visit(v,key=None):
            if key=='source_refs':
                keep=[]
                if not isinstance(v,list):return keep
                for r in v:
                    if isinstance(r,str):
                        if r in self.pool:keep.append(r)
                        continue
                    if not isinstance(r,dict) or set(r)!=set(REF['properties']):continue
                    try:
                        if fingerprint(r) not in allowed:
                            if not docs:continue
                            validate_evidence(r,docs)
                        keep.append(r)
                    except (ValueError,KeyError,TypeError):pass
                return keep
            if isinstance(v,dict):return {k:visit(x,k) for k,x in v.items()}
            if isinstance(v,list):return [visit(x) for x in v]
            return v
        return visit(deepcopy(value))

    def encode(self,value):
        if isinstance(value,dict):
            if set(value)==set(REF['properties']):return self.register(value)
            return {k:self.encode(v) for k,v in value.items()}
        if isinstance(value,list):return [self.encode(v) for v in value]
        return value

    def schema(self,value):
        if value==REF:return {'type':'string','pattern':r'^(?:(?:RR|SR|META|DUAL)-)?e[0-9a-f]{12}$','description':'Exact evidence_id from this task input'}
        if isinstance(value,dict):return {k:self.schema(v) for k,v in value.items()}
        if isinstance(value,list):return [self.schema(v) for v in value]
        return value

    def encode_output(self,value):
        result=self.encode(value)
        if self.original['task'] in {'exception-generate','existing-extract','test-ground-truth'}:
            for row in result.get('scenarios',[]):
                for k in ('concern_origins','concern_paths','canonical_interaction_id','interaction_type'):row.pop(k,None)
                if self.original['task']=='exception-generate':
                    for k in ('source_status','original_branch_id','coverage_kind'):row.pop(k,None)
            from .normal_rules import normalize_scenarios
            result=normalize_scenarios(result,self.original['input'],truth=self.original['task']=='test-ground-truth')
        if self.original['task']=='concern-match':
            for row in result.get('matches',[]):
                for k in ('status','status_reason','inheritance_paths','service','functional_types','technologies'):row.pop(k,None)
        if self.fused:
            for row in result.get('interactions',[]):
                row.pop('case_id',None)
                row.pop('sequence',None)
                row['reply_to']=row.pop('parent_id',None)
                for role in ('sender','receiver'):
                    matches=self.names.get(row[role].get('name'),[])
                    if len(matches)==1:row[role]={'component_id':matches[0]}
                if row.get('direction')=='return':row['operation'].pop('kinds',None)
                for p in row.get('data',{}).get('sequence',[]):
                    for k in ('data_type','required','default'):p.pop(k,None)
            if 'rr_sr_links' in result:result['refinements']=[{('rr_message_id' if k=='rr_id' else 'sr_message_ids' if k=='sr_ids' else k):v for k,v in link.items()} for link in result.pop('rr_sr_links')]
        return result

    def expand(self,value):
        def decode(v,key=None):
            if key=='source_refs':
                if not isinstance(v,list) or any(not isinstance(r,str) or r not in self.pool for r in v):raise ValueError('unknown evidence_id; select only IDs supplied in this task input')
                return [deepcopy(self.pool[r]) for r in v]
            if isinstance(v,dict):return {k:decode(x,k) for k,x in v.items()}
            if isinstance(v,list):return [decode(x) for x in v]
            return v
        result=decode(value)
        if self.original['task']=='normal-rules':
            from .normal_rules import identity_concern,separate_unknown_criteria,separate_foreign_checks
            rows={i['id']:i for i in self.original['input']['fused-ssd']['interactions']}
            for r in result.get('rules',[]):
                if r['interaction_id'] in rows:
                    key=identity_concern(r['concern_key'],rows[r['interaction_id']])
                    if key!=r['concern_key']:
                        self.normalizations.append({'rule_id':r['id'],'field':'concern_key','original_value':r['concern_key'],'value':key,'action':'apply confirmed human/service caller taxonomy; no change to trigger or evidence'})
                        r['concern_key']=key
                r['condition']=' '.join(ref['quote'] for ref in r['source_refs'])
                self.normalizations.append({'rule_id':r['id'],'field':'condition','action':'restore verbatim positive condition from selected source evidence, no generated quote'})
            result=separate_unknown_criteria(result,self.normalizations)
            result=separate_foreign_checks(result,self.original['input'],self.normalizations)
        if self.original['task']=='semantic-compare':
            from .comparison_batches import restrict_candidate_decisions
            result=restrict_candidate_decisions(result,self.original['input'],self.normalizations)
        if self.original['task'] in {'exception-generate','existing-extract','test-ground-truth'}:
            for row in result.get('scenarios',[]):
                for k in ('concern_origins','concern_paths','canonical_interaction_id','interaction_type'):row.pop(k,None)
                if self.original['task']=='exception-generate':
                    row.update(source_status='framework_inferred',original_branch_id=None,coverage_kind='exact')
                    if not row['concern_key'].startswith('api.data.') and row.get('field') is not None:
                        self.normalizations.append({'scenario_id':row['id'],'field':'field','original_value':row['field'],'action':'party/operation concern uses object as unit; field annotations are not independent data exceptions'})
                        row['field']=None
        if self.original['task']=='concern-match':
            from .concern_hierarchy import resolve_matches
            resolved=resolve_matches(self.original['input'],result.get('matches',[]))
            result={'matches':resolved['matches'],'pending':result.get('pending',[])+resolved['pending']}
        if self.original['task']=='test-operation-project':
            # Test rows also contain failure conditions and expected answers.
            # Only the literal operation-name slice may leave this channel.
            for obj in result.get('objects',[]):
                for op in obj['supported_operations']:
                    for ref in op['source_refs']:
                        if op['name'] not in ref['quote']:raise ValueError('test operation name is not a literal slice of its cited evidence')
                        ref['quote']=op['name']
        if self.fused:
            if 'refinements' in result:result['rr_sr_links']=[{('rr_id' if k=='rr_message_id' else 'sr_ids' if k=='sr_message_ids' else k):v for k,v in link.items()} for link in result.pop('refinements')]
            orders={};by_id={i['id']:i for i in result.get('interactions',[])}
            for row in result.get('interactions',[]):
                layer=row['layer'];orders[layer]=orders.get(layer,0)+1;row['sequence']=orders[layer]
                row['case_id']=self.original['input']['case-group']['id']
                row['parent_id']=row.pop('reply_to',None)
                if row['direction']=='request':
                    if row['parent_id'] is not None:self.normalizations.append({'message_id':row['id'],'field':'reply_to','action':'ignored request-only transport hint; parent is independently derived from actual endpoints/order'})
                    row['parent_id']=None
                for role in ('sender','receiver'):
                    cid=row[role].get('component_id');c=self.components.get(cid)
                    if c is None:raise ValueError('unknown SSD component_id; do not invent a service')
                    row[role]={'name':c['name'],'position':c['composition_type'],'source_refs':deepcopy(c['source_refs'])}
                for p in row.get('data',{}).get('sequence',[]):
                    for key,default in [('data_type',None),('required',None),('default',None),('constraints',[]),('source_refs',row.get('source_refs',[]))]:p.setdefault(key,deepcopy(default))
                for key,default in [('sequence',[]),('optional',[]),('source_refs',row.get('source_refs',[]))]:row['operation'].setdefault(key,deepcopy(default))
            for row in result.get('interactions',[]):
                if row['direction']=='return':
                    parent=by_id.get(row['parent_id'])
                    if not parent or parent['direction']!='request':raise ValueError('return.reply_to must reference a request message ID in this result')
                    row['operation']['kinds']=deepcopy(parent['operation'].get('kinds',[]))
                elif not row['operation'].get('kinds'):raise ValueError('request.operation.kinds must identify the actual business operation category')
            from .ssd_tools import complete_structure
            result=complete_structure(result,self.normalizations)
        return result


def task_document_view(documents,intent):
    """Deterministic, inspectable retrieval from the Markdown section index.

    Catalogs consume headings/identity metadata; API mapping consumes interface
    identity/routing declarations. Positive flow bodies remain with the SSD
    task. Unknown large formats fail for review rather than reverting to full.
    """
    from .scheduler import TaskBlocked
    out=[];index=markdown_index(documents)
    for d,entry in zip(documents,index['documents']):
        rows=d['lines'];chosen=set();mapping_table=False;in_table=False
        if sum(len(r['text'].encode()) for r in rows)<=4096:
            out.append(deepcopy(d));continue
        for row in rows:
            text=row['text'];head=re.match(r'^\s*#{1,6}\s+(.+)',text)
            table_row=text.lstrip().startswith('|')
            if table_row and not in_table:
                mapping_table=bool(re.search(r'接口名称|API名称|interface\s*name',text,re.I) and re.search(r'方法|路径|method|path',text,re.I))
            in_table=table_row
            path=[s['title'] for s in entry['sections'] if s['line_start']<=row['number']<=s['line_end']]
            in_case=any(re.search(r'用例|use[ -]?case',t,re.I) for t in path)
            if intent=='catalogue':
                keep=bool(head and (in_case or text.lstrip().startswith('# '))) or (in_case and text.lstrip().startswith('|')) or bool(re.search(r'Actor\s*[:：]|参与者\s*[:：]|用例(?:编号|名称|ID)\s*[:：]',text,re.I))
            elif intent=='api-map':
                keep=bool(head) or bool(re.search(r'(?:API|接口)\s*(?:编号|名称|ID)|所属服务|服务名称|方法[/／]路径|资源路径|影响范围|(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/',text,re.I))
                # Preserve interface catalog rows as a table block, not only its header.
                if table_row and mapping_table:keep=True
            elif intent=='components':
                keep=bool(head) or bool(re.search(r'Actor|参与者|所属服务|周边|系统|服务|数据库|调用|接口|Service|Database|LLM',text,re.I))
                if text.lstrip().startswith('|') and any(re.search(r'系统上下文|组成|交互方|用例清单|场景划分|基本信息|资源清单',t) for t in path):keep=True
            else:raise ValueError('unknown document context intent')
            if keep:chosen.add(row['number'])
        # Short unstructured inputs are safe to carry intact and explicitly
        # annotated by the caller's audit. Large unindexed inputs need review.
        if not entry['sections']:
            if sum(len(r['text'].encode()) for r in rows)>4096:raise TaskBlocked('awaiting_context',{'reason':'大文档没有可识别章节，请先确认文档索引和任务取片范围','source_id':d['source_id'],'intent':intent})
            chosen={r['number'] for r in rows}
        out.append({**d,'lines':[deepcopy(r) for r in rows if r['number'] in chosen]})
    return out


def catalogue_context(documents,source_index=None):
    view=task_document_view(documents,'catalogue')
    entries={d['source_id']:d for d in (source_index or markdown_index(documents))['documents']}
    index={'schema':'markdown-context-index-v1','documents':[deepcopy(entries[d['source_id']]) for d in documents]}
    # When a spec includes both a brief catalogue and formal case details,
    # the explicit 用例编号 record identifies the authoritative detail block.
    # Never bind a case to its same-named summary just because it appears first.
    for d,entry in zip(view,index['documents']):
        original=next(x for x in documents if x['source_id']==d['source_id'])
        roots=[]
        for row in original['lines']:
            m=re.match(r'^\s*\|\s*(?:用例编号|用例ID|Use\s*case\s*ID)\s*\|\s*([^|]+)\|',row['text'],re.I)
            if not m:continue
            identifier=m[1].strip().strip('`* ')
            parents=[s for s in entry['sections'] if s['line_start']<=row['number']<=s['line_end'] and identifier in s['title']]
            if not parents:continue
            root=max(parents,key=lambda s:s['level'])
            if root not in roots:roots.append(root)
        if roots:
            selected=[]
            for row in original['lines']:
                root=next((s for s in roots if s['line_start']<=row['number']<=s['line_end']),None)
                if not root:continue
                path=[s['title'] for s in entry['sections'] if s['line_start']<=row['number']<=s['line_end']]
                if row['number']==root['line_start'] or (row['text'].lstrip().startswith('|') and any('基本信息' in t for t in path)) or any(re.search(r'参与者|actors?',t,re.I) for t in path):selected.append(deepcopy(row))
            d['lines']=selected;entry['sections']=roots
        else:
            allowed={r['number'] for r in d['lines'] if re.match(r'^\s*#{1,6}\s+',r['text'])}
            entry['sections']=[s for s in entry['sections'] if s['line_start'] in allowed]
    return {'documents':view,'source-index':index}
