#!/usr/bin/env python3
"""Offline first-interaction memory example. No API/model/embedding execution."""
from pathlib import Path
import argparse
import sys
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.cac/tools'))
from scene_completion.ppt_contracts import registry
from scene_completion.ppt_method import (complete_data_matches,data_exceptions,compare_report,
                                        capability_union,bind_resource_services)
from scene_completion.ppt_runner import Execution
from scene_completion.ppt_exports import export_task
from scene_completion.ppt_sources import read_documents
from scene_completion.semantic_backend import write_json
from scene_completion.case_dag import run_lock


def inputs():
    docs=read_documents([Path(__file__).with_name('memory-normal.md')],'normal')
    source=docs[0]['source_id']
    def refs(line):return [{'source_id':source,'line_start':line,'line_end':line,'quote':docs[0]['lines'][line-1]['text']}]
    def parameter(name,location,required,line,dtype=None,default=None,rules=()):
        return {'name':name,'location':location,'required':required,'data_type':dtype,'default':default,'source_refs':refs(line),
          'constraints':[{'id':name+'-'+kind,'kind':kind,'value':value,'status':'explicit','source_refs':refs(line)} for kind,value in rules]}
    params=[parameter('x-wisecloud-service-id','header',True,4),parameter('memoryInstanceID','path',True,5),
      parameter('memoryType','query',False,6,rules=[('enum',['PROFILE','SEMANTIC'])]),
      parameter('page','query',False,7,dtype='integer',default=1,rules=[('minimum',1)]),
      parameter('pageSize','query',False,8,dtype='integer',default=20,rules=[('minimum',1),('maximum',100)])]
    api={'id':'API-M-IF2','name':'查询记忆库列表','address':'/ms/v1/memory-instances/{memoryInstanceID}/mem-repos','parameters':params,'source_refs':refs(3)}
    components=[]
    for cid,name,kind,line in [('dev','开发者','外部Actor（人类）',2),('ui','开发者UI/前端','UI/前端',2),
      ('platform','WiseCloudMemoryPlatformService','系统边界',2),('query','查询记忆库列表','用例',2),('db','Gaussdb4MySQL','外部数据库',9)]:
        components.append({'id':cid,'name':name,'composition_type':kind,'parent_id':None,'source_status':'explicit','source_refs':refs(line)})
    i={'id':'SC002-UC002-step1','case_id':'SC002-UC002','sequence':1,'parent_id':None,'layer':'RR',
       'sender':{'name':'开发者','position':'外部Actor（人类）','source_refs':refs(2)},
       'receiver':{'name':'WiseCloudMemoryPlatformService','position':'系统边界','source_refs':refs(2)},
       'operation':{'name':'查询记忆库列表','kinds':['read'],'sequence':['查询记忆库列表'],'optional':[],'source_refs':refs(2)},
       'data':{'sequence':deepcopy(params)},'direction':'request','api_id':None,'source_refs':refs(2)}
    model={'components':{'components':components,'relations':[]},'rr-ssd':{'interactions':[i]},'sr-ssd':{'interactions':[]},
      'api-map':{'services':[{'name':'WiseCloudMemoryPlatformService','interfaces':[{'id':api['id'],'name':api['name'],'method':None,'address':api['address'],'source_refs':refs(3)}],'source_refs':refs(2)}]},
      'api-parameters':{'apis':[api]},'registry':registry()}
    # Parties are supplied as a frozen illustrative semantic response, not an
    # executed inference. Unknown data constraints are added to pending by code.
    matches=[]
    for target,key,rule,line in [('sender','human.authentication','调用者身份必须通过认证',10),
      ('sender','human.authorization','只允许有权限的开发者查询',11),
      ('receiver','service.query_retrieval.resource_existence','指定记忆实例必须存在',12),
      ('receiver','service.query_retrieval.result_correctness','返回符合查询条件的正确列表',13),
      ('receiver','service.query_retrieval.data_visibility','只返回调用者可见的记忆库',14)]:
        matches.append({'interaction_id':i['id'],'target':target,'object':i[target]['name'],'concern_key':key,'basis':rule,'concrete_rule':rule,'source_refs':refs(line)})
    matched={'matches':complete_data_matches(model,matches),'pending':[]}
    model['concern-match']=matched
    return model


