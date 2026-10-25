"""Read-only row-by-row exception audit; never changes or fabricates scores."""
from pathlib import Path
import json
from .storage import read_json,write_json
from .normal_rules import normalize_location

def audit_run(source,destination,case_ids=None):
    source,destination=Path(source),Path(destination);state=read_json(source/'workflow_tasks.json')['tasks'];cases=[]
    for key,record in state.items():
        if record.get('stage')!='exception-evaluation' or record.get('status')!='passed':continue
        cid=record['case']
        if case_ids and cid not in case_ids:continue
        evaluation=read_json(source/record['output_file'])['payload']
        if not case_ids and evaluation['metrics']['generation_validity']['value']!=0:continue
        def output(stage):return read_json(source/state[cid+':'+stage]['output_file'])['payload']
        g=output('exception-generate')['scenarios'];gt=output('test-ground-truth')['scenarios'];decisions=output('GT_G')['decisions'];rows=[]
        for side,items,others in [('G',g,gt),('GT',gt,g)]:
            for item in items:
                pairs=[d for d in decisions if d['right_id' if side=='G' else 'left_id']==item['id']]
                diagnostics=[]
                for other in others:
                    f,l=normalize_location(item.get('field'),item.get('data_location'));of,ol=normalize_location(other.get('field'),other.get('data_location'))
                    if f and f==of and l==ol and item.get('data_location')!=other.get('data_location'):diagnostics.append({'counterpart':other['id'],'issue':'field-location encoding differs; normalize before comparison, not automatic semantic hit'})
                    if item['interaction_id']!=other['interaction_id'] and item['concern_key']==other['concern_key']:diagnostics.append({'counterpart':other['id'],'issue':'same concern on different interactions: inspect failure ownership; do not automatically match a whole chain'})
                rows.append({'channel':side,'scenario':item,'comparisons':pairs,'structural_diagnostics':diagnostics})
        case={'case':cid,'before_metric':evaluation['metrics']['generation_validity'],'G_count':len(g),'GT_count':len(gt),'pair_count':len(decisions),'rows':rows}
        cases.append(case);write_json(destination/(cid+'.json'),case)
        lines=['# '+cid+' 逐条异常核查','','原始指标保留；结构诊断不自动改变命中。','']
        for row in rows:
            s=row['scenario'];lines+=['## '+row['channel']+' · '+s['id'],'',s['cause'],'',f"交互：{s['interaction_id']}；对象：{s['object']}；关注点：{s['concern_key']}；字段：{s.get('field')}；位置：{s.get('data_location')}",'','触发条件：'+'；'.join(s['conditions']),'','原文依据：']
            lines += [f"- {r['source_id']}:{r['line_start']}-{r['line_end']}：{r['quote']}" for r in s['source_refs']]
            lines+=['','| 对方ID | 原判定 | 原因 |','|---|---|---|']
            lines += ['| '+(' | '.join(str(d[k]).replace('|','\\|').replace('\n',' ') for k in ('left_id' if row['channel']=='G' else 'right_id','status','reason')))+' |' for d in row['comparisons']]
            lines+=['','结构诊断：'+json.dumps(row['structural_diagnostics'],ensure_ascii=False),'']
        (destination/(cid+'.md')).write_text('\n'.join(lines),encoding='utf8')
    summary={'source_run':str(source),'cases':[{k:v for k,v in c.items() if k!='rows'} for c in cases],
       'G_count':sum(c['G_count'] for c in cases),'GT_count':sum(c['GT_count'] for c in cases),'pair_count':sum(c['pair_count'] for c in cases),'status':'baseline preserved; revised scores must come from a separately versioned run'}
    write_json(destination/'summary.json',summary);return summary
