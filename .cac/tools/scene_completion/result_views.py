"""Read-only, use-case/interaction views of persisted execution results.

No model calls, new matching, or reclassification happen in this module.
"""
from pathlib import Path
from .storage import read_json, fingerprint
from .execution_graph import LABELS, artifact_folder


class ResultView:
    def __init__(self, project):
        self.project=Path(project);self.root=self.project/'run'
        self.state=read_json(self.root/'workflow_tasks.json').get('tasks',{}) if (self.root/'workflow_tasks.json').exists() else {}
        graph=self.root/'workflow_graph.json'
        active={n['id'] for n in read_json(graph).get('nodes',[])} if graph.exists() else set(self.state)
        self.state={k:r for k,r in self.state.items() if k in active}
        self.manifest=read_json(self.root/'run_manifest.json') if (self.root/'run_manifest.json').exists() else {}

    def payload(self, key):
        r=self.state.get(key,{})
        if r.get('status')!='passed' or not r.get('output_file'):return {}
        path=(self.root/r['output_file']).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():return {}
        return read_json(path).get('payload',{})

    def cases(self):
        names={c['id']:c['name'] for key in ('rr-use-cases','sr-use-cases') for c in self.payload(key).get('cases',[])}
        groups={g['id']:g for g in self.payload('use-case-align').get('groups',[])}
        ids=sorted({r['case'] for r in self.state.values() if r.get('case') not in {None,'shared'}})
        return [{'id':cid,'name':' / '.join(dict.fromkeys(names[i] for i in groups.get(cid,{}).get('rr_ids',[])+groups.get(cid,{}).get('sr_ids',[]) if i in names)) or cid,
                 'analysis_complete':self.manifest.get('analysis_by_case',{}).get(cid,False),
                 'evaluation_complete':self.manifest.get('evaluation_by_case',{}).get(cid,False)} for cid in ids]

    def catalog(self):
        out=[]
        stages={'components','fused-ssd','rr-ssd','sr-ssd','object-operations','api-map','api-parameters','concern-match','normal-rules','missing-report','exception-evaluation'}
        for key,r in self.state.items():
            if r.get('status')!='passed' or r['stage'] not in stages or '--part-' in key:continue
            case=r['case'];stem=(key if case=='shared' else key[len(case)+1:]).replace(':','--')
            files=[]
            for ext in ('svg','json','md','dot'):
                p=artifact_folder(self.root,key,case)/(stem+'.'+ext)
                if p.is_file():files.append({'name':p.name,'path':p.relative_to(self.project).as_posix(),'bytes':p.stat().st_size,'task_key':key})
            if files:out.append({'key':key,'case':case,'label':LABELS.get(r['stage'],r['stage']),'stage':r['stage'],'files':files})
        return sorted(out,key=lambda x:(x['case']!='shared',x['case'],x['label']))

    def index(self):
        return {'complete':self.manifest.get('complete',False),'cases':self.cases(),'artifacts':self.catalog(),
                'registry_hash':self.manifest.get('registry_hash'),'recommendation':'未启用'}

    def detail(self, cid):
        case=next((c for c in self.cases() if c['id']==cid),None)
        if case is None:raise ValueError('未知用例')
        enriched=self.payload(cid+':enriched-view')
        fused=self.payload(cid+':fused-ssd')
        if not enriched and fused:
            from .inverse_alignment import canonical_fused
            enriched=canonical_fused(fused)
        evaluation=self.payload(cid+':exception-evaluation')
        report=self.payload(cid+':missing-report')
        channels={k:self.payload(cid+':'+stage).get('scenarios',[]) for k,stage in [('G','exception-generate'),('E','existing-extract'),('GT','test-ground-truth')]}
        # Report/evaluation snapshots contain the exact normalized units used
        # in scoring; prefer them over an earlier task's intermediate units.
        for k in channels:
            if k in evaluation:channels[k]=evaluation[k]
            elif k in report:channels[k]=report[k]
        missing={s['id'] if isinstance(s,dict) else s for s in report.get('M',[])}
        rows=[];seen=set()
        for interaction in sorted(enriched.get('interactions',[]),key=lambda i:i.get('sequence',0)):
            iid=interaction['id'];seen.add(iid)
            scoped={k:[s for s in values if (s.get('canonical_interaction_id') or s.get('interaction_id'))==iid] for k,values in channels.items()}
            rows.append({'interaction':interaction,'channels':scoped,
                         'concerns':{k:sorted({s['concern_key'] for s in values}) for k,values in scoped.items()},
                         'missing_ids':[s['id'] for s in scoped['G'] if s['id'] in missing]})
        reg_hash=self.manifest.get('registry_hash');p=self.root/'registry_used'/(str(reg_hash)+'.json')
        definitions=read_json(p).get('definitions',{}) if p.is_file() else {}
        return {'case':case,'interactions':rows,'unbound':{k:[s for s in v if (s.get('canonical_interaction_id') or s.get('interaction_id')) not in seen] for k,v in channels.items()},
                'definitions':definitions,'registry_hash':reg_hash,'registry_available':bool(definitions),
                'metrics':evaluation.get('metrics',{}),'full_matches':evaluation.get('full_matches',report.get('full_matches',{})),
                'partial_diagnostics':evaluation.get('partial_diagnostics',report.get('partial_diagnostics',{})),
                'rr_sr_links':fused.get('rr_sr_links',[]),'artifacts':[a for a in self.catalog() if a['case'] in {'shared',cid}]}