def run(output):
    data=inputs();output=Path(output)
    # Deliberately only illustrate the first RR interaction. Do not claim a full
    # case extraction or a paid model run from these frozen normal graph inputs.
    write_json(output/'first-interaction-input.json',data)
    frozen_party=[]
    causes={'human.authentication':'identity_rejected','human.authorization':'permission_denied',
      'service.query_retrieval.resource_existence':'instance_missing',
      'service.query_retrieval.result_correctness':'incorrect_result','service.query_retrieval.data_visibility':'visibility_violation'}
    for n,m in enumerate(data['concern-match']['matches'][:5],1):
        frozen_party.append({'id':'A'+str(n),'case_id':'SC002-UC002','interaction_id':'SC002-UC002-step1','layer':'RR',
          'object':m['object'],'operation':'查询记忆库列表','cause':causes[m['concern_key']],
          'conditions':['违反明示正常规则：'+m['concrete_rule']],'concern_key':m['concern_key'],
          'field':None,'rule_id':None,'source_status':'framework_inferred','derivation':'明示正常规则取反；离线固定响应示例','source_refs':m['source_refs']})
    with run_lock(output):
        ex=Execution(output,mocks={'exception-generate':{'scenarios':frozen_party,'pending':[]}})
        ex.add('exception-generate','exception-generate',static=data)
        state=ex.finish()
    if not state['complete']:raise RuntimeError('offline example did not validate')
    generated=next((output/'artifacts').glob('exception-generate.json'))
    import json
    g=json.loads(generated.read_text())['payload']['scenarios']
    # Documented E and illustrative GT are explicit fixtures, never given to G.
    existing=read_documents([Path(__file__).with_name('memory-existing.md')],'existing')[0]
    testdoc=read_documents([Path(__file__).with_name('memory-test.md')],'test')[0]
    e_refs=[{'source_id':existing['source_id'],'line_start':2,'line_end':2,'quote':existing['lines'][1]['text']}]
    e=[{**deepcopy(g[2]),'id':'E1','cause':'empty_list','conditions':['无匹配项；返回空列表，total=0'],'source_status':'explicit','derivation':'','source_refs':e_refs}]
    gt=[{**deepcopy(s),'id':'T-'+s['id'],'source_status':'explicit','derivation':''} for s in g if s['field'] is not None]
    for n,t in enumerate(gt,2):t['source_refs']=[{'source_id':testdoc['source_id'],'line_start':n,'line_end':n,'quote':testdoc['lines'][n-1]['text']}]
    gt.append({**deepcopy(g[2]),'id':'T-instance','source_status':'framework_inferred','derivation':'测试的资源不存在描述结合明确的记忆实例存在性约束细化；固定示例','source_refs':[{'source_id':testdoc['source_id'],'line_start':10,'line_end':10,'quote':testdoc['lines'][9]['text']}]+g[2]['source_refs']})
    decision=lambda a,b,status:{'left_id':a,'right_id':b,'status':status,'reason':'离线固定对应，按对象、操作、原因、必要条件核对'}
    eg=[decision(s['id'],'E1','unmatched') for s in g]
    tg=[decision(t['id'],s['id'],'full' if t['cause']==s['cause'] and t['field']==s['field'] else 'unmatched') for t in gt for s in g]
    te=[decision(t['id'],'E1','unmatched') for t in gt]
    report=compare_report(g,e,gt,eg,tg,te)
    report.update(example_only=True,ground_truth_status='固定示例，不是人工标注评测结果',model_executed=False)
    write_json(output/'illustrative_missing_report.json',report)
    for task in ('components','rr-ssd','api-map','api-parameters','concern-match'):export_task(output/'example-views',task,data[task])
    print('OFFLINE ONLY:',output,'; data rules:',len([s for s in g if s['field'] is not None]),'; party examples:',len(frozen_party))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);run(p.parse_args().output_dir)
