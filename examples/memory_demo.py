"""Offline fixture demo: supplied mock extractions, no model or network calls.

Exercises contracts, enrichment, deterministic rules, M and exporters. It does
not measure whether a model can extract or semantically compare these facts.
"""
from pathlib import Path
from copy import deepcopy
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.cac/tools'))
from scene_completion.source_documents import read_documents
from scene_completion.workflow import Execution,build_pipeline


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',required=True);args=parser.parse_args()
    root=Path(args.output_dir);sources=root/'fixture_sources';sources.mkdir(parents=True,exist_ok=True)
    rr_text='# SC002-UC002：查询记忆库列表\n开发者向WiseCloudMemoryPlatformService查询记忆库列表，可选memoryType，平台返回分页结果。\n6. 扩展路径：\n无匹配项时返回空列表，total为0。\n'
    sr_text='''# SC002-UC002：查询记忆库列表
开发者调用WiseCloudMemoryPlatformService的API-M-IF2，查询指定记忆实例下的记忆库列表。
接口地址：/ms/v1/memory-instances/{memoryInstanceID}/mem-repos
请求头：必填x-wisecloud-service-id，具体值约束未定义。
路径参数：必填memoryInstanceID，具体值约束未定义。
memoryType：可选，枚举PROFILE/SEMANTIC。
page：可选整数，默认1，最小1。
pageSize：可选整数，默认20，范围1-100。
成功返回200 OK、items[]以及分页结果。
'''
    (sources/'rr.md').write_text(rr_text);(sources/'sr.md').write_text(sr_text)
    rr=read_documents([sources/'rr.md'],'existing');sr=read_documents([sources/'sr.md'],'existing')
    def refs(doc,line):return [{'source_id':doc[0]['source_id'],'line_start':line,'line_end':line,'quote':doc[0]['lines'][line-1]['text']}]
    def party(name,position):return {'name':name,'position':position,'source_refs':refs(rr,2)}
    def interaction(layer):
        r=refs(rr,2) if layer=='RR' else refs(sr,2)
        return {'id':layer+'-request','case_id':'SC002-UC002','sequence':1,'parent_id':None,'layer':layer,
          'sender':{**party('开发者','外部Actor（人类）'),'source_refs':r},'receiver':{**party('WiseCloudMemoryPlatformService','内部服务'),'source_refs':r},
          'operation':{'name':'查询记忆库列表','kinds':['read'],'sequence':['查询记忆库列表'],'optional':[],'source_refs':r},
          'data':{'sequence':[]},'direction':'request','api_id':'API-M-IF2' if layer=='SR' else None,'source_refs':r}
    params=[]
    def parameter(name,location,required,line,dtype=None,default=None,rules=()):
        return {'name':name,'location':location,'required':required,'data_type':dtype,'default':default,
          'constraints':[{'id':name+'-'+k,'kind':k,'value':v,'status':'explicit','source_refs':refs(sr,line)} for k,v in rules],'source_refs':refs(sr,line)}
    params=[parameter('x-wisecloud-service-id','header',True,4),parameter('memoryInstanceID','path',True,5),
      parameter('memoryType','query',False,6,rules=[('enum',['PROFILE','SEMANTIC'])]),
      parameter('page','query',False,7,'integer',1,[('minimum',1)]),parameter('pageSize','query',False,8,'integer',20,[('minimum',1),('maximum',100)])]
    interface={'id':'API-M-IF2','name':'查询记忆库列表','method':None,'address':'/ms/v1/memory-instances/{memoryInstanceID}/mem-repos','source_refs':refs(sr,3)}
    components={'components':[{'id':str(i),'name':name,'composition_type':kind,'parent_id':None,'source_status':'explicit','source_refs':refs(rr,2)} for i,(name,kind) in enumerate([('开发者','外部Actor（人类）'),('WiseCloudMemoryPlatformService','内部服务')])],'relations':[]}
    mocks={'components':components,'api-map':{'services':[{'name':'WiseCloudMemoryPlatformService','interfaces':[interface],'source_refs':refs(sr,2)}]},
      'api-parameters':{'apis':[{k:v for k,v in interface.items() if k!='method'}|{'parameters':params}]},
      'rr-ssd':{'interactions':[interaction('RR')]},'sr-ssd':{'interactions':[interaction('SR')]},
      'interaction-align':{'aliases':[],'links':[{'rr_id':'RR-request','sr_ids':['SR-request'],'status':'confirmed','basis':'fixture中明示同一查询','source_refs':refs(sr,2)}]},
      'concern-match':{'matches':[],'pending':[]},'exception-generate':{'scenarios':[],'pending':[]},
      'existing-extract':{'scenarios':[{'id':'existing-empty','case_id':'SC002-UC002','interaction_id':'RR-request','layer':'RR',
       'object':'WiseCloudMemoryPlatformService','operation':'查询记忆库列表','cause':'no_matching_records','conditions':['按本次查询条件检索无匹配记录'],
       'concern_key':'service.query_retrieval.resource_existence','field':None,'rule_id':None,'source_status':'explicit','derivation':'','source_refs':refs(rr,4),
       'steps':{'normal_context':['开发者查询记忆库列表'],'trigger':'无匹配项','documented_follow_up':[{'action':'返回空列表，total为0','source_refs':refs(rr,4)}]}}]}}
    def compare(packet):
        g,e=packet['input']['left'],packet['input']['right'];decisions=[];missing=[]
        for a in g:
            hit=False
            for b in e:
                full=all(a[k]==b[k] for k in ('case_id','layer','object','operation','cause','conditions'))
                hit|=full;decisions.append({'left_id':a['id'],'right_id':b['id'],'status':'full' if full else 'unmatched','reason':'offline fixture exact facts'})
            if not hit:missing.append(a)
        return {'decisions':decisions,'missing':missing}
    mocks['gap-compare']=compare
    ex=Execution(root/'run',mocks=mocks,config={'max_concurrency':2,'fixture_version':'memory-demo-1.1'},case_ids=['SC002-UC002'])
    build_pipeline(ex,rr,sr,[]);result=ex.finish();print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['complete'] else 2

if __name__=='__main__':raise SystemExit(main())
