"""Audit saved cases against the new identities without fabricating recognition.

Old scenes may demonstrate that their four-element identity can be resolved;
they cannot become new G_c. This command does not call models or alter a run.
"""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.cac/tools'))
from scene_completion.result_views import ResultView
from scene_completion.concern_alignment import scenario_bindings,VERSION
from scene_completion.concern_registry import registry_scope,default_registry
from scene_completion.storage import read_json,write_json


def audit(project):
    project=Path(project);view=ResultView(project)
    snapshot=project/'run/registry_used'/(str(view.manifest.get('registry_hash'))+'.json')
    reg=read_json(snapshot) if snapshot.exists() else default_registry();cases=[]
    with registry_scope(reg):
        for case in view.cases():
            cid=case['id'];fused=view.payload(cid+':fused-ssd');enriched=view.payload(cid+':enriched-view')
            positive={'fused-ssd':fused,'api-parameters':view.payload('api-parameters')}
            if enriched:positive['enriched-interactions']=enriched
            saved=view.payload(cid+':exception-evaluation') or view.payload(cid+':missing-report')
            channels={}
            for key in ('G','E','GT'):
                resolved=[];pending=[]
                for s in saved.get(key,[]):
                    anchors=scenario_bindings(s,positive)
                    (resolved if anchors else pending).append({'id':s['id'],'binding_ids':[a['binding_id'] for a in anchors],
                        'object':s.get('object'),'concern_key':s['concern_key']})
                channels[key]={'scene_count':len(saved.get(key,[])),'resolvable':len(resolved),'unresolved':pending}
            cases.append({'id':cid,'name':case['name'],'channels':channels,
                'new_recognition_required':not bool(view.payload(cid+':concern-evaluation'))})
    return {'version':VERSION,'mode':'offline_identity_audit','official_metrics':None,
            'policy':'旧场景仅检查定位可迁移性，不反推为新版G_c，不生成新指标，不调用模型',
            'case_count':len(cases),'cases':cases}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('project',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();value=audit(args.project);write_json(args.output,value)
    print(json.dumps({'case_count':value['case_count'],'output':str(args.output),'official_metrics':None},ensure_ascii=False))
