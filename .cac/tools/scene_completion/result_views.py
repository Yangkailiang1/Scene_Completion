"""Read-only, use-case/interaction views of persisted execution results.

No model calls, new matching, or reclassification happen in this module.
"""
from pathlib import Path
from .storage import read_json
from .execution_graph import LABELS, artifact_folder


class ResultView:
    def __init__(self, project):
        self.project=Path(project);self.root=self.project/'run'
        self.state=read_json(self.root/'workflow_tasks.json').get('tasks',{}) if (self.root/'workflow_tasks.json').exists() else {}
        graph=self.root/'workflow_graph.json'
        self.nodes={n['id']:n for n in read_json(graph).get('nodes',[])} if graph.exists() else {}
        active=set(self.nodes) if graph.exists() else set(self.state)
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
            if files:out.append({'key':key,'case':case,'label':self.nodes.get(key,{}).get('label') or LABELS.get(r['stage'],r['stage']),'stage':r['stage'],'files':files})
        priority={'components':0,'fused-ssd':1,'rr-ssd':2,'sr-ssd':3,'object-operations':4,'api-map':5,'api-parameters':6}
        return sorted(out,key=lambda x:(priority.get(x['stage'],10),x['case']!='shared',x['case'],x['label']))

    def index(self):
        return {'complete':self.manifest.get('complete',False),'cases':self.cases(),'artifacts':self.catalog(),
                'registry_hash':self.manifest.get('registry_hash'),'recommendation':'未启用'}

    def metrics(self):
        from .result_alignment import aggregate_metrics
        rows=[]
        for c in self.cases():
            v=self.payload(c['id']+':exception-evaluation')
            pending=len(self.payload(c['id']+':test-ground-truth').get('pending',[]))
            rows.append({**c,'metrics':v.get('metrics',{}),'counts':{k:len(v.get(k,[])) for k in ('G','E','GT','M')},'truth_pending':pending,'generation_breakdown':v.get('generation_breakdown',{}),'status':'已评测（GT有待确认项）' if v and pending else '已评测' if v else '未评测'})
        sessions=read_json(self.root/'execution_sessions.json') if (self.root/'execution_sessions.json').exists() else []
        history=[]
        for p in (self.root/'report_versions').glob('*/missing_report.json'):
            summary=p.parent/'metrics_summary.json'
            history.append({'name':p.parent.name,'path':p.relative_to(self.project).as_posix(),'metrics':read_json(summary).get('metrics') if summary.exists() else None})
        generated=sum(r['counts']['G'] for r in rows);truth=sum(r['counts']['GT'] for r in rows)
        return {'cases':rows,'metrics':aggregate_metrics(rows),'diagnostic_counts':{'G':generated,'GT':truth,'one_to_one_ceiling':min(100,100*truth/generated) if generated else None},'complete':self.manifest.get('complete',False),'ruleset_version':self.manifest.get('ruleset_version'),'execution_id':sessions[-1]['id'] if sessions else None,
                'registry_hash':self.manifest.get('registry_hash'),'truth_source':'测试文档经机器整理（含允许的框架推导）','recommendation':'未启用',
                'history':history,'audit_files':[{'name':p.name,'path':p.relative_to(self.project).as_posix(),'bytes':p.stat().st_size} for p in sorted((self.root/'artifacts/shared/alignment-quality').glob('*')) if p.is_file() and p.suffix in {'.json','.md'}]}

    def scenario(self,cid,channel,sid):
        if channel not in {'G','E','GT'}:raise ValueError('未知结果来源')
        evaluation=self.payload(cid+':exception-evaluation')
        stage={'G':'exception-generate','E':'existing-extract','GT':'test-ground-truth'}[channel]
        values=evaluation.get(channel,self.payload(cid+':'+stage).get('scenarios',[]))
        value=next((s for s in values if s['id']==sid),None)
        if value is None:raise ValueError('该异常版本已变化，请刷新结果')
        return value

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
        from .result_alignment import align_rows
        pairs=evaluation.get('full_matches',{})
        if not pairs:pairs={'G_E':report.get('full_matches',[])}
        decisions={purpose:self.payload(cid+':'+stage).get('decisions',[]) for purpose,stage in [('G_E','gap-compare'),('GT_G','GT_G'),('GT_E','GT_E')]}
        rows=[];seen=set()
        for interaction in sorted(enriched.get('interactions',[]),key=lambda i:i.get('sequence',0)):
            iid=interaction['id'];seen.add(iid)
            scoped={k:[s for s in values if (s.get('canonical_interaction_id') or s.get('interaction_id'))==iid] for k,values in channels.items()}
            rows.append({'interaction':interaction,'channels':scoped,
                         'alignment_rows':align_rows(scoped,pairs,decisions),
                         'concerns':{k:sorted({s['concern_key'] for s in values}) for k,values in scoped.items()},
                         'missing_ids':[s['id'] for s in scoped['G'] if s['id'] in missing]})
        reg_hash=self.manifest.get('registry_hash');p=self.root/'registry_used'/(str(reg_hash)+'.json')
        definitions=read_json(p).get('definitions',{}) if p.is_file() else {}
        # The initial table carries triggers and IDs; long evidence is fetched
        # only when a cell is expanded, from the same frozen output version.
        def compact(s):
            return {**{k:v for k,v in s.items() if k not in {'source_refs','derivation','steps'}},'steps':{'trigger':s.get('steps',{}).get('trigger')},'lazy_detail':True}
        for row in rows:
            row['channels']={k:[compact(s) for s in values] for k,values in row['channels'].items()}
            for aligned in row['alignment_rows']:
                aligned['anchor']=compact(aligned['anchor'])
                aligned['cells']={k:[compact(s) for s in values] for k,values in aligned['cells'].items()}
        return {'case':case,'interactions':rows,'unbound':{k:[s for s in v if (s.get('canonical_interaction_id') or s.get('interaction_id')) not in seen] for k,v in channels.items()},
                'definitions':definitions,'registry_hash':reg_hash,'registry_available':bool(definitions),
                'metrics':evaluation.get('metrics',{}),'full_matches':evaluation.get('full_matches',report.get('full_matches',{})),
                'partial_diagnostics':evaluation.get('partial_diagnostics',report.get('partial_diagnostics',{})),
                'rr_sr_links':fused.get('rr_sr_links',[]),'artifacts':[a for a in self.catalog() if a['case'] in {'shared',cid}]}
