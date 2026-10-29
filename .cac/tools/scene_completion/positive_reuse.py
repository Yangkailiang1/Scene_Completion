"""Input/contract-bound positive reuse across project rule versions; never E/GT."""
from copy import deepcopy
from pathlib import Path
from .storage import read_json,write_json,fingerprint
from .contracts import schema
from .source_documents import read_project_documents

ALLOWED={'components','api-map','api-parameters','use-case-extract','use-case-align','fused-ssd','normal-rules','test-operation-project'}

def normalized_skill(text):return text.replace('推荐任务始终停用。','推荐仅由风险保底工具在缺失M就绪后执行。').strip()

def input_identity(value):
    # Document display names are not semantic material. Preserve every actual
    # line, source identity, case, object, operation, constraint and registry.
    def clean(v):
        if isinstance(v,list):return [clean(x) for x in v]
        if isinstance(v,dict):
            out={k:clean(x) for k,x in v.items() if not (k=='name' and 'source_id' in v and 'lines' in v)}
            if {'RR','SR','case-group'}<=v.keys() and v['case-group'].get('status')=='confirmed':
                out['case-group']={k:x for k,x in out['case-group'].items() if k not in {'reason','source_refs'}}
            return out
        return v
    return fingerprint(clean(value))

def compatible_skill(task,old,new,inputs):
    if old==normalized_skill(new):return True
    # Explicit compatibility for the release's Mermaid-only clarification.
    # It does not affect a plain-text API extraction; a Mermaid input must be redone.
    if task=='api-map':
        import re,json
        text=json.dumps(inputs,ensure_ascii=False)
        if re.search(r'sequenceDiagram|->>|-->>|<br\s*/?>',text,re.I):return False
        marker='Markdown中的Mermaid时序图与普通段落同样可作为来源。'
        trimmed='\n'.join(line for line in normalized_skill(new).splitlines() if not line.startswith(marker)).strip()
        return old==trimmed
    return False

def prepare(old,new):
    from . import use_cases  # registers the extended public extraction contracts
    old,new=Path(old),Path(new);a,b=read_json(old/'project.json'),read_json(new/'project.json');mapping={}
    # Changing independent tests must not invalidate unchanged RR/SR extraction.
    # Test-dependent seeds still require their actual scoped input hash to match.
    for role in ('RR','SR','test'):
        same=len(a['sources'][role])==len(b['sources'][role]) and all((old/x['path']).read_bytes()==(new/y['path']).read_bytes() for x,y in zip(a['sources'][role],b['sources'][role]))
        if not same:
            if role!='test':return
            continue
        x=read_project_documents(old,a['sources'][role],'test' if role=='test' else 'existing');y=read_project_documents(new,b['sources'][role],'test' if role=='test' else 'existing')
        mapping.update({i['source_id']:j['source_id'] for i,j in zip(x,y)})
    def rebind(v):
        if isinstance(v,list):return [rebind(x) for x in v]
        if isinstance(v,dict):return {k:mapping.get(x,x) if k=='source_id' and isinstance(x,str) else rebind(x) for k,x in v.items()}
        return v
    packets={}
    for f in (old/'run/packets').glob('*.json'):
        q=read_json(f);packets[(q.get('task'),fingerprint(q.get('input')))]=q
    state=read_json(old/'run/workflow_tasks.json').get('tasks',{}) if (old/'run/workflow_tasks.json').exists() else {};seeds=[]
    for key,r in state.items():
        if r.get('status')!='passed' or r.get('stage') not in ALLOWED:continue
        f=(old/'run'/r['output_file']).resolve()
        if not f.is_relative_to((old/'run').resolve()):continue
        v=read_json(f);q=packets.get((v['task'],v.get('metadata',{}).get('input_hash')))
        if not q or q.get('output_schema')!=schema(v['task']):continue
        seeds.append({'task':v['task'],'skill':normalized_skill(q.get('skill_text','')),'schema_hash':fingerprint(schema(v['task'])),'input_hash':input_identity(rebind(q['input'])),'payload':rebind(v['payload']),'source_project':a['id'],'source_key':key,'source_output_hash':fingerprint(v)})
    write_json(new/'run/positive_reuse.json',{'source_project':a['id'],'policy':'unchanged source bytes and public contract; revalidate actual task scope and evidence before reuse','seeds':seeds})

def find(root,task,inputs,scope,skill):
    from . import use_cases
    from .validation import validate_result
    if task not in ALLOWED:return None
    file=Path(root)/'positive_reuse.json'
    if not file.exists():return None
    for row in read_json(file)['seeds']:
        if row.get('input_hash')!=input_identity(inputs):continue
        if row['task']!=task or row['schema_hash']!=fingerprint(schema(task)) or not compatible_skill(task,row['skill'],skill,inputs):continue
        v=deepcopy(row['payload'])
        if task=='api-parameters' and inputs.get('interface'):v={'apis':[a for a in v['apis'] if a['id']==inputs['interface']['id']]}
        if task=='fused-ssd' and (not scope or any(i['case_id'] not in scope for i in v['interactions'])):continue
        try:validate_result(task,v,inputs)
        except (ValueError,KeyError,TypeError):continue
        return v,{k:row[k] for k in ('source_project','source_key','source_output_hash')}
    return None
